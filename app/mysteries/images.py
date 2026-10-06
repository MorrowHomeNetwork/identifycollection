"""
Turning an uploaded scan into pictures a web browser can show.

Museum scans are often large TIFF files that browsers cannot display. For
each photograph we make two JPEG copies ("derivatives"): one large enough to
zoom into, and a small one for the gallery. The museum's own master scan is
not kept here: IdentifyCollection is not the museum's image archive, and a
data folder that fits on a USB stick matters more. We record the master's
file name, size and fingerprint so it can always be matched up again.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

# Pillow refuses very large images by default as a safety measure against
# hostile files. Archival scans are legitimately large, so raise the ceiling
# to 500 megapixels (a 600 dpi scan of a 30 x 40 inch print).
Image.MAX_IMAGE_PIXELS = 500_000_000

WEB_LONG_EDGE = 4000  # pixels: plenty for zooming in on a face
THUMB_LONG_EDGE = 520


class NotAnImage(Exception):
    """The file could not be read as a picture."""


def _printable(image: Image.Image) -> Image.Image:
    """Bring any scan format down to plain greyscale or colour, which JPEG can hold."""
    if image.mode in {"I;16", "I;16L", "I;16B", "I"}:
        # 16-bit greyscale, common in archival scans: scale 0-65535 down to 0-255.
        image = image.point(lambda value: value * (1 / 256)).convert("L")
    elif image.mode == "F":
        image = image.point(lambda value: value * 255).convert("L")
    if image.mode in {"RGBA", "LA", "PA"} or (image.mode == "P" and "transparency" in image.info):
        # See-through areas become white paper rather than black.
        layered = image.convert("RGBA")
        flat = Image.new("RGB", layered.size, "white")
        flat.paste(layered, mask=layered.getchannel("A"))
        return flat
    if image.mode not in {"L", "RGB"}:
        image = image.convert("RGB")
    return image


def make_derivatives(source: Path, web_path: Path, thumb_path: Path) -> dict:
    """
    Read the scan at `source` and write the zoomable copy and the thumbnail.
    Returns what was learned about the scan. Raises NotAnImage if it is not a
    picture we can read.
    """
    try:
        with Image.open(source) as opened:
            original_format = opened.format or ""
            image = ImageOps.exif_transpose(opened)  # honour "this photo is sideways" notes from cameras
            width, height = image.size
            image = _printable(image)

            web = image.copy()
            web.thumbnail((WEB_LONG_EDGE, WEB_LONG_EDGE), Image.Resampling.LANCZOS)
            web_path.parent.mkdir(parents=True, exist_ok=True)
            web.save(web_path, "JPEG", quality=88, optimize=True, progressive=True)

            thumb = web.copy()
            thumb.thumbnail((THUMB_LONG_EDGE, THUMB_LONG_EDGE), Image.Resampling.LANCZOS)
            thumb_path.parent.mkdir(parents=True, exist_ok=True)
            thumb.save(thumb_path, "JPEG", quality=82, optimize=True)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, SyntaxError) as problem:
        for leftover in (web_path, thumb_path):
            leftover.unlink(missing_ok=True)
        raise NotAnImage(str(problem)) from problem

    return {
        "original_format": original_format,
        "width": width,
        "height": height,
        "web_width": web.width,
        "web_height": web.height,
    }
