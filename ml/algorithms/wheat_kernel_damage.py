"""Sunn-pest damage in a photo of wheat kernels (model 28).

Takes a close photo of a heap of harvested wheat grain and says whether the
kernels show sunn-pest (Eurygaster) feeding damage. The photo is resized to
1536 px wide and scored as the mean over a grid of 384 px crops, exactly as
the model was measured. Not a field or plant photo: a grain sample.

Served only if the artifact cleared its bar (MODEL_RESULTS.md section 28).
Trained on six Turkish cultivars under one lab setup, so provisional.
"""

from __future__ import annotations

import threading

from ml import paths
from ml.algorithms._loader import ModelDidNotShip
from ml.features.cnn import ImageSource, build_mobilenet_v3, load_rgb
from ml.labels import confidence_label
from ml.prep.common import SEEDED_CROPS, crop_key

_state: dict = {}
_lock = threading.Lock()


def _load():
    with _lock:
        if "model" not in _state:
            import torch

            path = paths.WHEAT_KERNEL_MODEL
            if not path.exists():
                raise FileNotFoundError(
                    f"{path.name} not found. Train it with `python -m ml.training.train_wheat_kernel_damage`."
                )
            checkpoint = torch.load(path, map_location="cpu", weights_only=False)
            if checkpoint.get("passed_bar") is not True:
                raise ModelDidNotShip(f"{path.name} did not clear its acceptance bar. See ml/MODEL_RESULTS.md.")
            model = build_mobilenet_v3(checkpoint["architecture"], len(checkpoint["classes"]), pretrained=False)
            model.load_state_dict(checkpoint["state_dict"])
            model.eval()
            _state["model"], _state["meta"] = model, checkpoint
        return _state["model"], _state["meta"]


def assess_wheat_kernels(source: ImageSource, crop: str = "wheat") -> dict:
    """Damaged or healthy, for a photo of a wheat grain sample."""
    from PIL import Image

    from ml.training.train_wheat_kernel_damage import _predict

    key = crop_key(crop)
    if key != "wheat":
        return {"crop": crop, "crop_key": key, "reason": "no_model_for_crop",
                "detail": "The kernel model is trained on wheat grain only."}

    model, meta = _load()
    image = load_rgb(source)
    height = round(image.height * meta["cache_width"] / image.width)
    image = image.resize((meta["cache_width"], height), Image.Resampling.BICUBIC)
    probabilities = _predict(model, [image])[0]
    best = int(probabilities.argmax())
    return {
        "crop": crop,
        "crop_key": key,
        "is_seeded_crop": key in SEEDED_CROPS,
        "kernel_condition": meta["classes"][best],
        "confidence_label": confidence_label(float(probabilities[best])),
        "caveats": [
            "Provisional: trained on grain photos of six Turkish wheat cultivars under one lab setup.",
            "Photograph a spread of kernels on a plain surface, not the standing crop.",
        ],
        "model": "wheat_kernel_damage",
    }
