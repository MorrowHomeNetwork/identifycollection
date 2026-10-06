"""
The pages for museum staff: adding photographs, reviewing what visitors
send, and exporting what was accepted. Every one requires a staff sign-in.
"""

from __future__ import annotations

import csv
import mimetypes
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from . import workflow
from .forms import MysteryForm
from .images import NotAnImage
from .intake import add_photograph, add_samples, remove_samples
from .models import Mystery, Submission


def staff_required(view):
    """Only signed-in members of staff get past this."""

    @login_required
    @wraps(view)
    def guarded(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return guarded


def _plural(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


# ---------------------------------------------------------------------------
# Photographs
# ---------------------------------------------------------------------------


@staff_required
def photos(request):
    if request.method == "POST":
        action = request.POST.get("action", "")
        chosen = Mystery.objects.filter(pk__in=request.POST.getlist("photo"))
        now = timezone.now()
        if action == "publish":
            count = chosen.exclude(status=Mystery.Status.PUBLISHED).update(status=Mystery.Status.PUBLISHED, published_at=now)
            messages.success(request, f"{_plural(count, 'photograph is', 'photographs are')} now on show.")
        elif action == "publish_all":
            count = Mystery.objects.filter(status=Mystery.Status.DRAFT).update(status=Mystery.Status.PUBLISHED, published_at=now)
            messages.success(request, f"{_plural(count, 'photograph is', 'photographs are')} now on show.")
        elif action == "retire":
            count = chosen.filter(status=Mystery.Status.PUBLISHED).update(status=Mystery.Status.RETIRED)
            messages.success(request, f"{_plural(count, 'photograph was', 'photographs were')} taken off show.")
        elif action == "add_samples":
            count = add_samples(request.user)
            messages.success(request, f"Added {_plural(count, 'practice photograph', 'practice photographs')}. They are not on show yet.")
        elif action == "remove_samples":
            count = remove_samples()
            messages.success(request, f"Removed {_plural(count, 'practice photograph', 'practice photographs')} and everything sent in about them.")
        return redirect("photos")

    everything = Mystery.objects.all().order_by("status", "-created_at", "-id")
    counts = {status: 0 for status in Mystery.Status.values}
    for photo in everything:
        counts[photo.status] += 1
    return render(
        request,
        "mysteries/photos.html",
        {
            "photos": everything,
            "counts": counts,
            "total": sum(counts.values()),
            "has_samples": any(photo.is_sample for photo in everything),
        },
    )


@staff_required
@require_POST
def photo_upload(request):
    """Receives scans. The page sends them one at a time so a big folder cannot time out."""
    uploads = request.FILES.getlist("file")
    results = []
    for upload in uploads:
        try:
            mystery, created = add_photograph(upload, request.user)
            results.append({"ok": True, "name": upload.name, "id": mystery.pk, "duplicate": not created})
        except NotAnImage:
            results.append({"ok": False, "name": upload.name, "error": "Not a picture IdentifyCollection can read."})
    if request.headers.get("X-Requested-With") == "fetch":
        return JsonResponse({"results": results}, status=200 if uploads else 400)
    added = sum(1 for item in results if item["ok"] and not item["duplicate"])
    skipped = [item["name"] for item in results if not item["ok"]]
    if added:
        messages.success(request, f"Added {_plural(added, 'photograph', 'photographs')}. They are not on show yet.")
    if skipped:
        messages.error(request, "Could not read: " + ", ".join(skipped))
    return redirect("photos")


@staff_required
def photo_edit(request, pk: int):
    photo = get_object_or_404(Mystery, pk=pk)
    form = MysteryForm(request.POST or None, instance=photo)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Saved.")
        return redirect("photos")
    return render(request, "mysteries/photo_edit.html", {"mystery": photo, "form": form})


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------


@staff_required
def queue(request):
    show = request.GET.get("show", Submission.Status.PENDING)
    if show not in Submission.Status.values:
        show = Submission.Status.PENDING
    submissions = Submission.objects.filter(status=show).select_related("mystery").order_by("created_at")
    counts = {status: Submission.objects.filter(status=status).count() for status in Submission.Status.values}
    return render(
        request,
        "mysteries/queue.html",
        {"submissions": submissions, "show": show, "counts": counts, "statuses": Submission.Status.choices},
    )


@staff_required
def submission(request, reference: str):
    item = get_object_or_404(Submission.objects.select_related("mystery", "decided_by"), reference=reference)
    if request.method == "POST":
        action = request.POST.get("action", "")
        note = request.POST.get("note", "").strip()
        try:
            if action == "accept":
                workflow.accept(item, request.user, note)
                messages.success(request, f"Accepted: {item.person_name}. It now shows on the photograph and in the export.")
            elif action == "reject":
                workflow.reject(item, request.user, note)
                messages.success(request, "Declined. Nothing was made public.")
            elif action == "withdraw":
                workflow.withdraw(item, request.user, note)
                messages.success(request, "Withdrawn. It no longer shows on the photograph; the history is kept.")
            elif action == "remove_personal_data":
                if request.POST.get("confirm") != "yes":
                    raise workflow.NotAllowed("Tick the box to confirm before removing the contributor's details.")
                workflow.remove_personal_data(item)
                messages.success(request, "The contributor's name and contact details were removed.")
        except workflow.NotAllowed as problem:
            messages.error(request, str(problem))
            return redirect("submission", reference=reference)
        if action in {"accept", "reject"}:
            return redirect("queue")
        return redirect("submission", reference=reference)

    boxes = [{**other.box, "label": other.person_name, "kind": "named"} for other in item.mystery.accepted_submissions() if other.has_box and other.pk != item.pk]
    if item.has_box:
        boxes.append({**item.box, "label": item.person_name, "kind": "proposed"})
    history = sorted(
        [("Accepted", event.at, event.by, event.note) for event in item.accessions.select_related("by")]
        + [("Withdrawn", event.at, event.by, event.reason) for event in item.deaccessions.select_related("by")],
        key=lambda row: row[1],
    )
    return render(request, "mysteries/submission.html", {"item": item, "boxes": boxes, "history": history, "Status": Submission.Status})


@staff_required
@require_GET
def evidence_file(request, pk: int):
    """Files contributors attach are for staff eyes only."""
    from .models import Evidence

    item = get_object_or_404(Evidence, pk=pk)
    path = item.file_path
    if not path or not path.is_file():
        raise Http404
    content_type = mimetypes.guess_type(item.file_name or path.name)[0] or "application/octet-stream"
    response = FileResponse(path.open("rb"), content_type=content_type, as_attachment=True, filename=item.file_name or path.name)
    response["Cache-Control"] = "no-store"
    return response


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

EXPORT_COLUMNS = [
    "reference", "status", "object_id", "photograph_title", "scan_file_name", "person_name", "confidence",
    "position_in_picture", "box_left_px", "box_top_px", "box_width_px", "box_height_px", "w3c_selector",
    "evidence_kind", "evidence_text", "evidence_file_name", "rights_acknowledged", "consent_given",
    "credited_to", "accepted_by", "accepted_at", "withdrawn_by", "withdrawn_at", "withdrawal_reason",
]  # fmt: skip


def export_rows():
    """Everything ever accepted: what stands today, and what was later withdrawn (so the catalog can be corrected)."""
    wanted = [Submission.Status.ACCEPTED, Submission.Status.WITHDRAWN]
    submissions = (
        Submission.objects.filter(status__in=wanted)
        .select_related("mystery")
        .prefetch_related("evidence", "accessions__by", "deaccessions__by")
        .order_by("mystery__object_id", "mystery_id", "id")
    )
    for item in submissions:
        evidence = list(item.evidence.all())
        first = evidence[0] if evidence else None
        accession = list(item.accessions.all())[-1] if item.accessions.all() else None
        withdrawal = list(item.deaccessions.all())[-1] if item.status == Submission.Status.WITHDRAWN and item.deaccessions.all() else None
        box = item.pixel_box() or ("", "", "", "")
        yield [
            item.reference, item.status, item.mystery.object_id, item.mystery.title, item.mystery.original_name,
            item.person_name, item.get_confidence_display(), item.position_note, *box, item.selector(),
            first.get_kind_display() if first else "", first.text if first else "", first.file_name if first else "",
            "yes" if first and first.rights_acknowledged else "", "yes" if first and first.consent_given else "",
            item.public_credit,
            accession.by.get_username() if accession and accession.by else "",
            accession.at.strftime("%Y-%m-%d %H:%M UTC") if accession else "",
            withdrawal.by.get_username() if withdrawal and withdrawal.by else "",
            withdrawal.at.strftime("%Y-%m-%d %H:%M UTC") if withdrawal else "",
            withdrawal.reason if withdrawal else "",
        ]  # fmt: skip


@staff_required
@require_GET
def export(request):
    counts = {
        "accepted": Submission.objects.filter(status=Submission.Status.ACCEPTED).count(),
        "withdrawn": Submission.objects.filter(status=Submission.Status.WITHDRAWN).count(),
    }
    return render(request, "mysteries/export.html", {"counts": counts, "columns": EXPORT_COLUMNS})


@staff_required
@require_GET
def export_csv(request):
    stamp = timezone.now().strftime("%Y-%m-%d")
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="identifications-{stamp}.csv"'
    response["Cache-Control"] = "no-store"
    response.write("\ufeff")  # tells Excel the file is UTF-8, so accented names survive
    writer = csv.writer(response)
    writer.writerow(EXPORT_COLUMNS)
    for row in export_rows():
        writer.writerow(row)
    return response
