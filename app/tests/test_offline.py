"""
The no-internet guard.

IdentifyCollection must work on a museum laptop with no internet connection,
and must never quietly fetch a font, a script or an image from someone else's
server (a "CDN"). These tests fail the moment a page or stylesheet starts
depending on anything outside this repository.

Ordinary links that a person may choose to click, such as the link to the
source code, are fine: they load nothing by themselves.
"""

import re
from html.parser import HTMLParser

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

# Places where our own interface files live.
OUR_FOLDERS = [settings.BASE_DIR / "templates", settings.BASE_DIR / "static"]
TEXT_TYPES = {".html", ".css", ".js", ".mjs", ".svg", ".txt", ".json", ".xml"}
# Licence texts legitimately mention web addresses; they are not loaded by pages.
EXEMPT_NAMES = {"OFL.txt", "LICENSE.txt", "LICENSE"}

# Libraries written by others and stored here. Their compressed code contains
# web addresses in comments and strings, which would trip the line-by-line
# check below without loading anything.
VENDOR_DIR = settings.BASE_DIR / "static" / "vendor"

# Anything that makes a browser FETCH from another server.
EXTERNAL_LOAD = re.compile(
    r"""
    (?:\b(?:src|srcset|poster|data|action|formaction|background|manifest|ping)\s*=\s*["']?\s*(?:https?:)?//)
    | (?:<link\b[^>]*\bhref\s*=\s*["']?\s*(?:https?:)?//)
    | (?:<(?:use|image|script)\b[^>]*\b(?:xlink:)?href\s*=\s*["']?\s*(?:https?:)?//)
    | (?:url\(\s*["']?\s*(?:https?:)?//)
    | (?:@import\s+["']\s*(?:https?:)?//)
    | (?:\bimport\s*\(?\s*["'](?:https?:)?//)
    | (?:\bfetch\s*\(\s*["'](?:https?:)?//)
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Tags whose address attributes are fetched automatically when a page opens.
AUTO_LOADING = {
    "link": ("href",),
    "script": ("src",),
    "img": ("src", "srcset"),
    "source": ("src", "srcset"),
    "video": ("src", "poster"),
    "audio": ("src",),
    "iframe": ("src",),
    "embed": ("src",),
    "object": ("data",),
    "use": ("href", "xlink:href"),
    "image": ("href", "xlink:href"),
    "form": ("action",),
}


def is_external(address: str) -> bool:
    address = (address or "").strip().lower()
    return address.startswith(("http:", "https:", "//"))


class _AutoLoadCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.found: list[tuple[str, str, str]] = []

    def handle_starttag(self, tag, attrs):
        wanted = AUTO_LOADING.get(tag)
        if not wanted:
            return
        for name, value in attrs:
            if name in wanted and value:
                self.found.append((tag, name, value))


class SourceFilesStayLocalTests(TestCase):
    def test_no_template_or_static_file_loads_anything_from_the_internet(self):
        offenders = []
        checked = 0
        for folder in OUR_FOLDERS:
            for path in sorted(folder.rglob("*")):
                if not path.is_file() or path.suffix.lower() not in TEXT_TYPES or path.name in EXEMPT_NAMES:
                    continue
                if VENDOR_DIR in path.parents:
                    continue  # other people's libraries, checked by hand when added (see VendoredLibraryTests)
                checked += 1
                text = path.read_text(encoding="utf-8")
                for number, line in enumerate(text.splitlines(), start=1):
                    if EXTERNAL_LOAD.search(line):
                        offenders.append(f"{path.relative_to(settings.BASE_DIR)}:{number}: {line.strip()[:120]}")
        self.assertGreater(checked, 5, "the guard found almost nothing to check; has the folder layout changed?")
        self.assertEqual(offenders, [], "These lines load something from another server:\n" + "\n".join(offenders))

    def test_the_guard_itself_recognises_the_usual_culprits(self):
        culprits = [
            '<script src="https://cdn.example.com/lib.js"></script>',
            "<link rel=stylesheet href=//fonts.example.com/css>",
            '<img src="http://example.com/a.png">',
            "@import 'https://example.com/a.css';",
            "src: url(https://example.com/font.woff2)",
            'background: url( "//example.com/a.png" )',
            '<use xlink:href="https://example.com/sprite.svg#a"/>',
            'import("https://example.com/mod.js")',
        ]
        for line in culprits:
            with self.subTest(line=line):
                self.assertRegex(line, EXTERNAL_LOAD)

        innocent = [
            '<a href="https://github.com/MorrowHomeNetwork/identifycollection">source</a>',
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 36 36">',
            'src: url("../fonts/besley/besley-latin-wght-normal.woff2") format("woff2");',
            '<link rel="stylesheet" href="/static/css/site.css">',
        ]
        for line in innocent:
            with self.subTest(line=line):
                self.assertNotRegex(line, EXTERNAL_LOAD)


class RenderedPagesStayLocalTests(TestCase):
    """Checks the finished pages as a browser would receive them."""

    def _assert_page_is_self_contained(self, response):
        self.assertEqual(response.status_code, 200)
        collector = _AutoLoadCollector()
        collector.feed(response.content.decode())
        self.assertTrue(collector.found, "expected the page to load at least its stylesheet")
        external = [item for item in collector.found if is_external(item[2])]
        self.assertEqual(external, [], f"page loads from another server: {external}")

    def test_first_run_page(self):
        self._assert_page_is_self_contained(self.client.get(reverse("setup")))

    def test_sign_in_page(self):
        get_user_model().objects.create_user("registrar", password="lantern-slide-archive-1908")
        self._assert_page_is_self_contained(self.client.get(reverse("login")))

    def test_staff_pages(self):
        user = get_user_model().objects.create_user("registrar", password="lantern-slide-archive-1908", is_staff=True)
        self.client.force_login(user)
        for name in ("home", "photos", "queue", "export"):
            with self.subTest(page=name):
                self._assert_page_is_self_contained(self.client.get(reverse(name)))

    def test_gallery(self):
        get_user_model().objects.create_user("registrar", password="lantern-slide-archive-1908")
        self._assert_page_is_self_contained(self.client.get(reverse("gallery")))

    def test_data_inspector_sign_in_page(self):
        self._assert_page_is_self_contained(self.client.get("/admin/login/"))


class FontsAreInTheRepositoryTests(TestCase):
    def test_every_font_the_stylesheet_names_exists_and_carries_its_licence(self):
        stylesheet = settings.BASE_DIR / "static" / "css" / "site.css"
        addresses = re.findall(r"""url\(\s*["']?([^"')]+)["']?\s*\)""", stylesheet.read_text(encoding="utf-8"))
        fonts = [address for address in addresses if address.endswith(".woff2")]
        self.assertGreaterEqual(len(fonts), 2)
        for address in fonts:
            with self.subTest(font=address):
                path = (stylesheet.parent / address).resolve()
                self.assertTrue(path.is_file(), f"missing font file: {path}")
                self.assertTrue((path.parent / "OFL.txt").is_file(), f"font licence missing next to {path.name}")


class VendoredLibraryTests(TestCase):
    def test_every_library_stored_here_carries_its_licence(self):
        libraries = [folder for folder in VENDOR_DIR.iterdir() if folder.is_dir()]
        self.assertTrue(libraries)
        for folder in libraries:
            with self.subTest(library=folder.name):
                self.assertTrue(any(folder.glob("LICENSE*")), f"no licence file in static/vendor/{folder.name}")
