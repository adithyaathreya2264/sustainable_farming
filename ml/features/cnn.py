"""Image preprocessing and network construction shared by training and serving.

## Why this module exists

Every transform defined here was, or would have been, defined twice: once in a
training script and once in the matching serving module. The soil-type CNN
shipped on 2026-09-22 did exactly that — its eval transform was written out in
`train_soil_type_model.py` and again in `soil_type_prediction.py`, identical
only by care. That is the same hazard `ml/features/soil_image.py` was created to
remove for the classical features: change one copy and the model keeps
answering, just about slightly different pixels than it was measured on.

## Canonical leaf preprocessing

Leaf models go through one function, `prepare_leaf_image`, in both paths:

    source -> EXIF-correct -> RGB -> resize to PREP_SIZE x PREP_SIZE

Training caches its output as lossless PNG, which makes epochs fast — decoding a
1024x768 JPEG costs far more than the network on a 256px input. Serving calls
the same function on the uploaded photo. Because the cache is lossless, the
pixels a served photo produces are identical to what training saw for the same
file. A lossy JPEG cache would have reintroduced a small, silent skew.

**EXIF orientation matters for real users.** Phone cameras frequently store the
image sideways and record the rotation in EXIF metadata instead of rotating the
pixels. The dataset photos are upright; a farmer's upload may not be. Without
`exif_transpose`, the model would sometimes see leaves on their side.
"""

from __future__ import annotations

from pathlib import Path
from typing import IO, Union

import numpy as np
from PIL import Image, ImageOps

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

# Leaf models: photos are first normalised to PREP_SIZE, then cropped or
# resized to INPUT_SIZE for the network.
PREP_SIZE = 256
INPUT_SIZE = 224

# Bump if prepare_leaf_image or the leaf transforms change in any way that
# alters pixels. Artifacts record it and serving refuses a mismatch.
LEAF_PREPROCESS_VERSION = 1

ImageSource = Union[str, Path, IO[bytes], Image.Image]


try:  # .heic support (tea dataset); optional so serving never depends on it
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:  # pragma: no cover
    pass


def load_rgb(source: ImageSource) -> Image.Image:
    """Open any supported source as an upright RGB image."""
    if isinstance(source, Image.Image):
        image = source
    else:
        with Image.open(source) as handle:
            image = handle.copy()
    return ImageOps.exif_transpose(image).convert("RGB")


def prepare_leaf_image(source: ImageSource) -> Image.Image:
    """Canonical leaf preprocessing. Training caches this; serving calls it."""
    return load_rgb(source).resize((PREP_SIZE, PREP_SIZE), Image.Resampling.BICUBIC)


def leaf_train_transform():
    """Augmentation for the leaf models, applied only inside the training fold.

    Rotations and flips in every direction are realistic here: a leaf has no
    canonical orientation in a hand-held photo. Colour jitter is kept moderate
    because colour carries diagnostic signal — yellowing, reddening and rust
    are the point — so aggressive hue shifts would destroy the evidence.
    """
    from torchvision import transforms

    return transforms.Compose(
        [
            transforms.RandomResizedCrop(INPUT_SIZE, scale=(0.6, 1.0)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomVerticalFlip(),
            transforms.RandomRotation(30),
            transforms.ColorJitter(brightness=0.25, contrast=0.25, saturation=0.15, hue=0.02),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )


def leaf_eval_transform():
    from torchvision import transforms

    return transforms.Compose(
        [
            transforms.Resize((INPUT_SIZE, INPUT_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )


# --------------------------------------------------------------------------
# Soil-type CNN transforms, moved here unchanged from the two places they were
# defined. The shipped soil artifact was trained with exactly these, so moving
# them does not require retraining.
# --------------------------------------------------------------------------


def soil_train_transform():
    from torchvision import transforms

    return transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(20),
            transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )


def soil_eval_transform():
    from torchvision import transforms

    return transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )


# --------------------------------------------------------------------------
# Networks
# --------------------------------------------------------------------------


def build_mobilenet_v3(arch: str, num_classes: int, *, pretrained: bool):
    """MobileNetV3 with its final layer replaced for `num_classes`.

    `pretrained=False` is used when loading a trained artifact: the weights come
    from the checkpoint, so fetching ImageNet weights would be wasted work and
    would make serving depend on network access.
    """
    from torch import nn
    from torchvision.models import (
        MobileNet_V3_Large_Weights,
        MobileNet_V3_Small_Weights,
        mobilenet_v3_large,
        mobilenet_v3_small,
    )

    if arch == "mobilenet_v3_large":
        model = mobilenet_v3_large(weights=MobileNet_V3_Large_Weights.DEFAULT if pretrained else None)
    elif arch == "mobilenet_v3_small":
        model = mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.DEFAULT if pretrained else None)
    else:
        raise ValueError(f"unknown architecture {arch!r}")
    model.classifier[3] = nn.Linear(model.classifier[3].in_features, num_classes)
    return model


# --------------------------------------------------------------------------
# Near-duplicate detection
# --------------------------------------------------------------------------


def dihedral_digest(image: Image.Image, hash_size: int = 16) -> str:
    """Average hash that is identical for an image and its flips and rotations.

    Computed under all 8 flips and 90-degree rotations and the smallest kept,
    so a photo and a mirrored or rotated copy of it land in the same group.
    That matters for public datasets, which often contain "augmented" copies
    mixed in with originals, and a flipped copy is invisible to a plain hash.

    16x16 rather than the 8x8 used for soil: leaf photos are far more uniform
    than soil photos (a green leaf, centred, on a similar background), and 64
    bits collide between genuinely different leaves often enough to merge
    unrelated images into one group. 256 bits still survives resizing and
    recompression.
    """
    gray = np.asarray(
        image.convert("L").resize((hash_size, hash_size), Image.Resampling.BILINEAR),
        dtype=np.float64,
    )
    variants = []
    for k in range(4):
        rotated = np.rot90(gray, k)
        variants.append(rotated)
        variants.append(np.fliplr(rotated))
    bits = ["".join("1" if b else "0" for b in (v > v.mean()).flatten()) for v in variants]
    return min(bits)
