"""Small facts every staff page shows, such as how many submissions are waiting."""

from .models import Submission


def staff_counts(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated or not user.is_staff:
        return {}
    return {"pending_count": Submission.objects.filter(status=Submission.Status.PENDING).count()}
