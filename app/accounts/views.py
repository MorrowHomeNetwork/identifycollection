"""
Views for signing in and for first-run setup.

A "view" is the code that answers one kind of request: it decides what the
person should see and returns a page.
"""

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import FormView

from .forms import FirstAccountForm
from .models import User


def first_run_setup_open() -> bool:
    """
    True only while this installation has no accounts at all.

    The moment the first account exists this is False for good, and the setup
    page refuses to do anything. Further staff accounts are created by a
    signed-in member of staff, never from the open web.
    """
    return settings.ALLOW_WEB_SETUP and not User.objects.exists()


class SignInView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def dispatch(self, request, *args, **kwargs):
        if first_run_setup_open():
            # Nobody can sign in yet: send them to create the first account.
            return redirect("setup")
        return super().dispatch(request, *args, **kwargs)


class FirstAccountView(FormView):
    template_name = "accounts/setup.html"
    form_class = FirstAccountForm
    success_url = reverse_lazy("home")

    def dispatch(self, request, *args, **kwargs):
        if not first_run_setup_open():
            return redirect("login")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        # "atomic" means all-or-nothing: the check and the save happen as one
        # step, so two browsers racing each other cannot both create a
        # "first" account.
        with transaction.atomic():
            if User.objects.exists():
                return redirect("login")
            user = form.save(commit=False)
            user.is_staff = True
            user.is_superuser = True  # the first account can do everything
            user.save()
        login(self.request, user)
        return super().form_valid(form)
