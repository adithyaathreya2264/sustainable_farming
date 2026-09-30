"""Wheat heading detection from a top-down canopy photo (model 14b).

## What it returns

`heading_detected` only: whether wheat heads cover at least 0.5% of the photo,
the fixed rule the bar measured. A growth-stage signal, for timing irrigation
and sprays around heading.

The model underneath (model 14) segments head, stem, leaf and background, but
its canopy-cover estimate failed its bar (MAE 0.0756 against 0.05), so **no
cover value, band or mask is returned**. Heading ships under bar 14b, which was
written after model 14's test read and is declared as such in MODEL_BARS.md.
The gate is the checkpoint's `heading_passed_bar`, not model 14's `passed_bar`.

Wheat is not a seeded app crop: every response carries `is_seeded_crop: False`.

## What it was trained on

GlobalWheat GWFSS (a 40% sample): top-down canopy photos from research sites.
A side-on phone photo, a single plant, or a non-wheat crop is outside what it
was measured on, and it will still return an answer. The response says so.
"""

from __future__ import annotations

import threading

from ml import paths
from ml.algorithms._loader import ModelDidNotShip
from ml.features.cnn import IMAGENET_MEAN, IMAGENET_STD, ImageSource, load_rgb
from ml.prep.common import SEEDED_CROPS, crop_key

INPUT_SIZE = 512

_state: dict = {}
_lock = threading.Lock()


def _load():
    with _lock:
        if "model" in _state:
            return _state["model"], _state["meta"]
        import torch

        from ml.training.train_wheat_segmentation import build_model

        path = paths.WHEAT_SEGMENTATION_MODEL
        if not path.exists():
            raise FileNotFoundError(
                f"{path.name} not found. Train it with "
                f"`python -m ml.training.train_wheat_segmentation`, then apply the "
                f"heading bar with `python -m ml.training.apply_wheat_heading_bar`."
            )
        checkpoint = torch.load(path, map_location="cpu", weights_only=False)
        if checkpoint.get("heading_passed_bar") is not True:
            raise ModelDidNotShip(
                f"{path.name} has not cleared bar 14b (heading detection) and must "
                f"not be served. See ml/MODEL_RESULTS.md."
            )
        model = build_model(pretrained=False)
        model.load_state_dict(checkpoint["state_dict"])
        model.eval()
        _state["model"], _state["meta"] = model, checkpoint
        return model, checkpoint


def detect_wheat_heading(source: ImageSource, crop: str = "wheat") -> dict:
    """Whether wheat heads are visible in a top-down canopy photo."""
    import torch
    from torchvision import transforms

    key = crop_key(crop)
    if key != "wheat":
        return {
            "crop": crop,
            "crop_key": key,
            "reason": "no_model_for_crop",
            "detail": "The heading model is trained on wheat only.",
        }

    model, meta = _load()
    head_index = meta["classes"].index("head")
    image = load_rgb(source).resize((INPUT_SIZE, INPUT_SIZE))
    x = transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD)(transforms.ToTensor()(image))
    with torch.no_grad():
        mask = model(x.unsqueeze(0))["out"][0].argmax(0)
    head_share = float((mask == head_index).float().mean())

    return {
        "crop": crop,
        "crop_key": key,
        "is_seeded_crop": key in SEEDED_CROPS,
        "heading_detected": head_share >= meta["head_rule"],
        "caveats": [
            "Provisional: trained on top-down research-site canopy photos. A "
            "side-on phone photo or a single plant is outside what was measured.",
            "No heads detected does not prove heading has not started; small "
            "early heads are the hardest to see.",
        ],
        "model": "wheat_heading_detection",
    }
