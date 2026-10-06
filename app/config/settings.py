"""
Settings for IdentifyCollection.

"Settings" is Django's name for the single file that configures the whole
application: where the database lives, which features are switched on, how
passwords are checked, and so on. Django reads this file once at start-up.

IdentifyCollection runs in one of two modes, chosen by the environment
variable IDENTIFYCOLLECTION_MODE:

    dev        The default. For working on the code: detailed error pages,
               started with "python manage.py runserver".
    portable   The double-click build a museum runs. Started by launch.py.
               Errors go to a log file instead of the screen.

A third mode for permanent server installs (PostgreSQL database, a real web
address) arrives with phase 3. The rule until then: one museum, one folder.
"""

from __future__ import annotations

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.core.management.utils import get_random_secret_key

# ---------------------------------------------------------------------------
# Where things are
# ---------------------------------------------------------------------------

# The app/ folder: this file is app/config/settings.py, so go up two levels.
BASE_DIR = Path(__file__).resolve().parent.parent

VERSION = (BASE_DIR / "VERSION").read_text(encoding="utf-8").strip()

# The AGPL licence requires that anyone using the software over a network can
# get its source code, so every page links here.
SOURCE_URL = "https://github.com/MorrowHomeNetwork/identifycollection"

MODE = os.environ.get("IDENTIFYCOLLECTION_MODE", "dev")
if MODE not in {"dev", "portable"}:
    raise ImproperlyConfigured(
        f"IDENTIFYCOLLECTION_MODE must be 'dev' or 'portable', not {MODE!r}."
    )
PORTABLE = MODE == "portable"

# Everything a museum creates lives in ONE folder, called "data", which sits
# next to the app/ folder. Back up that folder and you have backed up
# everything. Nothing a museum owns is ever stored inside app/.
DATA_DIR = Path(
    os.environ.get("IDENTIFYCOLLECTION_DATA_DIR") or BASE_DIR.parent / "data"
).resolve()
LOG_DIR = DATA_DIR / "logs"
for _folder in (DATA_DIR, LOG_DIR):
    _folder.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Security basics
# ---------------------------------------------------------------------------


def _load_or_create_secret_key(path: Path) -> str:
    """
    Django signs login sessions with a secret key. Each installation makes its
    own random key the first time it starts and keeps it in the data folder,
    so the key is never in the public source code and never shared between
    museums.
    """
    try:
        key = path.read_text(encoding="utf-8").strip()
        if key:
            return key
    except FileNotFoundError:
        pass
    key = get_random_secret_key()
    path.write_text(key + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)  # owner-only; has no effect on Windows, harmless there
    except OSError:
        pass
    return key


SECRET_KEY = _load_or_create_secret_key(DATA_DIR / "secret_key.txt")

# DEBUG shows detailed technical error pages. Useful while developing,
# never shown to a museum or its visitors.
DEBUG = MODE == "dev"



def _extra_hosts(value: str) -> list[str]:
    """Turn "192.168.1.20, museum.example" into a clean list of extra addresses."""
    hosts = [host.strip() for host in value.split(",") if host.strip()]
    if any("*" in host for host in hosts):
        raise ImproperlyConfigured(
            "IDENTIFYCOLLECTION_EXTRA_HOSTS must list exact names or addresses; '*' is not accepted."
        )
    return hosts


# Which addresses this copy answers to. Unless told otherwise: only the
# computer it runs on. A copy that other computers on the same network should
# reach (for example one running in a virtual machine) must be told the exact
# name or address people will type, separated by commas if there are several:
#
#     IDENTIFYCOLLECTION_EXTRA_HOSTS=192.168.1.20,museum.example
#
# Requests for any other address are refused. This stops another website from
# tricking a browser into talking to this app under a made-up name.
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "[::1]"]
ALLOWED_HOSTS += _extra_hosts(os.environ.get("IDENTIFYCOLLECTION_EXTRA_HOSTS", ""))

# The very first staff account is created in the browser ("first-run setup").
# The page only works while there are no accounts at all.
ALLOW_WEB_SETUP = True

# Cookies are how the browser remembers that someone is signed in. Browsers
# share cookies between everything on "127.0.0.1" regardless of port number,
# so distinct names stop IdentifyCollection and any other locally running
# Django project from signing each other out.
SESSION_COOKIE_NAME = "identifycollection_session"
CSRF_COOKIE_NAME = "identifycollection_csrf"


# ---------------------------------------------------------------------------
# What the application is made of
# ---------------------------------------------------------------------------

# An "app", in Django's vocabulary, is one self-contained part of the project.
INSTALLED_APPS = [
    "django.contrib.admin",  # Django's built-in data-inspection screens (/admin/)
    "django.contrib.auth",  # accounts, passwords, permissions
    "django.contrib.contenttypes",
    "django.contrib.sessions",  # remembering who is signed in
    "django.contrib.messages",
    "django.contrib.staticfiles",  # serving CSS, fonts and images
    "accounts",  # ours: staff accounts, sign-in, first-run setup
    "core",  # ours: the staff home page and the health check
    "mysteries",  # ours: photographs, identifications, review, export
]

# "Middleware" is a chain of small steps every request passes through.
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.about",
                "mysteries.context_processors.staff_counts",
            ],
        },
    },
]


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

# SQLite keeps the whole database in a single file. That is what makes the
# portable build possible: the app and its data are one folder.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "db.sqlite3",
        "OPTIONS": {
            # Take the write lock at the start of a change rather than midway,
            # and wait up to 20 seconds for another writer instead of failing.
            "transaction_mode": "IMMEDIATE",
            "timeout": 20,
        },
    }
}


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

# Our own account model (accounts/models.py) rather than Django's stock one.
# It is identical today; having our own from day one is what lets us add
# museum-specific fields later without rebuilding the database.
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"


# ---------------------------------------------------------------------------
# Language and time
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"  # times are stored in UTC; per-museum display zone comes later
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------------
# Static files: the CSS, fonts and images that make up the interface
# ---------------------------------------------------------------------------

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

# When the portable zip is built, every static file is gathered into this one
# folder ("collected") so the app can serve them without searching.
STATIC_ROOT = BASE_DIR / "staticfiles"

# Pictures made from the museum's scans, and files contributors attach as
# evidence, live here, inside the data folder.
MEDIA_ROOT = DATA_DIR / "media"

# While a file is being uploaded it is written here first. Keeping this inside
# the data folder means nothing of the museum's is ever left in a system
# temporary folder elsewhere on the computer.
FILE_UPLOAD_TEMP_DIR = DATA_DIR / "tmp"
for _folder in (MEDIA_ROOT, FILE_UPLOAD_TEMP_DIR):
    _folder.mkdir(parents=True, exist_ok=True)

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

if PORTABLE:
    # WhiteNoise lets the app serve its own static files, so no separate web
    # server is needed. It also renames each file to include a fingerprint of
    # its contents, so a browser never shows a stale stylesheet after an update.
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
    STORAGES["staticfiles"] = {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    }
    WHITENOISE_KEEP_ONLY_HASHED_FILES = True


# ---------------------------------------------------------------------------
# Logging: the app's diary, for working out what happened when something fails
# ---------------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "plain"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "identifycollection.log"),
            "maxBytes": 1_000_000,  # about 1 MB per file ...
            "backupCount": 5,  # ... and keep the five most recent
            "encoding": "utf-8",
            "delay": True,
            "formatter": "plain",
        },
    },
    # Portable: write to data/logs/identifycollection.log (the launcher window
    # stays clean and readable). Dev: print to the terminal.
    "root": {"handlers": ["file"] if PORTABLE else ["console"], "level": "INFO"},
}
