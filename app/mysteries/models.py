"""
What IdentifyCollection remembers.

A "model" describes one kind of record in the database. These are the core
of the project:

    Mystery           a photograph with people nobody at the museum can name
    Submission        one visitor's answer: "this person is ..."
    Evidence          what supports that answer
    AccessionEvent    a collections manager accepted an answer into the record
    DeaccessionEvent  a collections manager later withdrew an accepted answer

Two promises are built into this file. Nothing reaches the public or the
export without an AccessionEvent made by a member of staff. And an accepted
answer is never deleted: withdrawing it adds a DeaccessionEvent that says
who, when and why, and the history stays.
"""

from __future__ import annotations

import secrets
from pathlib import Path

from django.conf import settings
from django.db import models
from django.urls import reverse

_REFERENCE_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I, which people misread


def new_reference() -> str:
    """A short code a visitor can quote to staff, such as IC-7KQ2MX."""
    return "IC-" + "".join(secrets.choice(_REFERENCE_LETTERS) for _ in range(6))


class Mystery(models.Model):
    """A photograph the museum would like help with."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Not yet on show"
        PUBLISHED = "published", "On show"
        RETIRED = "retired", "Taken off show"

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True)
    is_sample = models.BooleanField(default=False, help_text="Made-up practice material, safe to remove.")

    # --- the scan ---
    original_name = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64, unique=True, help_text="Fingerprint of the original file.")
    original_bytes = models.BigIntegerField(default=0)
    original_format = models.CharField(max_length=20, blank=True)
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    web_width = models.PositiveIntegerField(default=0)
    web_height = models.PositiveIntegerField(default=0)

    # --- what the catalog says about it ---
    object_id = models.CharField("Object ID", max_length=100, blank=True, db_index=True)
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    date_text = models.CharField("Date", max_length=100, blank=True, help_text='As the catalog gives it, for example "about 1920".')
    catalog = models.JSONField(default=dict, blank=True, help_text="The catalog row this came from, kept as imported.")

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "mysteries"
        ordering = ["-published_at", "-created_at", "-id"]

    def __str__(self) -> str:
        return self.display_title

    @property
    def display_title(self) -> str:
        return self.title or self.object_id or f"Photograph {self.pk}"

    @property
    def is_public(self) -> bool:
        return self.status == self.Status.PUBLISHED

    def _derivative(self, kind: str) -> Path:
        return Path(settings.MEDIA_ROOT) / kind / self.sha256[:2] / f"{self.sha256}.jpg"

    @property
    def web_path(self) -> Path:
        return self._derivative("web")

    @property
    def thumb_path(self) -> Path:
        return self._derivative("thumb")

    def get_absolute_url(self) -> str:
        return reverse("mystery", args=[self.pk])

    def accepted_submissions(self):
        return self.submissions.filter(status=Submission.Status.ACCEPTED).order_by("decided_at")


class Submission(models.Model):
    """One person's answer about one face in one photograph."""

    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for review"
        ACCEPTED = "accepted", "Accepted into the record"
        REJECTED = "rejected", "Declined"
        WITHDRAWN = "withdrawn", "Withdrawn after acceptance"

    class Confidence(models.TextChoices):
        CERTAIN = "certain", "I am certain"
        PROBABLE = "probable", "I am fairly sure"
        POSSIBLE = "possible", "It is my best guess"

    mystery = models.ForeignKey(Mystery, on_delete=models.PROTECT, related_name="submissions")
    reference = models.CharField(max_length=12, unique=True, default=new_reference, editable=False)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)

    person_name = models.CharField(max_length=200)
    confidence = models.CharField(max_length=10, choices=Confidence.choices, default=Confidence.PROBABLE)

    # Where the person is in the picture: a box, as fractions (0 to 1) of the
    # picture's width and height, so it holds whatever size the picture is shown at.
    box_x = models.FloatField(null=True, blank=True)
    box_y = models.FloatField(null=True, blank=True)
    box_w = models.FloatField(null=True, blank=True)
    box_h = models.FloatField(null=True, blank=True)
    position_note = models.CharField(max_length=300, blank=True)

    # The contributor. All optional, and removable on request.
    contributor_name = models.CharField(max_length=200, blank=True)
    contributor_contact = models.CharField(max_length=254, blank=True)
    contact_ok = models.BooleanField(default=False)
    credit_ok = models.BooleanField(default=False)
    personal_data_removed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"{self.reference}: {self.person_name}"

    @property
    def has_box(self) -> bool:
        return None not in (self.box_x, self.box_y, self.box_w, self.box_h)

    @property
    def box(self) -> dict | None:
        if not self.has_box:
            return None
        return {"x": self.box_x, "y": self.box_y, "w": self.box_w, "h": self.box_h}

    def pixel_box(self) -> tuple[int, int, int, int] | None:
        """The box in pixels of the ORIGINAL scan: left, top, width, height."""
        if not self.has_box or not self.mystery.width:
            return None
        width, height = self.mystery.width, self.mystery.height
        return (round(self.box_x * width), round(self.box_y * height), round(self.box_w * width), round(self.box_h * height))

    def selector(self) -> str:
        """The box in the W3C "media fragment" notation other software understands."""
        box = self.pixel_box()
        return "xywh=pixel:{},{},{},{}".format(*box) if box else ""

    def web_annotation(self) -> dict:
        """This identification as a W3C Web Annotation, the open standard for notes on images."""
        target: dict = {"source": self.mystery.object_id or self.mystery.original_name}
        if self.has_box:
            target["selector"] = {
                "type": "FragmentSelector",
                "conformsTo": "http://www.w3.org/TR/media-frags/",
                "value": self.selector(),
            }
        return {
            "@context": "http://www.w3.org/ns/anno.jsonld",
            "id": f"urn:identifycollection:{self.reference}",
            "type": "Annotation",
            "motivation": "identifying",
            "body": [{"type": "TextualBody", "purpose": "identifying", "value": self.person_name}],
            "target": target,
        }

    @property
    def public_credit(self) -> str:
        return self.contributor_name if self.credit_ok and self.contributor_name else ""


class Evidence(models.Model):
    """What a contributor offers in support of their answer."""

    class Kind(models.TextChoices):
        TESTIMONY = "testimony", "I know from my own knowledge"
        DOCUMENT = "document", "I have a document or photograph"
        CROSS_REFERENCE = "cross_reference", "It matches another record"

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="evidence")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    text = models.TextField(blank=True)
    file = models.CharField(max_length=300, blank=True, help_text="Where the uploaded file is kept, inside the data folder.")
    file_name = models.CharField(max_length=255, blank=True)
    rights_acknowledged = models.BooleanField(default=False)
    consent_given = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "evidence"
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} for {self.submission.reference}"

    @property
    def file_path(self) -> Path | None:
        return Path(settings.MEDIA_ROOT) / self.file if self.file else None


class AccessionEvent(models.Model):
    """A member of staff accepted a submission into the museum's record."""

    submission = models.ForeignKey(Submission, on_delete=models.PROTECT, related_name="accessions")
    by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["at", "id"]


class DeaccessionEvent(models.Model):
    """A member of staff withdrew an accepted submission. The reason is required and kept."""

    submission = models.ForeignKey(Submission, on_delete=models.PROTECT, related_name="deaccessions")
    by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField()

    class Meta:
        ordering = ["at", "id"]
