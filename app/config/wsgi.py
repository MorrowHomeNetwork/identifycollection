"""
The hand-off point between the web server and Django.

WSGI is the standard plug that lets any Python web server run any Python web
application. The server (waitress, in the portable build) imports
"application" from this file and passes every request to it.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
