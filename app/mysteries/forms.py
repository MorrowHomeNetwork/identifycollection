"""
The forms: what a visitor fills in to identify someone, and what staff fill
in to describe a photograph. A Django "form" checks what was typed and
explains, in plain words, anything that needs fixing.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from django import forms
from django.conf import settings
from django.db import transaction

from .models import Evidence, Mystery, Submission

EVIDENCE_FILE_TYPES = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".gif"}
EVIDENCE_MAX_BYTES = 25 * 1024 * 1024


class IdentificationForm(forms.Form):
    person_name = forms.CharField(
        label="Who is this?",
        max_length=200,
        help_text="Their name, as fully as you know it. A maiden name or nickname helps too.",
    )
    confidence = forms.ChoiceField(
        label="How sure are you?",
        choices=Submission.Confidence.choices,
        initial=Submission.Confidence.PROBABLE,
        widget=forms.RadioSelect,
    )
    box_x = forms.FloatField(required=False, widget=forms.HiddenInput)
    box_y = forms.FloatField(required=False, widget=forms.HiddenInput)
    box_w = forms.FloatField(required=False, widget=forms.HiddenInput)
    box_h = forms.FloatField(required=False, widget=forms.HiddenInput)
    position_note = forms.CharField(
        label="Where are they in the picture?",
        required=False,
        max_length=300,
        help_text='Needed only if you did not mark them above. For example: "back row, second from the left".',
    )
    evidence_kind = forms.ChoiceField(
        label="How do you know?",
        choices=Evidence.Kind.choices,
        initial=Evidence.Kind.TESTIMONY,
        widget=forms.RadioSelect,
    )
    evidence_text = forms.CharField(
        label="Tell the museum what you know",
        required=False,
        max_length=5000,
        widget=forms.Textarea(attrs={"rows": 5}),
        help_text="For example: how you are related, where you have seen this picture before, "
        "or which other record shows the same person.",
    )
    evidence_file = forms.FileField(
        label="Attach your document or photograph",
        required=False,
        help_text="A PDF or a picture, up to 25 MB. A phone photo of the page is fine.",
    )
    rights = forms.BooleanField(
        required=False,
        label="I have the right to share this file, and I allow the museum to keep a copy with its records.",
    )
    consent = forms.BooleanField(
        required=False,
        label="I agree that the museum may keep what I have written here as part of its records.",
    )
    contributor_name = forms.CharField(label="Your name", required=False, max_length=200)
    contributor_contact = forms.CharField(label="Your email address or phone number", required=False, max_length=254)
    contact_ok = forms.BooleanField(required=False, label="The museum may contact me about this photograph.")
    credit_ok = forms.BooleanField(required=False, label="The museum may show my name next to this identification.")
    # Not shown to people. Programs that fill in every field give themselves away here.
    website = forms.CharField(required=False)

    def clean_evidence_file(self):
        upload = self.cleaned_data.get("evidence_file")
        if upload:
            if Path(upload.name).suffix.lower() not in EVIDENCE_FILE_TYPES:
                raise forms.ValidationError("Please attach a PDF or a picture (JPEG, PNG, TIFF, WebP or GIF).")
            if upload.size > EVIDENCE_MAX_BYTES:
                raise forms.ValidationError("This file is larger than 25 MB. A phone photo of the page is enough.")
        return upload

    def clean(self):
        data = super().clean()
        if data.get("website"):
            raise forms.ValidationError("This form could not be accepted.")

        box = [data.get(name) for name in ("box_x", "box_y", "box_w", "box_h")]
        if all(value is not None for value in box):
            x, y, w, h = box
            inside = 0 <= x < 1 and 0 <= y < 1 and 0.004 <= w <= 1 and 0.004 <= h <= 1 and x + w <= 1.001 and y + h <= 1.001
            if not inside:
                raise forms.ValidationError("The marked area was not understood. Please mark the person again.")
        else:
            for name in ("box_x", "box_y", "box_w", "box_h"):
                data[name] = None
            if not data.get("position_note"):
                self.add_error(
                    "position_note",
                    "Mark the person in the photograph, or describe here where they are.",
                )

        kind = data.get("evidence_kind")
        if kind == Evidence.Kind.TESTIMONY:
            if not data.get("evidence_text"):
                self.add_error("evidence_text", "Please say how you know who this is.")
            if not data.get("consent"):
                self.add_error("consent", "Please tick this box so the museum may keep your account.")
        elif kind == Evidence.Kind.DOCUMENT:
            if not data.get("evidence_file") and "evidence_file" not in self.errors:
                self.add_error("evidence_file", "Please attach the document or photograph.")
            if not data.get("rights"):
                self.add_error("rights", "Please tick this box so the museum may keep the file.")
        elif kind == Evidence.Kind.CROSS_REFERENCE:
            if not data.get("evidence_text"):
                self.add_error("evidence_text", "Please say which other record shows this person.")

        if data.get("contact_ok") and not data.get("contributor_contact"):
            self.add_error("contributor_contact", "Please give an email address or phone number, or untick the box below.")
        return data

    @transaction.atomic
    def save(self, mystery: Mystery) -> Submission:
        data = self.cleaned_data
        submission = Submission.objects.create(
            mystery=mystery,
            person_name=data["person_name"].strip(),
            confidence=data["confidence"],
            box_x=data["box_x"],
            box_y=data["box_y"],
            box_w=data["box_w"],
            box_h=data["box_h"],
            position_note=data.get("position_note", "").strip(),
            contributor_name=data.get("contributor_name", "").strip(),
            contributor_contact=data.get("contributor_contact", "").strip(),
            contact_ok=bool(data.get("contact_ok")),
            credit_ok=bool(data.get("credit_ok")),
        )
        kind = data["evidence_kind"]
        evidence = Evidence(
            submission=submission,
            kind=kind,
            text=data.get("evidence_text", "").strip(),
            rights_acknowledged=bool(data.get("rights")) and kind == Evidence.Kind.DOCUMENT,
            consent_given=bool(data.get("consent")),
        )
        upload = data.get("evidence_file")
        if upload and kind == Evidence.Kind.DOCUMENT:
            # Stored under a random name, so one contributor's file can never
            # overwrite another's and its name gives nothing away.
            relative = Path("evidence") / f"{uuid.uuid4().hex}{Path(upload.name).suffix.lower()}"
            target = Path(settings.MEDIA_ROOT) / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as out:
                for chunk in upload.chunks():
                    out.write(chunk)
            evidence.file = relative.as_posix()
            evidence.file_name = Path(upload.name).name[:255]
        evidence.save()
        return submission


class MysteryForm(forms.ModelForm):
    class Meta:
        model = Mystery
        fields = ["object_id", "title", "date_text", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}
        help_texts = {
            "object_id": "The catalog number of this photograph, if it has one.",
            "title": "A short description visitors will see above the picture.",
        }
