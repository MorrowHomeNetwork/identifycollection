"""
Tests for launch.py, the program behind the double-click.

These exercise the pieces that protect a museum's data: one copy at a time,
a safety copy before any upgrade, and a refusal to run old code on newer data.
The complete double-click journey is tested separately, against the finished
zip, by packaging/smoke_test.py.
"""

import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import launch

APP_DIR = Path(launch.__file__).resolve().parent


class PortTests(unittest.TestCase):
    def test_listens_on_this_computer_only(self):
        sock = launch.open_listening_socket(0)
        self.addCleanup(sock.close)
        host, port = sock.getsockname()
        self.assertEqual(host, "127.0.0.1")
        self.assertGreater(port, 0)

    def test_moves_to_another_port_when_the_preferred_one_is_taken(self):
        blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(blocker.close)
        blocker.bind(("127.0.0.1", 0))
        blocker.listen(1)
        taken = blocker.getsockname()[1]

        sock = launch.open_listening_socket(taken)
        self.addCleanup(sock.close)
        self.assertNotEqual(sock.getsockname()[1], taken)


class BackupTests(unittest.TestCase):
    def test_backup_is_a_complete_working_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            original = Path(folder) / "db.sqlite3"
            connection = sqlite3.connect(original)
            connection.execute("CREATE TABLE ledger (entry TEXT)")
            connection.execute("INSERT INTO ledger VALUES ('accession 1987.12.4')")
            connection.commit()
            connection.close()

            copy = launch.backup_database(original, Path(folder) / "backups", "upgrade-to-9.9.9")

            self.assertTrue(copy.name.startswith("db-before-upgrade-to-9.9.9-"))
            self.assertEqual(copy.suffix, ".sqlite3")
            check = sqlite3.connect(copy)
            try:
                self.assertEqual(check.execute("SELECT entry FROM ledger").fetchall(), [("accession 1987.12.4",)])
            finally:
                check.close()


class _FakeApp(BaseHTTPRequestHandler):
    """Stands in for a running IdentifyCollection: answers /healthz and nothing else."""

    answer: dict = {}

    def do_GET(self):  # noqa: N802 - the name is fixed by http.server
        body = json.dumps(self.answer).encode()
        self.send_response(200 if self.path == "/healthz" else 404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep test output quiet
        pass


class RunningInstanceTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.data_dir = Path(folder.name)

    def _serve(self, answer):
        handler = type("Handler", (_FakeApp,), {"answer": answer})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}/"

    def _write_run_file(self, url, instance):
        launch.run_file(self.data_dir).write_text(json.dumps({"url": url, "instance": instance}), encoding="utf-8")

    def test_no_run_file_means_not_running(self):
        self.assertIsNone(launch.find_running_instance(self.data_dir))

    def test_damaged_run_file_is_ignored(self):
        launch.run_file(self.data_dir).write_text("not json", encoding="utf-8")
        self.assertIsNone(launch.find_running_instance(self.data_dir))

    def test_leftover_run_file_from_a_closed_copy_is_ignored(self):
        closed = socket.socket()
        closed.bind(("127.0.0.1", 0))
        port = closed.getsockname()[1]
        closed.close()  # nothing is listening on this port any more
        self._write_run_file(f"http://127.0.0.1:{port}/", "abc")
        self.assertIsNone(launch.find_running_instance(self.data_dir))

    def test_running_copy_is_recognised_by_its_instance_code(self):
        url = self._serve({"app": "identifycollection", "status": "ok", "instance": "abc"})
        self._write_run_file(url, "abc")
        self.assertEqual(launch.find_running_instance(self.data_dir), url)

    def test_a_different_program_on_the_same_port_is_not_mistaken_for_us(self):
        url = self._serve({"app": "identifycollection", "status": "ok", "instance": "someone-else"})
        self._write_run_file(url, "abc")
        self.assertIsNone(launch.find_running_instance(self.data_dir))

    def test_waiting_gives_up_quietly(self):
        self.assertIsNone(launch.wait_for_running_instance(self.data_dir, 0))


def _run_python(code: str, *args: str, **env_changes: str) -> subprocess.CompletedProcess:
    """Run a snippet in a separate Python process, the way a second double-click would."""
    env = {**os.environ, **env_changes}
    return subprocess.run(
        [sys.executable, "-c", code, *args],
        cwd=APP_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


TRY_LOCK = """
import sys
from pathlib import Path
sys.path.insert(0, ".")
import launch
print("FREE" if launch.acquire_single_instance_lock(Path(sys.argv[1])) is not None else "HELD")
"""


class SingleInstanceLockTests(unittest.TestCase):
    def test_a_second_copy_cannot_claim_the_same_data_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            lock = launch.acquire_single_instance_lock(Path(folder))
            self.assertIsNotNone(lock)
            try:
                second = _run_python(TRY_LOCK, folder)
                self.assertEqual(second.stdout.strip(), "HELD", second.stderr)
            finally:
                os.close(lock)

            # Once the first copy has gone, the folder is free again.
            third = _run_python(TRY_LOCK, folder)
            self.assertEqual(third.stdout.strip(), "FREE", third.stderr)


DATABASE_JOURNEY = """
import json, sqlite3, sys
from pathlib import Path
sys.path.insert(0, ".")
import django
django.setup()
from django.conf import settings
from django.core.management import call_command
from django.db import connection
import launch

data_dir = Path(sys.argv[1])
db = Path(settings.DATABASES["default"]["NAME"])
backups = data_dir / "backups"
count = lambda: len(list(backups.glob("*.sqlite3"))) if backups.exists() else 0
report = {}

# 1. First start: the database is created; there is nothing to back up.
launch.prepare_database(data_dir)
report["created"] = db.exists() and db.stat().st_size > 0
report["backups_after_first_start"] = count()

# 2. Ordinary start: nothing to do, still no backup.
launch.prepare_database(data_dir)
report["backups_after_second_start"] = count()

# 3. An upgrade: pretend this database was made by an older version by
#    un-applying our own migrations, then start again.
call_command("migrate", "accounts", "zero", interactive=False, verbosity=0)
connection.close()
launch.prepare_database(data_dir)
report["backups_after_upgrade"] = count()
tables = connection.introspection.table_names()
report["upgraded"] = "accounts_user" in tables

# 4. A downgrade: the database knows a change this code has never heard of.
connection.close()
raw = sqlite3.connect(db)
raw.execute("INSERT INTO django_migrations (app, name, applied) VALUES ('accounts', '9999_from_the_future', '2099-01-01')")
raw.commit()
raw.close()
try:
    launch.prepare_database(data_dir)
    report["refused_newer_data"] = False
except launch.LaunchError as exc:
    report["refused_newer_data"] = "NEWER version" in str(exc)
report["backups_after_refusal"] = count()

print("REPORT " + json.dumps(report))
"""


class DatabasePreparationTests(unittest.TestCase):
    """Runs against a real database file in a scratch folder, in a separate process."""

    def test_create_then_upgrade_with_backup_then_refuse_newer_data(self):
        with tempfile.TemporaryDirectory() as folder:
            result = _run_python(
                DATABASE_JOURNEY,
                folder,
                IDENTIFYCOLLECTION_DATA_DIR=folder,
                IDENTIFYCOLLECTION_MODE="dev",
                DJANGO_SETTINGS_MODULE="config.settings",
            )
            lines = [line for line in result.stdout.splitlines() if line.startswith("REPORT ")]
            self.assertTrue(lines, f"no report produced.\nstdout: {result.stdout}\nstderr: {result.stderr}")
            report = json.loads(lines[-1][len("REPORT ") :])

        self.assertEqual(
            report,
            {
                "created": True,
                "backups_after_first_start": 0,
                "backups_after_second_start": 0,
                "backups_after_upgrade": 1,
                "upgraded": True,
                "refused_newer_data": True,
                "backups_after_refusal": 1,
            },
        )
