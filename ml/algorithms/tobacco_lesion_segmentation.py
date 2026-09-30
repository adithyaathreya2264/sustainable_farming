"""Tobacco leaf lesion severity from a close-up photo (model 17).

## What it returns

`lesion_area_percent`: the share of the photographed leaf surface covered by
lesions, to one decimal place. The bar measured this per-tile share against a
constant baseline (MODEL_BARS.md, model 17). No disease is named, because the
training masks do not name one, and no severity class is attached: there is no
reviewed scale to map percentages onto.

Tobacco is not a seeded app crop: every response carries
`is_seeded_crop: False`.

## What it was trained on

Close-up 800x800 tiles of tobacco leaves, photographed on two days in October
2023 from one source. A whole-leaf photo, a different crop, or a different
camera is outside what was measured.
"""

from __future__ import annotations

import threading

from ml import paths
from ml.algorithms._loader import ModelDidNotShip
from ml.features.cnn import IMAGENET_MEAN, IMAGENET_STD, ImageSource, load_rgb
from ml.prep.common import SEEDED_CROPS, crop_key

INPUT_SIZE = 800

_state: dict = {}
_lock = threading.Lock()


def _load():
    with _lock:
        if "model" in _state:
            return _state["model"], _state["meta"]
        import torch

        from ml.training.train_wheat_segmentation import build_model

        path = paths.TOBACCO_LESION_MODEL
        if not path.exists():
            raise FileNotFoundError(
                f"{path.name} not found. Train it with "
                f"`python -m ml.training.train_tobacco_lesion_segmentation`."
            )
        checkpoint = torch.load(path, map_location="cpu", weights_only=False)
        if checkpoint.get("passed_bar") is not True:
            raise ModelDidNotShip(
                f"{path.name} did not clear its acceptance bar and must not be served. "
                f"See ml/MODEL_RESULTS.md."
            )
        model = build_model(pretrained=False, num_classes=len(checkpoint["classes"]))
        model.load_state_dict(checkpoint["state_dict"])
        model.eval()
        _state["model"], _state["meta"] = model, checkpoint
        return model, checkpoint


def measure_tobacco_lesions(source: ImageSource, crop: str = "tobacco") -> dict:
    """Percentage of a close-up tobacco leaf photo covered by lesions."""
    import torch
    from torchvision import transforms

    key = crop_key(crop)
    if key != "tobacco":
        return {
            "crop": crop,
            "crop_key": key,
            "reason": "no_model_for_crop",
            "detail": "The lesion model is trained on tobacco only.",
        }

    model, meta = _load()
    lesion = meta["classes"].index("lesion")
    image = load_rgb(source).resize((INPUT_SIZE, INPUT_SIZE))
    x = transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD)(transforms.ToTensor()(image))
    with torch.no_grad():
        mask = model(x.unsqueeze(0))["out"][0].argmax(0)
    share = float((mask == lesion).float().mean())

    return {
        "crop": crop,
        "crop_key": key,
        "is_seeded_crop": key in SEEDED_CROPS,
        "lesion_area_percent": round(100 * share, 1),
        "caveats": [
            "Provisional: trained on close-up tiles from one source over two days. "
            "Whole-leaf photos and other cameras are outside what was measured.",
            "The disease is not identified; this is lesion area only.",
        ],
        "model": "tobacco_lesion_segmentation",
    }
