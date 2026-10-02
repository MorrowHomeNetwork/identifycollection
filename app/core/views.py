"""
The home page and the health check.
"""

import os
import platform

import django
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@login_required
def home(request):
    """What staff see after signing in. An honest placeholder for now."""
    return render(
        request,
        "core/home.html",
        {
            "data_dir": settings.DATA_DIR,
            "database_file": settings.DATABASES["default"]["NAME"],
            "log_file": settings.LOG_DIR / "identifycollection.log",
            "portable": settings.PORTABLE,
            "python_version": platform.python_version(),
            "django_version": django.get_version(),
        },
    )


@require_GET
@never_cache
def healthz(request):
    """
    A tiny machine-readable "I am alive" answer.

    The launcher uses it to tell whether IdentifyCollection is already running
    from this folder, and the automated smoke test uses it to know the app has
    started. It reveals nothing about the collection.
    """
    return JsonResponse(
        {
            "app": "identifycollection",
            "status": "ok",
            "version": settings.VERSION,
            "instance": os.environ.get("IDENTIFYCOLLECTION_INSTANCE", ""),
        }
    )
