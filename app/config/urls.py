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
from mysteries import public, staff

urlpatterns = [
    # --- anyone ---
    path("", public.gallery, name="gallery"),
    path("photo/<int:pk>/", public.mystery, name="mystery"),
    path("thanks/<str:reference>/", public.thanks, name="thanks"),
    path("media/web/<int:pk>.jpg", public.web_image, name="web_image"),
    path("media/thumb/<int:pk>.jpg", public.thumb_image, name="thumb_image"),
    # --- accounts ---
    path("setup/", FirstAccountView.as_view(), name="setup"),
    path("login/", SignInView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    # --- museum staff ---
    path("staff/", home, name="home"),
    path("staff/photos/", staff.photos, name="photos"),
    path("staff/photos/upload/", staff.photo_upload, name="photo_upload"),
    path("staff/photos/<int:pk>/", staff.photo_edit, name="photo_edit"),
    path("staff/review/", staff.queue, name="queue"),
    path("staff/review/<str:reference>/", staff.submission, name="submission"),
    path("staff/evidence/<int:pk>/file/", staff.evidence_file, name="evidence_file"),
    path("staff/export/", staff.export, name="export"),
    path("staff/export/identifications.csv", staff.export_csv, name="export_csv"),
    # --- behind the scenes ---
    path("healthz", healthz, name="healthz"),
    path("admin/", admin.site.urls),
]
