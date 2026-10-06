"""
The decisions a collections manager can take, and nothing else.

Every change of a submission's status goes through one of these functions,
so the rules live in one place: who may decide, what must be recorded, and
which moves are allowed.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from .models import AccessionEvent, DeaccessionEvent, Submission


class NotAllowed(Exception):
    """The requested decision does not apply to a submission in its current state."""


def _decide(submission: Submission, user, status: str, note: str) -> None:
    submission.status = status
    submission.decided_by = user
    submission.decided_at = timezone.now()
    submission.decision_note = note
    submission.save(update_fields=["status", "decided_by", "decided_at", "decision_note"])


@transaction.atomic
def accept(submission: Submission, user, note: str = "") -> None:
    """Accept into the record. Also used to reinstate something declined or withdrawn earlier."""
    if submission.status == Submission.Status.ACCEPTED:
        raise NotAllowed("This identification is already accepted.")
    AccessionEvent.objects.create(submission=submission, by=user, note=note)
    _decide(submission, user, Submission.Status.ACCEPTED, note)


@transaction.atomic
def reject(submission: Submission, user, note: str = "") -> None:
    if submission.status != Submission.Status.PENDING:
        raise NotAllowed("Only a submission waiting for review can be declined.")
    _decide(submission, user, Submission.Status.REJECTED, note)


@transaction.atomic
def withdraw(submission: Submission, user, reason: str) -> None:
    """Take an accepted identification back out of the record, keeping the history."""
    if submission.status != Submission.Status.ACCEPTED:
        raise NotAllowed("Only an accepted identification can be withdrawn.")
    if not reason.strip():
        raise NotAllowed("A reason is required to withdraw an identification.")
    DeaccessionEvent.objects.create(submission=submission, by=user, reason=reason.strip())
    _decide(submission, user, Submission.Status.WITHDRAWN, reason.strip())


@transaction.atomic
def remove_personal_data(submission: Submission) -> None:
    """Erase who sent this, at their request. The identification itself stays."""
    submission.contributor_name = ""
    submission.contributor_contact = ""
    submission.contact_ok = False
    submission.credit_ok = False
    submission.personal_data_removed_at = timezone.now()
    submission.save(
        update_fields=["contributor_name", "contributor_contact", "contact_ok", "credit_ok", "personal_data_removed_at"]
    )
