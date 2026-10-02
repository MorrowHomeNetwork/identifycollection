"""
launch.py: starts the portable (double-click) build of IdentifyCollection.

"Start IdentifyCollection.bat" runs this file with the Python that ships
inside the zip. In order, it:

  1. works out where it lives and where the "data" folder next to it is;
  2. if IdentifyCollection is already running from this folder, simply
     reopens the browser on it and stops;
  3. prepares the database: creates it the first time, upgrades it after an
     update (taking a safety copy first);
  4. starts a small web server that only this computer can reach;
  5. opens the default web browser on it.

Developers use "python manage.py runserver" instead; this file is for the
people who should never have to think about any of the above.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import secrets
import socket
import sqlite3
import sys
import time
import traceback
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
BUNDLE_DIR = APP_DIR.parent

HOST = "127.0.0.1"  # "this computer only": nothing on the network can connect
PREFERRED_PORT = 8765
PORT_ATTEMPTS = 20
WAIT_FOR_OTHER_COPY_SECONDS = 60

log = logging.getLogger("identifycollection.launch")

# For talking to our own copy on this computer. Deliberately ignores any
# "proxy" (a go-between some office networks route web traffic through): a
# request to this very computer must never be sent out through one.
_local_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

# Remembered so that a crash report can be written next to the data it is about.
_data_dir_in_use: Path | None = None


class LaunchError(Exception):
    """A problem we can explain to the person in plain words."""


def say(message: str = "") -> None:
    """Print to the launcher window. Our own wording is plain ASCII; folder names may not be."""
    if sys.stdout is None:
        return
    try:
        print(message, flush=True)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "ascii"
        print(message.encode(encoding, "replace").decode(encoding), flush=True)
    except OSError:
        pass  # the window is gone; nothing useful to do


# ---------------------------------------------------------------------------
# The data folder
# ---------------------------------------------------------------------------


def resolve_data_dir(cli_value: str | None) -> Path:
    chosen = cli_value or os.environ.get("IDENTIFYCOLLECTION_DATA_DIR")
    return Path(chosen).resolve() if chosen else BUNDLE_DIR / "data"


def ensure_writable(data_dir: Path) -> None:
    """IdentifyCollection keeps everything in its data folder, so it must be able to write there."""
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        probe = data_dir / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        raise LaunchError(
            "IdentifyCollection cannot save files in its own folder:\n"
            f"    {data_dir}\n"
            "Move the whole IdentifyCollection folder somewhere you can save to,\n"
            "such as Documents or the Desktop, and start it again.\n"
            f"(The system said: {exc})"
        ) from exc


# ---------------------------------------------------------------------------
# One copy at a time
# ---------------------------------------------------------------------------


def run_file(data_dir: Path) -> Path:
    return data_dir / "run.json"


def acquire_single_instance_lock(data_dir: Path) -> int | None:
    """
    Claim the data folder for this copy of the app.

    Two copies writing to one database at the same time is how data gets
    damaged, and double-clicking twice is the most natural thing in the world.
    So the first copy takes a lock on a small file and keeps it for as long
    as it runs. The operating system releases the lock by itself when the
    program ends, however it ends, so a crash never leaves the folder stuck.

    Returns a file handle to keep open, or None if another copy has the lock.
    """
    handle = os.open(data_dir / "run.lock", os.O_RDWR | os.O_CREAT)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(handle)
        return None
    return handle


def find_running_instance(data_dir: Path) -> str | None:
    """
    If IdentifyCollection is already running from this data folder, return its
    address. A leftover run.json from a copy that was closed is ignored: we
    only believe it if the app answers and quotes the same instance code.
    """
    try:
        info = json.loads(run_file(data_dir).read_text(encoding="utf-8"))
        url, instance = info["url"], info["instance"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    try:
        with _local_opener.open(url + "healthz", timeout=3) as response:
            answer = json.load(response)
    except (OSError, ValueError, urllib.error.URLError):
        return None
    if answer.get("app") == "identifycollection" and answer.get("instance") == instance:
        return url
    return None


def wait_for_running_instance(data_dir: Path, seconds: float) -> str | None:
    """Another copy holds the lock; give it time to finish starting, then return its address."""
    deadline = time.monotonic() + seconds
    while True:
        url = find_running_instance(data_dir)
        if url or time.monotonic() >= deadline:
            return url
        time.sleep(0.5)


# ---------------------------------------------------------------------------
# The network port
# ---------------------------------------------------------------------------


def open_listening_socket(preferred_port: int = PREFERRED_PORT) -> socket.socket:
    """
    Claim a port on this computer for the app to listen on.

    A "port" is a numbered door on the computer; the browser needs to know
    which door to knock on. We ask for the same one each time so bookmarks
    keep working, try the next few if another program has it, and finally
    let the system pick any free one.
    """
    candidates = [preferred_port + offset for offset in range(PORT_ATTEMPTS)] if preferred_port else []
    candidates = [port for port in candidates if port < 65536]
    candidates.append(0)  # 0 means "any free port"
    last_error: OSError | None = None
    for port in candidates:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                # Windows: insist on sole use of the port. Without this, Windows
                # lets two programs listen on one port and the browser may reach
                # the wrong one.
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else:
                # Elsewhere: allow reusing the port straight after a restart.
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((HOST, port))
            return sock
        except OSError as exc:
            last_error = exc
            sock.close()
    raise LaunchError(f"Could not open any network port on this computer ({last_error}).")


# ---------------------------------------------------------------------------
# The database
# ---------------------------------------------------------------------------


def backup_database(db_path: Path, backup_dir: Path, label: str) -> Path:
    """Copy the database safely (SQLite's own backup routine), and return the copy's path."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = backup_dir / f"db-before-{label}-{stamp}.sqlite3"
    source = sqlite3.connect(db_path)
    try:
        destination = sqlite3.connect(target)
        try:
            source.backup(destination)
        finally:
            destination.close()
    finally:
        source.close()
    return target


def prepare_database(data_dir: Path) -> None:
    """
    Bring the database up to date with this version of the app.

    Django records every change to the database layout as a numbered
    "migration". Applying the ones this database has not seen yet is how a
    new version upgrades an existing museum's data in place.
    """
    from django.conf import settings
    from django.core.management import call_command
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    db_path = Path(settings.DATABASES["default"]["NAME"])
    had_data = db_path.exists() and db_path.stat().st_size > 0

    executor = MigrationExecutor(connection)
    loader = executor.loader

    # Refuse to run old code against newer data. If the database records
    # changes this version has never heard of, a newer IdentifyCollection made
    # them, and guessing would risk the museum's records.
    from_the_future = sorted(
        key for key in loader.applied_migrations if key[0] in loader.migrated_apps and key not in loader.disk_migrations
    )
    if from_the_future:
        connection.close()
        raise LaunchError(
            "This data folder was last used by a NEWER version of IdentifyCollection\n"
            f"than this one ({settings.VERSION}). Nothing has been changed.\n"
            "Start the newer version instead, or put back a backup of the data\n"
            "folder that was made with this version."
        )

    pending = executor.migration_plan(loader.graph.leaf_nodes())
    if not pending:
        return

    if had_data:
        connection.close()
        say("  Updating the database for this version (a safety copy is made first) ...")
        backup = backup_database(db_path, data_dir / "backups", f"upgrade-to-{settings.VERSION}")
        log.info("Database backed up to %s before applying %d migration(s)", backup, len(pending))
    else:
        say("  First start: creating the database ...")

    call_command("migrate", interactive=False, verbosity=0)
    log.info("Applied %d migration(s)", len(pending))


# ---------------------------------------------------------------------------
# Start-up
# ---------------------------------------------------------------------------


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the portable build of IdentifyCollection.")
    parser.add_argument("--no-browser", action="store_true", help="do not open the web browser")
    parser.add_argument(
        "--port",
        type=int,
        default=PREFERRED_PORT,
        help=f"preferred port (default {PREFERRED_PORT}; 0 = any free port)",
    )
    parser.add_argument("--data-dir", help="where to keep data (default: the data folder next to app)")
    return parser.parse_args(argv)


def run(argv: list[str]) -> int:
    global _data_dir_in_use

    args = parse_args(argv)

    # With Python's isolated mode the script's own folder is not searched for
    # imports automatically, so add it: this is how "config", "accounts" and
    # "core" are found.
    if str(APP_DIR) not in sys.path:
        sys.path.insert(0, str(APP_DIR))

    data_dir = resolve_data_dir(args.data_dir)
    _data_dir_in_use = data_dir
    ensure_writable(data_dir)

    version = (APP_DIR / "VERSION").read_text(encoding="utf-8").strip()
    say()
    say(f"  IdentifyCollection {version}")
    say()

    lock = acquire_single_instance_lock(data_dir)
    if lock is None:
        say("  IdentifyCollection is already open from this folder. Finding it ...")
        existing = wait_for_running_instance(data_dir, WAIT_FOR_OTHER_COPY_SECONDS)
        if not existing:
            raise LaunchError(
                "Another IdentifyCollection window is using this folder but did not\n"
                "answer. Look for that window and close it, then start again. If you\n"
                "cannot find one, restart the computer and start again."
            )
        say(f"  Already running at {existing}")
        if not args.no_browser:
            webbrowser.open(existing)
        return 0

    instance = secrets.token_hex(8)
    os.environ["IDENTIFYCOLLECTION_MODE"] = "portable"
    os.environ["IDENTIFYCOLLECTION_DATA_DIR"] = str(data_dir)
    os.environ["IDENTIFYCOLLECTION_INSTANCE"] = instance
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    if (data_dir / "db.sqlite3").exists():
        say("  Starting ...")
    else:
        say("  Starting for the first time. This can take a minute ...")

    import django

    django.setup()
    log.info("Launcher starting: version %s, data folder %s, Python %s", version, data_dir, sys.version.split()[0])

    prepare_database(data_dir)

    from waitress import create_server

    from config.wsgi import application

    sock = open_listening_socket(args.port)
    port = sock.getsockname()[1]
    url = f"http://{HOST}:{port}/"
    server = create_server(application, sockets=[sock], threads=8, ident="IdentifyCollection")

    run_path = run_file(data_dir)
    temporary = run_path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(
            {
                "url": url,
                "port": port,
                "pid": os.getpid(),
                "instance": instance,
                "version": version,
                "python": sys.executable,
                "started": datetime.now().astimezone().isoformat(timespec="seconds"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    temporary.replace(run_path)  # swapped in whole, so a reader never sees half a file

    say()
    say(f"  IdentifyCollection is running at:  {url}")
    say()
    say("  Your web browser should open by itself. If it does not, type the")
    say("  address above into it.")
    say()
    say("  Keep this window open while you work.")
    say("  To stop IdentifyCollection, close this window.")
    say()
    log.info("Serving on %s", url)

    if not args.no_browser:
        webbrowser.open(url)

    try:
        server.run()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            server.close()
        finally:
            try:
                run_path.unlink()
            except OSError:
                pass
            os.close(lock)
        log.info("Launcher stopped")
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        return run(sys.argv[1:] if argv is None else argv)
    except LaunchError as exc:
        if logging.getLogger().handlers:  # the log file is set up: keep a record there too
            log.error("Could not start: %s", exc)
        say()
        say("  " + str(exc).replace("\n", "\n  "))
        say()
        return 2
    except Exception:  # noqa: BLE001 - last line of defence: explain, record, exit non-zero
        details = traceback.format_exc()
        crash_file = (_data_dir_in_use or resolve_data_dir(None)) / "logs" / "launcher-crash.txt"
        try:
            crash_file.parent.mkdir(parents=True, exist_ok=True)
            with crash_file.open("a", encoding="utf-8") as handle:
                handle.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n{details}")
            where = f"The technical details were saved to:\n      {crash_file}"
        except OSError:
            where = "The technical details follow:\n" + details
        say()
        say("  IdentifyCollection could not start.")
        say("  " + where)
        say("  Please send that file to whoever set this up for you.")
        say()
        return 1


if __name__ == "__main__":
    sys.exit(main())
