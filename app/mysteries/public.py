"""
The pages visitors see. None of them needs an account.
"""

from __future__ import annotations

from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from accounts.views import first_run_setup_open

from .forms import IdentificationForm
from .models import Mystery, Submission


def _viewable(request, pk: int) -> Mystery:
    """A photograph is public once staff put it on show. Staff can see the rest too."""
    mystery = get_object_or_404(Mystery, pk=pk)
    if not (mystery.is_public or request.user.is_staff):
        raise Http404
    return mystery


def gallery(request):
    if first_run_setup_open():
        return redirect("setup")  # a brand-new copy: someone has to create the first staff account
    accepted = Count("submissions", filter=Q(submissions__status=Submission.Status.ACCEPTED))
    on_show = Mystery.objects.filter(status=Mystery.Status.PUBLISHED).annotate(named=accepted).order_by("-published_at", "-id")
    page = Paginator(on_show, 24).get_page(request.GET.get("page"))
    return render(request, "mysteries/gallery.html", {"page": page})


def mystery(request, pk: int):
    photo = _viewable(request, pk)
    accepted = list(photo.accepted_submissions())
    if request.method == "POST":
        if not photo.is_public:
            raise Http404
        form = IdentificationForm(request.POST, request.FILES)
        if form.is_valid():
            submission = form.save(photo)
            return redirect("thanks", reference=submission.reference)
    else:
        form = IdentificationForm()
    boxes = [{**item.box, "label": item.person_name, "kind": "named"} for item in accepted if item.has_box]
    return render(request, "mysteries/mystery.html", {"mystery": photo, "accepted": accepted, "form": form, "boxes": boxes})


@require_GET
def thanks(request, reference: str):
    submission = get_object_or_404(Submission.objects.select_related("mystery"), reference=reference)
    return render(request, "mysteries/thanks.html", {"submission": submission})


def _picture(path) -> FileResponse:
    if not path.is_file():
        raise Http404
    response = FileResponse(path.open("rb"), content_type="image/jpeg")
    response["Cache-Control"] = "private, max-age=86400"
    return response


@require_GET
def web_image(request, pk: int):
    return _picture(_viewable(request, pk).web_path)


@require_GET
def thumb_image(request, pk: int):
    return _picture(_viewable(request, pk).thumb_path)
