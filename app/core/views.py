"""
The staff home page and the health check.
"""

import os
import platform

import django
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from mysteries.models import Mystery, Submission
from mysteries.staff import staff_required


@staff_required
def home(request):
    """What staff see after signing in: where things stand, and where to go next."""
    stats = {
        "published": Mystery.objects.filter(status=Mystery.Status.PUBLISHED).count(),
        "draft": Mystery.objects.filter(status=Mystery.Status.DRAFT).count(),
        "pending": Submission.objects.filter(status=Submission.Status.PENDING).count(),
        "accepted": Submission.objects.filter(status=Submission.Status.ACCEPTED).count(),
    }
    return render(
        request,
        "core/home.html",
        {
            "stats": stats,
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
