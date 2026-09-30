"""Soil type from a photograph.

## What changed from the inherited version

1. **Features are imported, not redefined.** `extract_features` previously
   existed twice — once here, once in the training script, byte-identical with
   nothing enforcing that. Tuning a histogram bin count during training would
   have silently desynchronised serving from the fitted model, and predictions
   would have kept flowing, just wrong ones. Both sides now import
   `ml/features/soil_image.py`, and the artifact records `FEATURE_VERSION` so a
   mismatch raises instead of mispredicting.

2. **Accepts bytes and file objects, not just paths.** The inherited signature
   took a filesystem path, which would have forced an HTTP upload handler to
   spill every request body to a temporary file first.

3. **Two candidates, the better one served.** MobileNetV3 transfer learning
   scored 0.9726 on the held-out test set against the classical model's 0.9178,
   so it is the default. `predict_soil_type(..., model="classical")` selects the
   1 MB alternative, which also cleared the bar and is materially smaller.

4. **Categorical confidence**, like every other model here.

## This is additive to the district lookup, never a replacement

The farmer already gets a soil type from their district via `soilLookup.js`.
This adds a second, independent signal. Where they disagree, that disagreement
is information for the caller to present — not something to resolve here by
overriding the region default.

## A caution about the test numbers

The source directories contain heavy duplication. 56 of 295 training images
were near-duplicates of test images and were removed before fitting; the
remaining 239 training images are only 183 distinct photographs. The test set
is 73 images, of which 6 are Cinder. These scores are honest but they rest on a
small, duplicate-ridden sample.
"""

from __future__ import annotations

import numpy as np

from ml import paths
from ml.algorithms._loader import load_artifact
from ml.features.soil_image import FEATURE_VERSION, ImageSource, extract_features
from ml.labels import confidence_label

CLASSICAL = "classical"
CNN = "mobilenetv3"


def _classical_bundle() -> dict:
    bundle = load_artifact(paths.SOIL_TYPE_MODEL)
    stored = bundle.get("feature_version")
    if stored != FEATURE_VERSION:
        raise RuntimeError(
            f"soil_type_model.pkl was trained with feature version {stored}, but "
            f"ml/features/soil_image.py is now version {FEATURE_VERSION}. The "
            f"feature definition changed since this model was fitted - retrain "
            f"with `python -m ml.training.train_soil_type_model` rather than "
            f"serving a mismatch."
        )
    return bundle


def _cnn():
    """Load the MobileNetV3 candidate. Imported lazily - torch is heavy."""
    import torch

    from ml.features.cnn import build_mobilenet_v3, soil_eval_transform

    path = paths.require(paths.SOIL_TYPE_CNN_MODEL)
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    classes = checkpoint["classes"]

    # Transform and network come from ml/features/cnn.py, the same definitions
    # the training script uses, rather than a second hand-written copy.
    model = build_mobilenet_v3("mobilenet_v3_small", len(classes), pretrained=False)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model, soil_eval_transform(), classes


_cnn_cache = None


def predict_soil_type(source: ImageSource, model: str = CNN) -> dict:
    """Classify a soil photograph.

    `source` may be a path, an open binary file object, or a PIL image.
    """
    if model == CLASSICAL:
        bundle = _classical_bundle()
        estimator = bundle["model"]
        features = extract_features(source).reshape(1, -1)
        probabilities = estimator.predict_proba(features)[0]
        classes = list(estimator.classes_)
    elif model == CNN:
        global _cnn_cache
        import torch
        from PIL import Image

        if _cnn_cache is None:
            _cnn_cache = _cnn()
        net, transform, classes = _cnn_cache

        if isinstance(source, Image.Image):
            image = source.convert("RGB")
        else:
            with Image.open(source) as handle:
                image = handle.convert("RGB")
        with torch.no_grad():
            logits = net(transform(image).unsqueeze(0))
            probabilities = torch.softmax(logits, dim=1)[0].numpy()
    else:
        raise ValueError(f"model must be {CLASSICAL!r} or {CNN!r}, got {model!r}")

    order = np.argsort(probabilities)[::-1]
    best = int(order[0])
    return {
        "predicted_soil_type": str(classes[best]),
        "confidence_label": confidence_label(float(probabilities[best])),
        "ranked": [
            {
                "soil_type": str(classes[i]),
                "confidence_label": confidence_label(float(probabilities[i])),
            }
            for i in order
        ],
        "model": model,
        "note": (
            "Additive to the district-based soil lookup, not a replacement. "
            "Trained on 183 distinct images across 4 classes; Cinder Soil has "
            "only 6 test images and its accuracy is correspondingly uncertain."
        ),
    }
