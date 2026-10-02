"""
A "context processor" hands the same few facts to every page, so each page
template can show them without every view having to pass them along.
"""

from django.conf import settings


def about(request):
    return {
        "app_version": settings.VERSION,
        "source_url": settings.SOURCE_URL,
    }
