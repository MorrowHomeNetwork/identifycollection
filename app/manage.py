#!/usr/bin/env python
"""
Django's command-line tool for this project. Used during development:

    python manage.py runserver        start a development server
    python manage.py test             run the automated tests
    python manage.py makemigrations   record a change to the database layout
    python manage.py migrate          apply recorded changes to the database

Museums never use this file; their copy is started by launch.py.
"""

import os
import sys
from pathlib import Path


def main() -> None:
    # Make sure the app/ folder is importable however this file was started.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django is not installed in this Python. From the repository folder, "
            "run:  python -m pip install -r requirements.txt"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
