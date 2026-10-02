"""
Forms: the fields a person fills in, and the checks run on what they typed.
"""

from django.contrib.auth.forms import UserCreationForm

from .models import User


class FirstAccountForm(UserCreationForm):
    """
    Creates the first staff account on a fresh installation.

    Django's UserCreationForm already does the careful parts: it asks for the
    password twice, runs the password rules from settings.py, and stores only
    a scrambled ("hashed") form of the password, never the password itself.
    """

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].help_text = (
            "What you will type to sign in. Letters, numbers and @ . + - _ only."
        )
        self.fields["password2"].label = "Password, again"
        self.fields["password2"].help_text = ""
