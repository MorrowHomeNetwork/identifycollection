"""
Housekeeping checks: the things that must be true for every release.
"""

import io
import re
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

REPO_DIR = settings.BASE_DIR.parent


class MigrationTests(TestCase):
    def test_every_change_to_the_database_layout_has_been_recorded(self):
        # If a model was edited without running "makemigrations", a museum's
        # database would not be upgraded to match. This fails in that case.
        output = io.StringIO()
        try:
            call_command("makemigrations", "--check", "--dry-run", stdout=output, stderr=output)
        except SystemExit:
            self.fail("Model changes are not recorded. Run: python manage.py makemigrations\n" + output.getvalue())


class VersionTests(SimpleTestCase):
    def test_version_looks_like_a_version(self):
        self.assertRegex(settings.VERSION, r"^\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?$")

    def test_changelog_has_an_entry_for_this_version(self):
        # The text of each GitHub Release is taken from CHANGELOG.md, so a
        # version without an entry would publish with empty release notes.
        changelog = (REPO_DIR / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertRegex(changelog, rf"(?m)^## \[?{re.escape(settings.VERSION)}\]?\b")


class DependencyTests(SimpleTestCase):
    def test_every_dependency_is_pinned_to_an_exact_version_with_a_checksum(self):
        text = (REPO_DIR / "requirements.txt").read_text(encoding="utf-8")
        logical_lines = text.replace("\\\n", " ").splitlines()
        requirements = [line.strip() for line in logical_lines if line.strip() and not line.lstrip().startswith("#")]
        self.assertTrue(requirements)
        for requirement in requirements:
            with self.subTest(requirement=requirement.split()[0]):
                self.assertRegex(requirement, r"^[A-Za-z0-9_.\-]+==[0-9][^\s]*\s")
                self.assertIn("--hash=sha256:", requirement)


class WindowsFilesTests(SimpleTestCase):
    """Files that are opened by Windows itself must stay plain."""

    def _windows_files(self) -> list[Path]:
        files = sorted((REPO_DIR / "packaging" / "windows").iterdir())
        self.assertTrue(any(path.suffix == ".bat" for path in files))
        return files

    def test_windows_files_are_plain_ascii(self):
        # Batch files and Notepad on older Windows mis-read anything fancier.
        for path in self._windows_files():
            with self.subTest(file=path.name):
                try:
                    path.read_bytes().decode("ascii")
                except UnicodeDecodeError as exc:
                    self.fail(f"{path.name} contains a non-ASCII character at byte {exc.start}")

    def test_launcher_text_is_plain_ascii(self):
        (settings.BASE_DIR / "launch.py").read_bytes().decode("ascii")
