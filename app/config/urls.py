"""
The address book: which web address shows which page.

Each line pairs a path (what comes after the site address) with a "view",
Django's word for the piece of code that produces a page.
"""

from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import path

from accounts.views import FirstAccountView, SignInView
from core.views import healthz, home

urlpatterns = [
    path("", home, name="home"),
    path("setup/", FirstAccountView.as_view(), name="setup"),
    path("login/", SignInView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("healthz", healthz, name="healthz"),
    path("admin/", admin.site.urls),
]
