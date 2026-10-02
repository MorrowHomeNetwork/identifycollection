"""
Automated tests for staff accounts: first-run setup, signing in, signing out.

A "test" is a small program that uses the app the way a person would and
checks that the right thing happens. Run them all with:

    python manage.py test
"""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

User = get_user_model()

GOOD_PASSWORD = "lantern-slide-archive-1908"


class FirstRunSetupTests(TestCase):
    """A brand-new installation has no accounts; the first visit creates one."""

    def test_fresh_install_leads_to_the_setup_page(self):
        response = self.client.get("/", follow=True)
        self.assertEqual(
            [url for url, _status in response.redirect_chain],
            ["/login/?next=/", "/setup/"],
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create the first staff account")

    def test_setup_creates_an_all_powerful_account_and_signs_it_in(self):
        response = self.client.post(
            reverse("setup"),
            {"username": "registrar", "password1": GOOD_PASSWORD, "password2": GOOD_PASSWORD},
        )
        self.assertRedirects(response, reverse("home"))

        user = User.objects.get()
        self.assertEqual(user.username, "registrar")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

        home = self.client.get(reverse("home"))
        self.assertEqual(home.status_code, 200)
        self.assertContains(home, "Signed in as registrar")

    def test_the_password_itself_is_never_stored(self):
        self.client.post(
            reverse("setup"),
            {"username": "registrar", "password1": GOOD_PASSWORD, "password2": GOOD_PASSWORD},
        )
        user = User.objects.get()
        self.assertNotIn(GOOD_PASSWORD, user.password)
        self.assertTrue(user.check_password(GOOD_PASSWORD))

    def test_mismatched_passwords_are_refused(self):
        response = self.client.post(
            reverse("setup"),
            {"username": "registrar", "password1": GOOD_PASSWORD, "password2": GOOD_PASSWORD + "x"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.exists())
        self.assertContains(response, "field-errors")

    def test_weak_passwords_are_refused(self):
        for weak in ("12345678", "password", "short"):
            with self.subTest(password=weak):
                response = self.client.post(
                    reverse("setup"),
                    {"username": "registrar", "password1": weak, "password2": weak},
                )
                self.assertEqual(response.status_code, 200)
                self.assertFalse(User.objects.exists())

    def test_setup_closes_for_good_once_an_account_exists(self):
        User.objects.create_user("registrar", password=GOOD_PASSWORD)

        visit = self.client.get(reverse("setup"))
        self.assertRedirects(visit, reverse("login"))

        attempt = self.client.post(
            reverse("setup"),
            {"username": "intruder", "password1": GOOD_PASSWORD, "password2": GOOD_PASSWORD},
        )
        self.assertRedirects(attempt, reverse("login"))
        self.assertEqual(list(User.objects.values_list("username", flat=True)), ["registrar"])

    @override_settings(ALLOW_WEB_SETUP=False)
    def test_setup_can_be_switched_off_entirely(self):
        visit = self.client.get(reverse("setup"))
        self.assertRedirects(visit, reverse("login"))

        attempt = self.client.post(
            reverse("setup"),
            {"username": "intruder", "password1": GOOD_PASSWORD, "password2": GOOD_PASSWORD},
        )
        self.assertRedirects(attempt, reverse("login"))
        self.assertFalse(User.objects.exists())


class SignInTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("registrar", password=GOOD_PASSWORD)

    def test_sign_in_page_is_shown(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sign in")
        self.assertContains(response, "Visitors never need an account")

    def test_right_password_signs_in(self):
        response = self.client.post(reverse("login"), {"username": "registrar", "password": GOOD_PASSWORD})
        self.assertRedirects(response, reverse("home"))

    def test_wrong_password_is_refused_with_a_plain_message(self):
        response = self.client.post(reverse("login"), {"username": "registrar", "password": "not-it"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "do not match an account here")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_sign_in_returns_to_the_page_that_was_asked_for(self):
        response = self.client.post(
            reverse("login") + "?next=/admin/",
            {"username": "registrar", "password": GOOD_PASSWORD, "next": "/admin/"},
        )
        self.assertRedirects(response, "/admin/", fetch_redirect_response=False)

    def test_sign_in_never_forwards_to_another_website(self):
        response = self.client.post(
            reverse("login"),
            {"username": "registrar", "password": GOOD_PASSWORD, "next": "https://example.com/"},
        )
        self.assertRedirects(response, reverse("home"))

    def test_someone_already_signed_in_skips_the_sign_in_page(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("login"))
        self.assertRedirects(response, reverse("home"))

    def test_sign_out(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("login"))
        after = self.client.get(reverse("home"))
        self.assertRedirects(after, "/login/?next=/")

    def test_sign_out_cannot_be_triggered_by_a_mere_link(self):
        # Signing out must be a deliberate button press (a "POST"), so that a
        # link on some other web page cannot sign a member of staff out.
        self.client.force_login(self.user)
        with self.assertLogs("django.request", level="WARNING"):
            response = self.client.get(reverse("logout"))
        self.assertEqual(response.status_code, 405)
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)
