#!/usr/bin/env python3
"""
smoke_test.py: proves that a built zip actually works.

    python packaging/smoke_test.py dist/IdentifyCollection-<version>-windows-x64.zip

A "smoke test" switches the finished thing on and checks that nothing catches
fire. This one does what a museum would do, with no shortcuts:

  1. extracts the zip into a folder with an awkward name (spaces, brackets,
     an ampersand, an accented letter), because real folders have such names;
  2. starts it through "Start IdentifyCollection.bat";
  3. opens the pages, creates the first staff account, signs out, signs in;
     then adds a scan, puts it on show, identifies someone as a visitor,
     accepts the answer as staff and downloads the export;
  4. checks the stylesheet and a font arrive, and that no page loads anything
     from the internet;
  5. starts it a second time and checks the second copy steps aside;
  6. stops it, starts it again, and checks the account is still there.

How the zip is started depends on the computer running the test:

  windows   the real thing: cmd.exe runs the batch file. Used by the GitHub
            build on every change. This is the result that counts.
  wine      on Linux, runs the same Windows programs through Wine, a
            compatibility layer. A good rehearsal, not proof.
  host      runs the app with this computer's own Python and its installed
            packages instead of the bundled Windows ones. Checks the app
            and its files, not the Windows runtime or the batch file.

It uses only Python's standard library.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
import zlib
from pathlib import Path

BAT_NAME = "Start IdentifyCollection.bat"
USERNAME = "smoke-tester"
PASSWORD = "glass-plate-negative-1911"
START_TIMEOUT = 300  # seconds; a first start under Wine or on a busy build machine can be slow

EXTERNAL_LOAD = re.compile(
    r"""<(?:link|script|img|source|iframe|video|audio|embed|object)\b[^>]*\b(?:href|src|data)\s*=\s*["']?\s*(?:https?:)?//""",
    re.IGNORECASE,
)


class SmokeFailure(Exception):
    pass


def note(message: str) -> None:
    print(f"  ok  {message}", flush=True)


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


# ---------------------------------------------------------------------------
# A very small web browser
# ---------------------------------------------------------------------------


class Browser:
    """Keeps cookies between requests, follows redirects, never uses a proxy."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPCookieProcessor(self.cookies),
        )

    def request(self, path: str, form: dict | None = None) -> tuple[int, str, bytes, dict]:
        url = urllib.parse.urljoin(self.base_url, path)
        data = urllib.parse.urlencode(form).encode() if form is not None else None
        request = urllib.request.Request(url, data=data, headers={"Referer": url})
        try:
            with self.opener.open(request, timeout=60) as response:
                return response.status, response.geturl(), response.read(), dict(response.headers)
        except urllib.error.HTTPError as error:
            return error.code, error.geturl(), error.read(), dict(error.headers)

    def get(self, path: str) -> tuple[int, str, str]:
        status, final_url, body, _headers = self.request(path)
        return status, urllib.parse.urlsplit(final_url).path, body.decode("utf-8")

    def post_files(self, path: str, fields: dict, files: dict, page_with_form: str, headers: dict | None = None):
        """Send a form that carries files, the way a browser's file chooser does."""
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page_with_form)
        expect(token is not None, f"no form security token found on the page before posting to {path}")
        boundary = uuid.uuid4().hex
        parts = []
        for name, value in {**fields, "csrfmiddlewaretoken": token.group(1)}.items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
        for name, (filename, content, kind) in files.items():
            head = f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\nContent-Type: {kind}\r\n\r\n'
            parts.append(head.encode() + content + b"\r\n")
        body = b"".join(parts) + f"--{boundary}--\r\n".encode()
        url = urllib.parse.urljoin(self.base_url, path)
        request = urllib.request.Request(
            url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Referer": url, **(headers or {})}
        )
        try:
            with self.opener.open(request, timeout=120) as response:
                return response.status, urllib.parse.urlsplit(response.geturl()).path, response.read()
        except urllib.error.HTTPError as error:
            return error.code, urllib.parse.urlsplit(error.geturl()).path, error.read()

    def post(self, path: str, form: dict, page_with_form: str) -> tuple[int, str, str]:
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page_with_form)
        expect(token is not None, f"no form security token found on the page before posting to {path}")
        status, final_url, body, _headers = self.request(path, {**form, "csrfmiddlewaretoken": token.group(1)})
        return status, urllib.parse.urlsplit(final_url).path, body.decode("utf-8")


# ---------------------------------------------------------------------------
# Starting and stopping the bundle
# ---------------------------------------------------------------------------


def _copy_output(pipe, log_path: Path) -> None:
    with log_path.open("wb") as log:
        for chunk in iter(lambda: pipe.read1(4096), b""):
            log.write(chunk)
            log.flush()


def find_program(*names: str, env_name: str | None = None, beside: str | None = None) -> str | None:
    """Find a helper program: an explicit setting first, then the PATH, then the usual Linux location."""
    candidates = [os.environ.get(env_name)] if env_name else []
    for name in names:
        candidates.append(shutil.which(name))
        if beside:
            candidates.append(str(Path(beside).parent / name))
        candidates.append(f"/usr/lib/wine/{name}")
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


class Runner:
    def __init__(self, kind: str, bundle: Path, workspace: Path):
        self.kind = kind
        self.bundle = bundle
        self.workspace = workspace
        self.launches = 0
        # Start from a clean slate: none of our own settings leak in from the build machine.
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("IDENTIFYCOLLECTION_")}
        self.env["IDENTIFYCOLLECTION_NO_PAUSE"] = "1"  # nobody is here to "press any key"
        if kind == "wine":
            self.wine = find_program("wine64", "wine", env_name="WINE")
            expect(self.wine is not None, "--runner wine needs Wine (set WINE=/path/to/wine64 if it is not on the PATH)")
            self.wineserver = find_program("wineserver", beside=self.wine)
            self.env.setdefault("WINEDEBUG", "-all")
            self.env.setdefault("WINEPREFIX", str(workspace / "wineprefix"))
            self.env.setdefault("LC_ALL", "C.UTF-8")
        if kind == "host":
            # Uses the packages already installed for this computer's own Python
            # (pip install -r requirements.txt). The ones inside the bundle are
            # built for Windows and cannot be borrowed elsewhere.
            self.env.pop("PYTHONPATH", None)
            self.env["PYTHONDONTWRITEBYTECODE"] = "1"

    def command(self, arguments: list[str]):
        if self.kind == "windows":
            # What a double-click does: cmd.exe runs the batch file from its own folder.
            return f'cmd.exe /d /c "{BAT_NAME}" ' + " ".join(arguments)
        if self.kind == "wine":
            return [self.wine, "cmd", "/c", BAT_NAME, *arguments]
        return [sys.executable, "-X", "utf8", str(self.bundle / "app" / "launch.py"), *arguments]

    def start(self, *extra: str) -> tuple[subprocess.Popen, Path]:
        self.launches += 1
        log_path = self.workspace / f"launch-{self.launches}.log"
        process = subprocess.Popen(
            self.command(["--no-browser", *extra]),
            cwd=self.bundle,
            env=self.env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        # Copy whatever the launcher window would show into a file as it appears.
        # (Through a pipe rather than straight to the file: Windows programs
        # running under Wine cannot start with their output aimed at a file.)
        threading.Thread(target=_copy_output, args=(process.stdout, log_path), daemon=True).start()
        return process, log_path

    def stop(self, process: subprocess.Popen) -> None:
        if process.poll() is None:
            if self.kind == "windows":
                # /T: the whole family (cmd.exe and the python.exe it started). /F: now.
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            else:
                process.terminate()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=30)
        if self.kind == "wine":
            # End every Windows program still running in this test's Wine session.
            for flag in ("-k", "-w"):
                try:
                    subprocess.run([self.wineserver or "wineserver", flag], env=self.env, check=False, timeout=60)
                except (OSError, subprocess.TimeoutExpired):
                    pass


def read_log(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "(no output captured)"


def wait_until_running(bundle: Path, process: subprocess.Popen, log_path: Path) -> dict:
    """The launcher writes data/run.json once it is serving; wait for it, then for a healthy answer."""
    run_json = bundle / "data" / "run.json"
    deadline = time.monotonic() + START_TIMEOUT
    started = time.monotonic()
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise SmokeFailure(f"the launcher exited early with code {process.returncode}:\n{read_log(log_path)}")
        if run_json.is_file():
            try:
                info = json.loads(run_json.read_text(encoding="utf-8"))
                status, _url, body, _headers = Browser(info["url"]).request("healthz")
                if status == 200 and json.loads(body).get("instance") == info["instance"]:
                    info["seconds_to_start"] = round(time.monotonic() - started, 1)
                    return info
                if status >= 500:
                    app_log = read_log(bundle / "data" / "logs" / "identifycollection.log")
                    raise SmokeFailure(f"the app started but answers with an error ({status}). Its log ends:\n{app_log[-3000:]}")
            except (OSError, ValueError, KeyError):
                pass  # not ready yet
        time.sleep(0.25)
    raise SmokeFailure(f"the app did not start within {START_TIMEOUT} seconds:\n{read_log(log_path)}")


# ---------------------------------------------------------------------------
# The journey
# ---------------------------------------------------------------------------


def first_run_journey(base_url: str, expected_version: str) -> None:
    browser = Browser(base_url)

    status, _url, body, headers = browser.request("healthz")
    health = json.loads(body)
    expect(status == 200 and health["app"] == "identifycollection" and health["status"] == "ok", f"bad health answer: {health}")
    expect(health["version"] == expected_version, f"running version {health['version']} is not the zip's {expected_version}")
    expect("IdentifyCollection" in headers.get("Server", ""), f"unexpected web server: {headers.get('Server')}")
    note(f"health check answers; version {health['version']}")

    status, path, page = browser.get("")
    expect(status == 200 and path == "/setup/", f"a fresh copy should open on /setup/, got {status} at {path}")
    expect("Create the first staff account" in page, "the first-run page has the wrong content")
    expect(not EXTERNAL_LOAD.search(page), "the first-run page loads something from the internet")
    note("fresh copy opens on the first-run page")

    stylesheet = re.search(r'<link rel="stylesheet" href="([^"]+)"', page)
    expect(stylesheet is not None, "no stylesheet link on the page")
    status, _url, css, headers = browser.request(stylesheet.group(1))
    expect(status == 200 and "text/css" in headers.get("Content-Type", ""), f"stylesheet not served: {status}")
    expect(b"Besley" in css and b"--marking" in css, "the stylesheet is not ours")
    expect("max-age=" in headers.get("Cache-Control", ""), "fingerprinted static files should be cacheable")
    css_text = css.decode("utf-8")
    expect(not re.search(r"url\(\s*[\"']?\s*(?:https?:)?//", css_text), "the stylesheet loads something from the internet")
    font = re.search(r'url\("([^"]+\.woff2)"\)', css_text)
    expect(font is not None, "no font address in the stylesheet")
    font_url = urllib.parse.urljoin(urllib.parse.urljoin(base_url, stylesheet.group(1)), font.group(1))
    status, _url, font_bytes, _headers = browser.request(font_url)
    expect(status == 200 and font_bytes[:4] == b"wOF2", f"font not served correctly ({status})")
    note("stylesheet and font are served from the bundle itself")

    status, path, page = browser.post(
        "setup/", {"username": USERNAME, "password1": PASSWORD, "password2": PASSWORD}, page
    )
    expect(status == 200 and path == "/staff/", f"creating the first account should land on the staff home page, got {status} at {path}")
    expect(f"Signed in as {USERNAME}" in page, "the home page does not show who is signed in")
    expect("portable build" in page, "the home page should say this is the portable build")
    expect(not EXTERNAL_LOAD.search(page), "the home page loads something from the internet")
    note("first staff account created and signed in")

    status, path, page = browser.post("logout/", {}, page)
    expect(status == 200 and path == "/login/", f"signing out should land on the sign-in page, got {status} at {path}")
    note("signed out")

    status, path, _page = browser.get("setup/")
    expect(path == "/login/", f"first-run setup must be closed once an account exists, but /setup/ led to {path}")
    note("first-run setup is closed now that an account exists")

    status, path, wrong = browser.post("login/", {"username": USERNAME, "password": "not the password"}, page)
    expect(status == 200 and path == "/login/" and "do not match an account here" in wrong, "a wrong password was not refused properly")
    status, path, home = browser.post("login/", {"username": USERNAME, "password": PASSWORD}, wrong)
    expect(status == 200 and path == "/staff/" and f"Signed in as {USERNAME}" in home, f"signing in failed: {status} at {path}")
    note("wrong password refused; right password signs in")

    status, _path, missing = browser.get("no-such-page/")
    expect(status == 404 and "There is no page at this address" in missing, "the 'page not found' page is not ours")
    note("unknown addresses get the plain 'not found' page")

    collection_journey(browser, base_url)


def practice_scan(width: int = 900, height: int = 600) -> bytes:
    """A small greyscale PNG picture, built by hand so this test needs nothing but Python itself."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    rows = b"".join(b"\x00" + bytes((x * 200 // width + y // 8) % 256 for x in range(width)) for y in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def collection_journey(staff: Browser, base_url: str) -> None:
    """The whole point of the project, end to end: scan in, answer in, decision made, export out."""
    visitor = Browser(base_url)  # a second browser with no sign-in, as a member of the public

    _status, _path, photos_page = staff.get("staff/photos/")
    status, _path, body = staff.post_files(
        "staff/photos/upload/", {}, {"file": ("1987.12.4.png", practice_scan(), "image/png")}, photos_page,
        headers={"X-Requested-With": "fetch"},
    )  # fmt: skip
    expect(status == 200, f"adding a photograph failed with status {status}: {body[:300]!r}")
    result = json.loads(body)["results"][0]
    expect(result["ok"], f"the practice scan was refused: {result}")
    photo = result["id"]
    note("a scan was added and turned into browser pictures")

    status, _path, private = visitor.get(f"photo/{photo}/")
    expect(status == 404, f"a photograph must be hidden from visitors until staff put it on show (got {status})")
    status, path, _page = staff.post("staff/photos/", {"action": "publish", "photo": photo}, photos_page)
    expect(status == 200 and path == "/staff/photos/", f"putting the photograph on show failed: {status} at {path}")

    status, _path, wall = visitor.get("")
    expect(status == 200 and f"/photo/{photo}/" in wall, "the photograph is not on the public gallery after being put on show")
    status, _url, picture, headers = visitor.request(f"media/web/{photo}.jpg")
    expect(status == 200 and picture[:2] == b"\xff\xd8", "the zoomable picture is not a JPEG made from the scan")
    status, _url, thumb, _headers = visitor.request(f"media/thumb/{photo}.jpg")
    expect(status == 200 and thumb[:2] == b"\xff\xd8", "the gallery thumbnail was not made")
    note("hidden until put on show; then on the public gallery with its pictures")

    status, _path, page = visitor.get(f"photo/{photo}/")
    expect(status == 200 and "Tell the museum who you recognize" in page, "the photograph page has no answer form")
    expect(not EXTERNAL_LOAD.search(page), "the photograph page loads something from the internet")
    for script in re.findall(r'<script src="([^"]+)"', page):
        status, _url, code, _headers = visitor.request(script)
        expect(status == 200 and len(code) > 200, f"a script the page needs was not served: {script}")
    expect("openseadragon" in page, "the zooming viewer is missing from the photograph page")

    status, path, thanks = visitor.post(
        f"photo/{photo}/",
        {
            "person_name": "Edith Marlow", "confidence": "certain",
            "box_x": "0.25", "box_y": "0.2", "box_w": "0.1", "box_h": "0.2",
            "evidence_kind": "testimony", "evidence_text": "She was my grandmother.", "consent": "on",
        },
        page,
    )  # fmt: skip
    expect(status == 200 and path.startswith("/thanks/IC-"), f"sending an answer failed: {status} at {path}")
    reference = path.strip("/").split("/")[-1]
    _status, _path, page = visitor.get(f"photo/{photo}/")
    expect("Edith Marlow" not in page, "an answer became public before any member of staff reviewed it")
    note(f"a visitor identified someone with evidence, without an account ({reference})")

    status, _path, review = staff.get(f"staff/review/{reference}/")
    expect(status == 200 and "She was my grandmother." in review, "staff cannot see the answer and its evidence")
    status, path, _page = staff.post(f"staff/review/{reference}/", {"action": "accept", "note": "smoke test"}, review)
    expect(status == 200 and path == "/staff/review/", f"accepting failed: {status} at {path}")
    _status, _path, page = visitor.get(f"photo/{photo}/")
    expect("Edith Marlow" in page, "an accepted name does not show on the public photograph page")
    note("staff accepted it; the name now shows publicly")

    status, _url, export, headers = staff.request("staff/export/identifications.csv")
    text = export.decode("utf-8")
    expect(status == 200 and "attachment" in headers.get("Content-Disposition", ""), "the export did not arrive as a file")
    expect("Edith Marlow" in text and "1987.12.4.png" in text and "xywh=pixel:225,120,90,120" in text, f"the export is incomplete:\n{text}")
    status, _url, _body, _headers = visitor.request("staff/export/identifications.csv")
    expect("/login/" in _url, "the export must not be open to visitors")
    note("the export file holds the identification, with the marked area in pixels")


def returning_journey(base_url: str) -> None:
    browser = Browser(base_url)
    status, path, page = browser.get("staff/")
    expect(status == 200 and path == "/login/", f"after a restart the staff pages should ask to sign in, got {status} at {path}")
    status, path, home = browser.post("login/", {"username": USERNAME, "password": PASSWORD}, page)
    expect(status == 200 and path == "/staff/" and f"Signed in as {USERNAME}" in home, "the account did not survive a restart")
    _status, _path, wall = Browser(base_url).get("")
    link = re.search(r'href="(/photo/\d+/)"', wall)
    expect(link is not None, "the photograph did not survive a restart")
    _status, _path, page = Browser(base_url).get(link.group(1).lstrip("/"))
    expect("Edith Marlow" in page, "the accepted identification did not survive a restart")
    note("after a restart the account, the photograph and the identification are still there")


def run(zip_path: Path, kind: str, keep: bool) -> None:
    expect(zip_path.is_file(), f"no such zip: {zip_path}")
    awkward = "IC smoke (test) & co é"
    workspace = Path(tempfile.mkdtemp(prefix="ic-smoke-"))
    runner = None
    first = second = None
    try:
        extract_to = workspace / awkward
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract_to)
        tops = [path for path in extract_to.iterdir()]
        expect(len(tops) == 1 and tops[0].is_dir(), "the zip should contain exactly one top-level folder")
        bundle = tops[0]
        version = (bundle / "app" / "VERSION").read_text(encoding="utf-8").strip()
        expect(bundle.name == f"IdentifyCollection-{version}", f"unexpected folder name in zip: {bundle.name}")
        expect(not (bundle / "data").exists(), "a fresh zip must not contain a data folder")
        print(f"Smoke-testing IdentifyCollection {version} ({kind}) in:\n  {bundle}", flush=True)

        runner = Runner(kind, bundle, workspace)

        # --- first start ---------------------------------------------------
        first, first_log = runner.start()
        info = wait_until_running(bundle, first, first_log)
        note(f"started in {info['seconds_to_start']} s at {info['url']}")
        expect(info["url"].startswith("http://127.0.0.1:"), f"must listen on this computer only, not {info['url']}")
        if kind != "host":
            python_used = info["python"].replace("\\", "/").lower()
            expect(
                python_used.endswith(f"{bundle.name.lower()}/runtime/python.exe"),
                f"the app is not running on the bundled Python but on: {info['python']}",
            )
            note("running on the Python inside the bundle")

        first_run_journey(info["url"], version)

        data = bundle / "data"
        for name in ("db.sqlite3", "secret_key.txt", "run.lock", "logs/identifycollection.log"):
            expect((data / name).is_file(), f"expected data/{name} to exist")
        log_text = (data / "logs" / "identifycollection.log").read_text(encoding="utf-8", errors="replace")
        expect("Serving on" in log_text, "the log file does not record the start-up")
        expect("Traceback" not in log_text, f"the log file records an error:\n{log_text}")
        expect(not (data / "backups").exists(), "a first start has nothing to back up, yet a backup was made")
        expect(any((data / "media" / "web").rglob("*.jpg")), "the pictures are not kept inside the data folder")
        expect(not any((data / "tmp").glob("*")), "upload scratch files were left behind in data/tmp")
        note("database, pictures, secret key and log file are inside the bundle's data folder")

        # --- a second double-click while it is running ----------------------
        second, second_log = runner.start()
        try:
            code = second.wait(timeout=150)
        except subprocess.TimeoutExpired:
            raise SmokeFailure(f"a second start did not step aside:\n{read_log(second_log)}") from None
        expect(code == 0, f"a second start should exit quietly (0), not {code}:\n{read_log(second_log)}")
        expect("Already running at" in read_log(second_log), f"a second start did not recognise the first:\n{read_log(second_log)}")
        status, _url, _body, _headers = Browser(info["url"]).request("healthz")
        expect(status == 200, "the first copy stopped answering after a second start")
        note("a second double-click steps aside and leaves the first copy running")

        # --- stop, start again ---------------------------------------------
        runner.stop(first)
        time.sleep(1)
        first, first_log = runner.start()
        again = wait_until_running(bundle, first, first_log)
        expect(again["instance"] != info["instance"], "the restarted copy should be a new instance")
        note(f"stopped, then started again in {again['seconds_to_start']} s")
        returning_journey(again["url"])
        expect(not (data / "backups").exists(), "an ordinary restart must not touch the database layout")

        print("\nSMOKE TEST PASSED", flush=True)
    finally:
        if runner:
            for process in (second, first):
                if process is not None:
                    runner.stop(process)
        if keep:
            print(f"(kept for inspection: {workspace})")
        else:
            shutil.rmtree(workspace, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Start a built IdentifyCollection zip and check that it works.")
    parser.add_argument("zip", type=Path, help="the zip produced by build_portable.py")
    parser.add_argument(
        "--runner",
        choices=["auto", "windows", "wine", "host"],
        default="auto",
        help="how to start the bundle (default: windows on Windows, otherwise host)",
    )
    parser.add_argument("--keep", action="store_true", help="keep the extracted folder afterwards, for inspection")
    args = parser.parse_args()
    kind = args.runner
    if kind == "auto":
        kind = "windows" if os.name == "nt" else "host"
    if kind == "windows" and os.name != "nt":
        parser.error("--runner windows only works on Windows; use wine or host here")
    try:
        run(args.zip.resolve(), kind, args.keep)
    except SmokeFailure as failure:
        print(f"\nSMOKE TEST FAILED: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
