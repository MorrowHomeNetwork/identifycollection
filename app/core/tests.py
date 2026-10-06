"""
Automated tests for the home page, the health check and the error page.
"""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import path, reverse

User = get_user_model()


def _deliberately_broken_page(request):
    raise RuntimeError("deliberate failure for the error-page test")


# A stand-in address book used only by ServerErrorPageTests below.
urlpatterns = [path("broken/", _deliberately_broken_page)]


class HealthCheckTests(TestCase):
    def test_answers_without_signing_in(self):
        response = self.client.get(reverse("healthz"))
        self.assertEqual(response.status_code, 200)
        answer = response.json()
        self.assertEqual(answer["app"], "identifycollection")
        self.assertEqual(answer["status"], "ok")
        self.assertEqual(answer["version"], settings.VERSION)
        self.assertIn("instance", answer)

    def test_is_never_cached_by_the_browser(self):
        response = self.client.get(reverse("healthz"))
        self.assertIn("no-cache", response["Cache-Control"])

    def test_only_answers_plain_reads(self):
        with self.assertLogs("django.request", level="WARNING"):
            response = self.client.post(reverse("healthz"))
        self.assertEqual(response.status_code, 405)


class HomePageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("registrar", password="lantern-slide-archive-1908")

    def test_requires_signing_in(self):
        response = self.client.get(reverse("home"))
        self.assertRedirects(response, "/login/?next=/")

    def test_shows_the_version_and_where_the_data_is(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, settings.VERSION)
        self.assertContains(response, "Where your data is kept")
        self.assertContains(response, "Get the source code")


class ErrorPageTests(TestCase):
    def test_unknown_address_gets_our_own_plain_page(self):
        with self.assertLogs("django.request", level="WARNING"):
            response = self.client.get("/no-such-page/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "There is no page at this address", status_code=404)


@override_settings(ROOT_URLCONF=__name__)
class ServerErrorPageTests(TestCase):
    def test_a_crash_shows_a_plain_page_and_no_technical_details(self):
        client = Client(raise_request_exception=False)
        with self.assertLogs("django.request", level="ERROR"):
            response = client.get("/broken/")
        self.assertEqual(response.status_code, 500)
        self.assertContains(response, "hit a problem", status_code=500)
        self.assertContains(response, "identifycollection.log", status_code=500)
        self.assertNotContains(response, "deliberate failure", status_code=500)
        self.assertNotContains(response, "Traceback", status_code=500)


class DataInspectorTests(TestCase):
    """Django's built-in admin screens, kept as a behind-the-scenes inspection tool."""

    def test_open_to_the_first_account(self):
        admin = User.objects.create_superuser("registrar", password="lantern-slide-archive-1908")
        self.client.force_login(admin)
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)

    def test_closed_to_everyone_else(self):
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])


class AddressTests(TestCase):
    """Which addresses the app agrees to answer on."""

    def test_an_address_nobody_listed_is_refused(self):
        with self.assertLogs("django.security.DisallowedHost", level="ERROR"):
            response = self.client.get("/healthz", HTTP_HOST="192.168.1.20:8000")
        self.assertEqual(response.status_code, 400)

    def test_a_listed_address_is_answered(self):
        with self.settings(ALLOWED_HOSTS=[*settings.ALLOWED_HOSTS, "192.168.1.20"]):
            response = self.client.get("/healthz", HTTP_HOST="192.168.1.20:8000")
        self.assertEqual(response.status_code, 200)

    def test_extra_addresses_are_read_from_a_comma_separated_list(self):
        from config.settings import _extra_hosts

        self.assertEqual(_extra_hosts(""), [])
        self.assertEqual(_extra_hosts(" 192.168.1.20 , museum.example,, "), ["192.168.1.20", "museum.example"])

    def test_answering_to_every_address_is_not_allowed(self):
        from config.settings import _extra_hosts

        for value in ("*", "192.168.1.20,*", "*.example"):
            with self.subTest(value=value), self.assertRaises(ImproperlyConfigured):
                _extra_hosts(value)
