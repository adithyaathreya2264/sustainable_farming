"""Leaf condition from a photo — sugarcane and rice.

## The crop argument is required

One model per crop, chosen by the crop the app already knows from the planting
the photo belongs to. The same reasoning as crop-scoped disease Q&A (bar 4b):
a combined model would first have to tell rice from sugarcane, a problem the
app never needs solved, and would mislabel across crops when it failed.

Ragi, maize and cotton have no model. For them this returns
`reason: "no_model_for_crop"` instead of raising, so the caller can fall back to
the crop-scoped disease Q&A. That gap is documented in
`ml/UNBLOCKING_PARKED_MODELS.md`.

## Rice is conditional

The rice dataset has no healthy class, so its model names one of four diseases
for *any* rice leaf. It is served only with `symptom_reported=True`, after the
farmer has reported a problem, and its responses carry
`offer_none_of_these: True` and `can_say_healthy: False`. Without the flag the
call returns `reason: "symptom_required"`. See MODEL_BARS.md, model 12.

Whether any of these models is actually served is decided by its artifact's
`passed_bar` flag, not by this list. Models that failed their bars raise
`ModelDidNotShip`.

## What the model cannot know

It always names one of its classes. Photograph a rice leaf and pass
`crop="sugarcane"`, or photograph a hand, and it will still return a confident
sugarcane condition. Nothing in the training data teaches it to say "this is
not a leaf of the crop I know". The confidence label narrows the risk but does
not remove it, and the response says so.

## Output

Structured only, for the same reasons as every other model here — the app
localises, so no prose is composed in this layer:

- `condition.key` — a stable identifier (`brown_rust`), never the dataset's
  raw folder name.
- `condition.category` — `healthy`, `disease`, `pest_damage`, `abiotic` or
  `unclassified`. This is what lets the app avoid recommending a fungicide
  for herbicide injury. It comes from `ml/leaf_conditions.py`, is not
  agronomist-reviewed, and carries `category_verified: false`.
- `condition.qa_disease` — for classes that are unambiguously the same disease
  as a Q&A corpus entry, the name to pass to
  `disease_info_retrieval.find_disease_info` for documented remedies. `None`
  otherwise, and never a mere resemblance.
- a categorical `confidence_label`, never a probability.
"""

from __future__ import annotations

import threading

import numpy as np

from ml import paths
from ml.algorithms._loader import ModelDidNotShip
from ml.features.cnn import (
    LEAF_PREPROCESS_VERSION,
    ImageSource,
    build_mobilenet_v3,
    leaf_eval_transform,
    prepare_leaf_image,
)
from ml.labels import confidence_label
from ml.leaf_conditions import CONDITIONAL_CROPS, LEAF_CONDITIONS, SUPPORTED_CROPS, condition_for
from ml.prep.common import SEEDED_CROPS, crop_key

TOP_K = 3

_models: dict[str, tuple] = {}
_lock = threading.Lock()


def _load(crop: str):
    with _lock:
        if crop in _models:
            return _models[crop]

        import torch

        path = paths.leaf_condition_model(crop)
        if not path.exists():
            raise FileNotFoundError(
                f"{path.name} not found. Train it with "
                f"`python -m ml.training.train_leaf_condition_model --crop {crop}`."
            )
        checkpoint = torch.load(path, map_location="cpu", weights_only=False)

        if checkpoint.get("passed_bar") is not True:
            raise ModelDidNotShip(
                f"{path.name} did not clear its acceptance bar and must not be served. "
                f"See ml/MODEL_RESULTS.md."
            )
        if checkpoint.get("preprocess_version") != LEAF_PREPROCESS_VERSION:
            raise RuntimeError(
                f"{path.name} was trained with leaf preprocessing version "
                f"{checkpoint.get('preprocess_version')}, but ml/features/cnn.py is now "
                f"version {LEAF_PREPROCESS_VERSION}. Retrain rather than serve a mismatch."
            )

        classes = checkpoint["classes"]
        model = build_mobilenet_v3(checkpoint["architecture"], len(classes), pretrained=False)
        model.load_state_dict(checkpoint["state_dict"])
        model.eval()
        _models[crop] = (model, classes, leaf_eval_transform())
        return _models[crop]


def _describe(crop: str, folder: str, probability: float) -> dict:
    condition = condition_for(crop, folder)
    return {
        "key": condition.key,
        "display_name": condition.display_name,
        "category": condition.category,
        "category_verified": False,
        "qa_disease": condition.qa_disease,
        "confidence_label": confidence_label(probability),
    }


def supported_crops() -> list[str]:
    return list(SUPPORTED_CROPS)


def diagnose_leaf(
    source: ImageSource, crop: str, top_k: int = TOP_K, *, symptom_reported: bool = False
) -> dict:
    """Classify a leaf photo of `crop`.

    `source` may be a path, an open binary file object (an HTTP upload), or a
    PIL image. Phone-camera EXIF rotation is corrected before classification.

    `symptom_reported` is required for crops whose model has no healthy class
    (rice). Such a model names one of its diseases for *every* leaf, healthy
    ones included, so it may only be asked "which disease?" after the farmer
    has already reported a problem. See MODEL_BARS.md, model 12.
    """
    key = crop_key(crop)
    if key not in LEAF_CONDITIONS:
        return {
            "crop": crop,
            "crop_key": key,
            "condition": None,
            "alternatives": [],
            "reason": "no_model_for_crop",
            "detail": (
                f"No leaf-photo model exists for {crop!r}. Supported: "
                f"{list(SUPPORTED_CROPS)}. Use the crop-scoped disease Q&A instead."
            ),
        }

    # Explicit list, not "no healthy class": tomato fruit grading has no
    # healthy class but a grade applies to every fruit.
    conditional = key in CONDITIONAL_CROPS
    if conditional and not symptom_reported:
        return {
            "crop": crop,
            "crop_key": key,
            "condition": None,
            "alternatives": [],
            "reason": "symptom_required",
            "detail": (
                f"The {key} model has no healthy class, so it would name a disease "
                f"for a healthy leaf. Call it only after a symptom has been "
                f"reported, with symptom_reported=True."
            ),
        }

    import torch

    model, classes, transform = _load(key)
    image = prepare_leaf_image(source)
    with torch.no_grad():
        probabilities = torch.softmax(model(transform(image).unsqueeze(0)), dim=1)[0].numpy()

    order = np.argsort(probabilities)[::-1][:top_k]
    ranked = [_describe(key, classes[i], float(probabilities[i])) for i in order]
    top = ranked[0]

    caveats = [
        "Provisional: trained and tested on images from a single public dataset "
        "per crop. Photos taken in the field under different light, background "
        "and camera will be less accurate than the measured figures.",
        "The model cannot recognise a photo of the wrong crop or of something "
        "that is not a leaf; it will still name one of its conditions.",
    ]
    if conditional:
        caveats.append(
            "This model only distinguishes between the diseases it knows. It "
            "cannot tell a healthy leaf, a nutrient deficiency or any other "
            "condition from them, and will name one of its diseases regardless. "
            "'None of these' must stay available as an answer."
        )
    if top["category"] == "healthy":
        caveats.append(
            "A 'healthy' result is not a guarantee. If symptoms are visible, "
            "check the other listed conditions or consult an extension officer."
        )

    return {
        "crop": crop,
        "crop_key": key,
        "condition": top,
        "alternatives": ranked[1:],
        "caveats": caveats,
        "model": f"leaf_condition_{key}",
        # For conditional models the UI must offer "none of these / something
        # else" alongside the ranked diseases; it is part of the serving
        # contract, not an optional nicety.
        "offer_none_of_these": conditional,
        "is_seeded_crop": key in SEEDED_CROPS,
        "can_say_healthy": not conditional,
    }
