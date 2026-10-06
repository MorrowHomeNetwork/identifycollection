"""
Bringing photographs in: from an uploaded scan, or from the built-in practice set.
"""

from __future__ import annotations

import hashlib
import random
import tempfile
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageDraw, ImageFilter

from .images import NotAnImage, make_derivatives
from .models import Mystery

MAX_SCAN_BYTES = 600 * 1024 * 1024


def add_photograph(upload, user=None, *, is_sample: bool = False, **catalog) -> tuple[Mystery, bool]:
    """
    Store one uploaded scan as a new, not-yet-shown mystery.

    Returns (mystery, created). The same file uploaded twice is recognised by
    its fingerprint and is not added again. Raises NotAnImage for anything
    that is not a readable picture.
    """
    if upload.size > MAX_SCAN_BYTES:
        raise NotAnImage("This file is larger than 600 MB.")
    scratch_dir = Path(settings.FILE_UPLOAD_TEMP_DIR)
    scratch_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with tempfile.NamedTemporaryFile(dir=scratch_dir, suffix=".upload", delete=False) as scratch:
        for chunk in upload.chunks():
            digest.update(chunk)
            scratch.write(chunk)
    scratch_path = Path(scratch.name)
    try:
        fingerprint = digest.hexdigest()
        existing = Mystery.objects.filter(sha256=fingerprint).first()
        if existing:
            return existing, False
        mystery = Mystery(
            original_name=Path(upload.name).name[:255],
            sha256=fingerprint,
            original_bytes=upload.size,
            created_by=user,
            is_sample=is_sample,
            **catalog,
        )
        facts = make_derivatives(scratch_path, mystery.web_path, mystery.thumb_path)
        for name, value in facts.items():
            setattr(mystery, name, value)
        mystery.save()
        return mystery, True
    finally:
        scratch_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Practice material
# ---------------------------------------------------------------------------

SAMPLES = [
    ("SAMPLE.001", "Five people outside a building", "about 1915", 5),
    ("SAMPLE.002", "Wedding party on the church steps", "about 1924", 7),
    ("SAMPLE.003", "Two women at a garden gate", "1930s", 2),
    ("SAMPLE.004", "School class with their teacher", "about 1908", 9),
    ("SAMPLE.005", "Three men beside a delivery wagon", "about 1919", 3),
    ("SAMPLE.006", "Family portrait in a studio", "about 1899", 4),
]


def _draw_sample(seed: int, people: int) -> Image.Image:
    """A made-up 'old photograph': plain silhouettes, so nobody real is depicted."""
    rng = random.Random(seed)
    width, height = 2400, 1800
    image = Image.new("L", (width, height), 150)
    draw = ImageDraw.Draw(image)
    for y in range(height):  # a backdrop that darkens towards the floor
        draw.line([(0, y), (width, y)], fill=int(178 - 70 * (y / height)))
    draw.rectangle([0, int(height * 0.82), width, height], fill=84)
    rows = 2 if people > 4 else 1
    per_row = [people - people // 2, people // 2] if rows == 2 else [people]
    for row, count in enumerate(per_row):
        back = rows == 2 and row == 0
        base = height * (0.80 if back else 0.97)
        scale = 0.82 if back else 1.0
        spread = width * (0.72 if count > 2 else 0.4)
        for index in range(count):
            cx = width / 2 + (index - (count - 1) / 2) * (spread / max(count - 1, 1) if count > 1 else 0) + rng.uniform(-18, 18)
            tall = rng.uniform(0.86, 1.0) * scale
            body_w, body_h, head = 300 * tall, 760 * tall, 112 * tall
            shade = rng.choice([52, 64, 78, 176, 190])
            top = base - body_h
            draw.rounded_rectangle([cx - body_w / 2, top, cx + body_w / 2, base], radius=int(110 * tall), fill=shade)
            draw.ellipse([cx - head, top - head * 2.05, cx + head, top - head * 0.05], fill=214)
            draw.pieslice([cx - head * 1.08, top - head * 2.2, cx + head * 1.08, top - head * 0.3], 180, 360, fill=rng.choice([40, 52, 66]))
            if rng.random() < 0.3:
                draw.rectangle([cx - head * 1.25, top - head * 2.25, cx + head * 1.25, top - head * 2.05], fill=36)
                draw.rectangle([cx - head * 0.8, top - head * 2.9, cx + head * 0.8, top - head * 2.2], fill=36)
    image = image.filter(ImageFilter.GaussianBlur(1.6))
    grain = Image.effect_noise((width, height), 16).point(lambda value: value - 128 + 128)
    image = Image.blend(image, grain, 0.12)
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, width - 1, height - 1], outline=235, width=26)  # the white border of a print
    return image


def add_samples(user=None) -> int:
    """Create the practice photographs (skipping any already present). Returns how many were added."""
    from django.core.files.uploadedfile import SimpleUploadedFile
    import io

    added = 0
    for number, (object_id, title, date_text, people) in enumerate(SAMPLES, start=1):
        if Mystery.objects.filter(is_sample=True, object_id=object_id).exists():
            continue
        buffer = io.BytesIO()
        _draw_sample(number, people).save(buffer, "PNG")
        upload = SimpleUploadedFile(f"{object_id}.png", buffer.getvalue(), content_type="image/png")
        _mystery, created = add_photograph(
            upload,
            user,
            is_sample=True,
            object_id=object_id,
            title=f"{title} (practice photograph)",
            date_text=date_text,
            description="A made-up picture for trying IdentifyCollection out. It shows nobody real.",
        )
        added += int(created)
    return added


def remove_samples() -> int:
    """Delete the practice photographs and everything submitted about them."""
    from .models import AccessionEvent, DeaccessionEvent, Submission

    samples = Mystery.objects.filter(is_sample=True)
    count = samples.count()
    submissions = Submission.objects.filter(mystery__in=samples)
    AccessionEvent.objects.filter(submission__in=submissions).delete()
    DeaccessionEvent.objects.filter(submission__in=submissions).delete()
    for submission in submissions:
        for item in submission.evidence.all():
            if item.file_path:
                item.file_path.unlink(missing_ok=True)
    submissions.delete()
    for mystery in samples:
        mystery.web_path.unlink(missing_ok=True)
        mystery.thumb_path.unlink(missing_ok=True)
    samples.delete()
    return count
