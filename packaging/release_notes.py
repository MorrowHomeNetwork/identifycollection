#!/usr/bin/env python3
"""
release_notes.py: prints the text that describes one version on its GitHub
Release page.

    python packaging/release_notes.py 0.0.1
    python packaging/release_notes.py 0.0.1 --checksums dist/SHA256SUMS.txt

The text is the section of CHANGELOG.md for that version, followed by how to
start the download and, if given, its checksum. The automated release uses
this, so a release can never be published with notes that differ from the
changelog. Exits with an error if the changelog has no entry for the version.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent


def changelog_section(changelog: str, version: str) -> str | None:
    """Everything under the '## [version]' heading, up to the next '## ' heading."""
    lines = changelog.splitlines()
    heading = re.compile(rf"^## \[?{re.escape(version)}\]?(\s|$)")
    start = next((index for index, line in enumerate(lines) if heading.match(line)), None)
    if start is None:
        return None
    end = next((index for index in range(start + 1, len(lines)) if lines[index].startswith("## ")), len(lines))
    return "\n".join(lines[start + 1 : end]).strip()


def build_notes(version: str, checksums: Path | None) -> str:
    section = changelog_section((REPO_DIR / "CHANGELOG.md").read_text(encoding="utf-8"), version)
    if not section:
        raise SystemExit(f"CHANGELOG.md has no entry (or an empty one) for version {version}.")
    zip_name = f"IdentifyCollection-{version}-windows-x64.zip"
    parts = [
        section,
        "## To try it",
        f"1. Download **{zip_name}** below.\n"
        "2. Right-click it, choose **Extract All...**, and open the folder that creates.\n"
        "3. Double-click **Start IdentifyCollection**.\n\n"
        "Nothing is installed and no internet connection is needed. "
        "`READ ME FIRST.txt` in the folder explains what to do if Windows shows a warning.",
    ]
    if checksums:
        wanted = [line for line in checksums.read_text(encoding="utf-8").splitlines() if line.strip().endswith(zip_name)]
        if not wanted:
            raise SystemExit(f"{checksums} has no checksum for {zip_name}.")
        parts.append(
            "## Checking the download (optional)\n"
            "The SHA-256 checksum of the zip is:\n\n"
            f"```\n{wanted[0].strip()}\n```\n\n"
            f"In PowerShell, `Get-FileHash {zip_name}` should print the same value."
        )
    return "\n\n".join(parts) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Print the GitHub Release notes for one version.")
    parser.add_argument("version", help="for example 0.0.1 (a leading 'v' is ignored)")
    parser.add_argument("--checksums", type=Path, help="path to SHA256SUMS.txt from the build")
    args = parser.parse_args()
    sys.stdout.write(build_notes(args.version.removeprefix("v"), args.checksums))
    return 0


if __name__ == "__main__":
    sys.exit(main())
