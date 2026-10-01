"""Colour and texture features for soil photographs.

## Why this is its own module

This function previously existed twice, byte-for-byte identical, in
`train_soil_type_model.py` and `soil_type_prediction.py`. Nothing enforced that
they stayed identical. Tuning a histogram bin count during training — an
obvious, harmless-looking change — would have left the serving path computing a
different feature vector than the model was fitted on, and the model would have
kept returning predictions rather than raising, so the damage would have been
silent and would have looked like a mysterious accuracy drop in production.

Training and serving now import the same function. If it changes, it changes
for both, and models trained under the old definition are invalidated by the
`FEATURE_VERSION` check below rather than quietly mispredicting.

## Why these features

Soil type from a photograph is dominated by colour: red laterite, black cotton
soil, pale alluvial and grey cinder separate largely on hue and value alone.
Texture is included as a coarse grain indicator but is expected to matter less.

This was originally written as a fallback, because the environment it was
authored in could not reach `storage.googleapis.com` to fetch pretrained
ImageNet weights. That constraint does not apply here — pretrained weights
download fine — so this is now one of two candidates evaluated against the same
bar rather than the only option. It is kept because colour genuinely is the
dominant signal for this problem, and a 1 MB classical model that matches a
pretrained CNN is the better artifact to serve.
"""

from __future__ import annotations

from pathlib import Path
from typing import IO, Union

import numpy as np
from PIL import Image
from scipy import ndimage

# Bump when the feature definition changes in any way that alters the vector:
# bin counts, image size, channel order, the texture window, or the ordering of
# the concatenation. Artifacts record the version they were trained under and
# serving refuses to load a mismatch.
FEATURE_VERSION = 1

IMG_SIZE = (128, 128)
_HSV_BINS = 16
_TEXTURE_WINDOW = 5

# 3 HSV channels x 16 bins, + texture mean/std, + RGB mean x3, + RGB std x3
FEATURE_COUNT = 3 * _HSV_BINS + 2 + 3 + 3

ImageSource = Union[str, Path, IO[bytes], Image.Image]


def extract_features(source: ImageSource) -> np.ndarray:
    """Return the feature vector for one soil image.

    Accepts a path, an open binary file object, or a PIL image. The file-object
    case is what makes an HTTP upload possible without first spilling the
    request body to a temporary file — the original path-only signature would
    have forced every caller to do that.
    """
    if isinstance(source, Image.Image):
        img = source.convert("RGB").resize(IMG_SIZE)
    else:
        with Image.open(source) as handle:
            img = handle.convert("RGB").resize(IMG_SIZE)

    rgb = np.asarray(img, dtype=np.float64) / 255.0
    hsv = np.asarray(img.convert("HSV"), dtype=np.float64) / 255.0

    features: list[float] = []

    for channel in range(3):
        hist, _ = np.histogram(hsv[:, :, channel], bins=_HSV_BINS, range=(0, 1))
        total = hist.sum()
        # A histogram of a uniform image sums to the pixel count, never zero,
        # but guard anyway rather than emit NaNs that only surface as a
        # confusing sklearn error several frames later.
        features.extend(hist / total if total else np.zeros(_HSV_BINS))

    gray = np.asarray(img.convert("L"), dtype=np.float64) / 255.0
    local_var = ndimage.generic_filter(gray, np.var, size=_TEXTURE_WINDOW)
    features.append(float(local_var.mean()))
    features.append(float(local_var.std()))

    features.extend(float(rgb[:, :, i].mean()) for i in range(3))
    features.extend(float(rgb[:, :, i].std()) for i in range(3))

    vector = np.asarray(features, dtype=np.float64)
    if vector.shape[0] != FEATURE_COUNT:  # pragma: no cover - guards a code edit
        raise AssertionError(
            f"Feature vector is {vector.shape[0]} long, expected {FEATURE_COUNT}. "
            f"If this was an intentional change, bump FEATURE_VERSION."
        )
    return vector


def image_digest(source: ImageSource) -> str:
    """Perceptual-ish digest used to find near-duplicate images across a split.

    Deliberately crude: an 8x8 grayscale average hash. It is not trying to catch
    every duplicate, only the case this dataset plausibly contains — the same
    photo resized, recompressed or lightly cropped appearing in both the train
    and test directories. At 295 images that alone can manufacture apparent
    accuracy, so it is checked rather than assumed.
    """
    if isinstance(source, Image.Image):
        img = source.convert("L").resize((8, 8))
    else:
        with Image.open(source) as handle:
            img = handle.convert("L").resize((8, 8))
    pixels = np.asarray(img, dtype=np.float64)
    bits = pixels > pixels.mean()
    return "".join("1" if b else "0" for b in bits.flatten())
