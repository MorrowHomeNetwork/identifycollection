#!/usr/bin/env python3
"""
build_portable.py: assembles the portable Windows zip.

Run from anywhere:

    python packaging/build_portable.py

It produces, in the dist/ folder:

    IdentifyCollection-<version>-windows-x64.zip   the thing a museum downloads
    SHA256SUMS.txt                                 its checksum, for verifying a download

What goes into the zip:

    IdentifyCollection-<version>/
        Start IdentifyCollection.bat    the double-click
        READ ME FIRST.txt
        LICENSE.txt
        THIRD-PARTY-NOTICES.txt
        runtime/    a complete Python for Windows, with the packages from
                    requirements.txt installed into it
        app/        this project's own code, with its static files collected

This script runs on Windows, Linux or macOS: it never runs the Windows Python
it is packing, it only arranges files. It uses nothing outside Python's
standard library, plus "pip" to download the pinned packages.

The build machine needs Python 3.12 or newer, pip, and (for this step only)
an internet connection. The finished zip needs neither Python nor internet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
APP_DIR = REPO_DIR / "app"
PACKAGING_DIR = REPO_DIR / "packaging"
CACHE_DIR = REPO_DIR / ".cache"
BUILD_DIR = REPO_DIR / "build"

# Windows refuses paths longer than about 260 characters, and its built-in
# "Extract All" simply fails on them. The zip is usually extracted somewhere
# like C:\Users\<name>\Downloads\<zip name>\ (about 60 to 80 characters), so
# everything inside the zip must stay comfortably shorter than the difference.
LONGEST_PATH_ALLOWED = 170

# Parts of the Python runtime a museum's copy never uses: the tools for
# compiling C extensions, the Tk desktop-window toolkit, the IDLE editor, and
# pip itself (packages are installed here, at build time, not on the laptop).
RUNTIME_FOLDERS_TO_REMOVE = [
    "include",
    "libs",
    "Scripts",
    "tcl",
    "Lib/tkinter",
    "Lib/idlelib",
    "Lib/turtledemo",
    "Lib/ensurepip",
    "Lib/venv",
]
RUNTIME_FILES_TO_REMOVE = [
    "Lib/turtle.py",
    "DLLs/_tkinter.pyd",
    "DLLs/tcl90.dll",
    "DLLs/tcl9tk90.dll",
    "DLLs/libtommath.dll",
    "DLLs/_ctypes_test.pyd",
]
RUNTIME_GLOBS_TO_REMOVE = [
    "DLLs/_test*.pyd",
    "Lib/site-packages/pip",
    "Lib/site-packages/pip-*.dist-info",
]

# Things in app/ that are for developers, not for the shipped copy.
APP_NAMES_TO_SKIP = {"__pycache__", "tests", "tests.py", "staticfiles", "build_info.json"}

# The files that must exist in a healthy bundle. If any is missing the build
# stops, rather than shipping something that fails on a museum's laptop.
MUST_EXIST = [
    "Start IdentifyCollection.bat",
    "READ ME FIRST.txt",
    "LICENSE.txt",
    "THIRD-PARTY-NOTICES.txt",
    "runtime/python.exe",
    "runtime/LICENSE.txt",
    "runtime/LICENSES-incorporated-software.txt",
    "runtime/vcruntime140.dll",
    "runtime/DLLs/_sqlite3.pyd",
    "runtime/DLLs/sqlite3.dll",
    "runtime/Lib/os.py",
    "runtime/Lib/site-packages/django/__init__.py",
    "runtime/Lib/site-packages/waitress/__init__.py",
    "runtime/Lib/site-packages/whitenoise/__init__.py",
    "runtime/Lib/site-packages/tzdata/zoneinfo/UTC",
    "runtime/Lib/site-packages/PIL/__init__.py",
    "app/static/vendor/openseadragon/LICENSE.txt",
    "app/launch.py",
    "app/VERSION",
    "app/config/settings.py",
    "app/staticfiles/staticfiles.json",
    "app/build_info.json",
]


class BuildError(Exception):
    pass


def step(message: str) -> None:
    print(f"==> {message}", flush=True)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


# ---------------------------------------------------------------------------
# The Python runtime
# ---------------------------------------------------------------------------


def fetch_runtime(pin: dict, local_copy: Path | None) -> Path:
    """Return the path of the runtime archive, downloading it if needed. Always checksum-verified."""
    if local_copy:
        archive = local_copy
        if not archive.is_file():
            raise BuildError(f"--runtime-archive: no such file: {archive}")
    else:
        CACHE_DIR.mkdir(exist_ok=True)
        archive = CACHE_DIR / pin["filename"]
        if archive.is_file() and sha256_of(archive) != pin["sha256"]:
            archive.unlink()  # a damaged or outdated download: fetch it again
        if not archive.is_file():
            step(f"Downloading Python {pin['python_version']} for Windows")
            partial = archive.with_name(archive.name + ".part")
            with urllib.request.urlopen(pin["url"], timeout=120) as response, partial.open("wb") as out:
                shutil.copyfileobj(response, out)
            partial.replace(archive)

    actual = sha256_of(archive)
    if actual != pin["sha256"]:
        raise BuildError(
            "The Python runtime archive does not match its recorded checksum.\n"
            f"  file:     {archive}\n"
            f"  expected: {pin['sha256']}\n"
            f"  actual:   {actual}\n"
            "Refusing to build with it."
        )
    return archive


def unpack_runtime(archive: Path, runtime_dir: Path) -> None:
    """
    Unpack the archive's top-level "python" folder directly as "runtime".

    The files are written straight to their final place. Unpacking elsewhere
    and then renaming the folder is the obvious way, but on Windows a virus
    scanner inspecting the freshly written programs can make that rename fail.
    """
    with tarfile.open(archive) as tar:
        members = []
        for member in tar.getmembers():
            top, _, rest = member.name.partition("/")
            if top != "python" or not (member.isdir() or member.isreg()):
                raise BuildError(f"Unexpected entry in the runtime archive: {member.name!r}")
            member.name = f"{runtime_dir.name}/{rest}" if rest else runtime_dir.name
            members.append(member)
        tar.extractall(runtime_dir.parent, members=members, filter="data")  # "data": plain files and folders only
    if not (runtime_dir / "python.exe").is_file():
        raise BuildError("The runtime archive does not have the expected layout (python/python.exe).")


def prune_runtime(runtime_dir: Path) -> None:
    for name in RUNTIME_FOLDERS_TO_REMOVE + RUNTIME_FILES_TO_REMOVE:
        remove(runtime_dir / name)
    for pattern in RUNTIME_GLOBS_TO_REMOVE:
        for match in runtime_dir.glob(pattern):
            remove(match)


def isolate_runtime(runtime_dir: Path, pin: dict) -> None:
    """
    Tell the bundled Python to look for code ONLY inside this folder.

    A file named python<version>._pth next to python.exe lists the folders
    Python may import from. With it in place, Python ignores everything else
    on the computer: other Python installations, settings in the Windows
    registry, and environment variables. One museum's laptop cannot make this
    copy behave differently from another's.
    """
    major, minor = pin["python_version"].split(".")[:2]
    if not (runtime_dir / f"python{major}{minor}.dll").is_file():
        raise BuildError(f"python{major}{minor}.dll is missing from the runtime; is python-runtime.json consistent?")
    (runtime_dir / f"python{major}{minor}._pth").write_bytes(b"Lib\r\nDLLs\r\nLib\\site-packages\r\n")


def add_runtime_licences(runtime_dir: Path) -> None:
    """
    Several components built into Python require their licence notice to
    accompany every copy. The runtime's own LICENSE.txt does not carry all of
    them, so Python's official licence document goes in alongside it.
    (See packaging/licenses/README.md.)
    """
    shutil.copyfile(
        PACKAGING_DIR / "licenses" / "python-license.rst",
        runtime_dir / "LICENSES-incorporated-software.txt",
    )


def install_packages(site_packages: Path, pin: dict) -> None:
    """Install the pinned, checksum-verified packages for WINDOWS, whatever this build machine is."""
    target = pin["pip_target"]
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-input",
        "--quiet",
        "--no-deps",  # requirements.txt already lists everything, exactly
        "--require-hashes",  # refuse any file whose checksum is not in requirements.txt
        "--only-binary=:all:",  # ready-made packages only; never run a package's build code
        "--no-compile",
        "--platform",
        target["platform"],
        "--python-version",
        target["python_version"],
        "--implementation",
        target["implementation"],
        "--abi",
        target["abi"],
        "--target",
        str(site_packages),
        "-r",
        str(REPO_DIR / "requirements.txt"),
    ]
    subprocess.run(command, check=True)
    # pip also writes small command-line shortcuts; the bundle has no use for them.
    for leftover in ("bin", "Scripts"):
        remove(site_packages / leftover)


# ---------------------------------------------------------------------------
# The app
# ---------------------------------------------------------------------------


def copy_app(app_out: Path) -> None:
    def skip(_folder: str, names: list[str]) -> set[str]:
        return {name for name in names if name in APP_NAMES_TO_SKIP or name.endswith((".pyc", ".pyo"))}

    shutil.copytree(APP_DIR, app_out, ignore=skip)


def collect_static(app_out: Path, site_packages: Path) -> None:
    """
    Gather every CSS file, font and image into app/staticfiles, each renamed to
    include a fingerprint of its contents, plus a compressed copy. This is
    Django's "collectstatic" step. It runs on the build machine's own Python,
    but uses the Django that was just installed into the bundle.
    """
    with tempfile.TemporaryDirectory() as scratch_data:
        env = {
            **os.environ,
            "PYTHONPATH": str(site_packages),
            "PYTHONDONTWRITEBYTECODE": "1",
            "DJANGO_SETTINGS_MODULE": "config.settings",
            "IDENTIFYCOLLECTION_MODE": "portable",
            "IDENTIFYCOLLECTION_DATA_DIR": scratch_data,  # keep build-time scratch files out of the bundle
        }
        subprocess.run(
            [sys.executable, "-B", "manage.py", "collectstatic", "--noinput", "--verbosity", "0"],
            cwd=app_out,
            env=env,
            check=True,
        )


def git_output(*args: str) -> str | None:
    try:
        result = subprocess.run(["git", *args], cwd=REPO_DIR, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def build_time() -> int:
    """
    The moment stamped on every file in the zip. Taken from the commit being
    built, so that building the same commit twice gives the same zip.
    """
    if os.environ.get("SOURCE_DATE_EPOCH"):
        return int(os.environ["SOURCE_DATE_EPOCH"])
    commit_time = git_output("log", "-1", "--format=%ct")
    return int(commit_time) if commit_time else int(time.time())


def write_build_info(app_out: Path, version: str, pin: dict, stamp: int) -> None:
    info = {
        "version": version,
        "commit": git_output("rev-parse", "HEAD"),
        "uncommitted_changes": bool(git_output("status", "--porcelain")),
        "built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stamp)),
        "python_runtime": f"{pin['python_version']} ({pin['distribution'].split(' ')[0]} {pin['release']})",
        "built_on": f"{platform.system()} / Python {platform.python_version()}",
    }
    (app_out / "build_info.json").write_bytes((json.dumps(info, indent=2) + "\n").encode("utf-8"))


# ---------------------------------------------------------------------------
# The Windows-facing files
# ---------------------------------------------------------------------------


def windows_text(source: Path, version: str) -> bytes:
    """Plain ASCII with Windows line endings: what batch files and old Notepads need."""
    text = source.read_text(encoding="utf-8").replace("\r\n", "\n").replace("@VERSION@", version)
    if not text.isascii():
        raise BuildError(f"{source.name} must contain plain ASCII characters only.")
    return text.replace("\n", "\r\n").encode("ascii")


def add_top_level_files(stage: Path, version: str) -> None:
    for name in ("Start IdentifyCollection.bat", "READ ME FIRST.txt"):
        (stage / name).write_bytes(windows_text(PACKAGING_DIR / "windows" / name, version))
    shutil.copyfile(REPO_DIR / "LICENSE", stage / "LICENSE.txt")
    shutil.copyfile(REPO_DIR / "THIRD-PARTY-NOTICES.md", stage / "THIRD-PARTY-NOTICES.txt")


# ---------------------------------------------------------------------------
# Checks, then the zip
# ---------------------------------------------------------------------------


def check_bundle(stage: Path) -> tuple[int, str]:
    missing = [name for name in MUST_EXIST if not (stage / name).is_file()]
    if missing:
        raise BuildError("The bundle is incomplete. Missing:\n  " + "\n  ".join(missing))

    if (stage / "data").exists():
        raise BuildError("A data folder ended up inside the bundle; a museum's zip must start empty.")

    leftovers = [path for path in stage.rglob("*") if path.name == "__pycache__" or path.suffix in {".pyc", ".pyo"}]
    if leftovers:
        raise BuildError(f"Compiled Python leftovers in the bundle, for example: {leftovers[0]}")

    files = [path for path in stage.rglob("*") if path.is_file()]
    longest = max((f"{stage.name}/{path.relative_to(stage).as_posix()}" for path in files), key=len)
    if len(longest) > LONGEST_PATH_ALLOWED:
        raise BuildError(
            f"A path inside the zip is {len(longest)} characters long (limit {LONGEST_PATH_ALLOWED}); "
            f"Windows would fail to extract it:\n  {longest}"
        )
    return len(files), longest


def write_zip(stage: Path, zip_path: Path, stamp: int) -> None:
    """Write the zip with files in a fixed order and one fixed date, so builds are repeatable."""
    date_time = time.gmtime(max(stamp, 315532800))[:6]  # zip files cannot hold dates before 1980
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    remove(zip_path)
    files = sorted(path for path in stage.rglob("*") if path.is_file())
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            name = f"{stage.name}/{path.relative_to(stage).as_posix()}"
            entry = zipfile.ZipInfo(name, date_time=date_time)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.create_system = 3  # "made on Unix": lets the permissions below be recorded
            entry.external_attr = 0o100644 << 16  # an ordinary readable file, wherever it is extracted
            archive.writestr(entry, path.read_bytes(), compresslevel=9)
    with zipfile.ZipFile(zip_path) as archive:
        damaged = archive.testzip()
    if damaged:
        raise BuildError(f"The zip failed its own integrity check at: {damaged}")


def build(runtime_archive: Path | None, output_dir: Path) -> Path:
    if sys.version_info < (3, 12):
        raise BuildError(f"The build needs Python 3.12 or newer; this is {platform.python_version()}.")

    version = (APP_DIR / "VERSION").read_text(encoding="utf-8").strip()
    pin = json.loads((PACKAGING_DIR / "python-runtime.json").read_text(encoding="utf-8"))
    stage = BUILD_DIR / f"IdentifyCollection-{version}"
    runtime_dir = stage / "runtime"
    site_packages = runtime_dir / "Lib" / "site-packages"
    stamp = build_time()

    step(f"Building IdentifyCollection {version} for Windows (64-bit)")
    archive = fetch_runtime(pin, runtime_archive)

    remove(stage)
    stage.mkdir(parents=True)

    step(f"Unpacking Python {pin['python_version']} and removing the parts a museum never uses")
    unpack_runtime(archive, runtime_dir)
    prune_runtime(runtime_dir)
    isolate_runtime(runtime_dir, pin)
    add_runtime_licences(runtime_dir)

    step("Installing the pinned packages (checksums verified)")
    install_packages(site_packages, pin)

    step("Copying the app and collecting its static files")
    copy_app(stage / "app")
    collect_static(stage / "app", site_packages)
    write_build_info(stage / "app", version, pin, stamp)
    add_top_level_files(stage, version)

    # Python may have left compiled files behind while we worked; none may ship.
    for cache in list(stage.rglob("__pycache__")):
        remove(cache)

    step("Checking the bundle")
    file_count, longest = check_bundle(stage)

    zip_path = output_dir / f"IdentifyCollection-{version}-windows-x64.zip"
    step(f"Writing {zip_path.name}")
    write_zip(stage, zip_path, stamp)
    checksum = sha256_of(zip_path)
    # Written as exact bytes: a Windows-style line ending here would stop the
    # Linux "sha256sum --check" in the release job from finding the file.
    (output_dir / "SHA256SUMS.txt").write_bytes(f"{checksum}  {zip_path.name}\n".encode("ascii"))

    unpacked_mb = sum(path.stat().st_size for path in stage.rglob("*") if path.is_file()) / 1_000_000
    print()
    print(f"  zip:           {zip_path}")
    print(f"  size:          {zip_path.stat().st_size / 1_000_000:.1f} MB ({unpacked_mb:.0f} MB extracted, {file_count} files)")
    print(f"  sha256:        {checksum}")
    print(f"  longest path:  {len(longest)} characters")
    print()
    try:
        shown = os.path.relpath(zip_path, Path.cwd())
    except ValueError:  # Windows: the zip is on a different drive from the current folder
        shown = str(zip_path)
    print(f"  Next: python packaging/smoke_test.py {shown}")
    return zip_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the portable Windows zip of IdentifyCollection.")
    parser.add_argument(
        "--runtime-archive",
        type=Path,
        help="use this already-downloaded Python runtime archive instead of downloading it (checksum still verified)",
    )
    parser.add_argument("--output-dir", type=Path, default=REPO_DIR / "dist", help="where to put the zip (default: dist/)")
    args = parser.parse_args()
    try:
        build(args.runtime_archive, args.output_dir.resolve())
    except BuildError as exc:
        print(f"\nBUILD FAILED: {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"\nBUILD FAILED: a step exited with an error: {' '.join(map(str, exc.cmd[:4]))} ...", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
