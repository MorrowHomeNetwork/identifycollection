"""
Staff accounts.

A "model" is Django's description of one kind of record kept in the database.
This one is the museum staff account. It adds nothing to Django's standard
account yet. It exists so that museum-specific details can be added later
without rebuilding the database, which is what happens if a project starts
on the stock account model and changes its mind.

Visitors who submit identifications never need an account; that is a rule of
the project, not an omission.
"""

from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    class Meta(AbstractUser.Meta):
        verbose_name = "staff account"
        verbose_name_plural = "staff accounts"
