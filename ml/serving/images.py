"""Decode an uploaded photo once, defensively, into the PIL image every image
model accepts (`ml/features/cnn.py:ImageSource`)."""

from __future__ import annotations

import io

from PIL import Image, ImageOps

MAX_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 25_000_000

_SIGNATURES = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n")


class ImageRejected(ValueError):
    """The upload is not an image this service will decode."""


class ImageTooLarge(ValueError):
    pass


def decode_upload(data: bytes) -> Image.Image:
    if len(data) > MAX_BYTES:
        raise ImageTooLarge(f"image exceeds {MAX_BYTES // (1024 * 1024)} MB")
    if not data.startswith(_SIGNATURES):
        raise ImageRejected("only JPEG and PNG images are accepted")
    try:
        probe = Image.open(io.BytesIO(data))
        if probe.width * probe.height > MAX_PIXELS:
            raise ImageTooLarge("image exceeds 25 megapixels")
        probe.verify()
        image = Image.open(io.BytesIO(data))
        image = ImageOps.exif_transpose(image)
        return image.convert("RGB")
    except (ImageTooLarge, ImageRejected):
        raise
    except Exception as exc:  # noqa: BLE001 - any decoder failure is a bad upload
        raise ImageRejected(f"could not decode image: {exc}") from exc
