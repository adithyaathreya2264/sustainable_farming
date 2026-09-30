"""Insect pest detection from a photo (YOLOv8, model 11).

## What it was trained on, and what that implies

Tight 224x224 crops, one insect each, from the Roboflow RF100 "insects" set
(CC BY 4.0). It has never seen a small insect in a cluttered field photo and
has never seen an image with no insect in it. It will find insects in a
close-up. On a wide field shot or an empty leaf its behaviour is unmeasured.
Every response carries that caveat.

## Crop-aware, not crop-filtered

`crop` is required, as for every other photo model here. Each detection is
marked with `pest_of_this_crop`, from `ml/insect_pests.py`. A detection of a
pest that does not attack the farmer's crop is **flagged, not dropped**: it is
more likely a misidentification than a discovery, and the farmer should see it
was flagged rather than have it silently disappear.

## Output

Structured only. Each detection gives a stable `key`, the pest's `hosts`,
`related_rules` where an agronomic rule concerns the same pest (yellow stem
borer to `RICE_STEM_BORER_SCOUT`), a categorical `confidence_label`, and a box
in fractions of the image, 0-1, so the caller need not know what size the model
ran at.
"""

from __future__ import annotations

import json
import threading

from ml import paths
from ml.algorithms._loader import ModelDidNotShip
from ml.features.cnn import ImageSource, load_rgb
from ml.insect_pests import pest_for
from ml.labels import confidence_label
from ml.prep.common import crop_key

META_PATH = paths.ARTIFACTS_DIR / "insect_detector_meta.json"
MODEL_PATH = paths.ARTIFACTS_DIR / "insect_detector.pt"

_state: dict = {}
_lock = threading.Lock()


def _load():
    with _lock:
        if "model" in _state:
            return _state["model"], _state["meta"]
        if not META_PATH.exists() or not MODEL_PATH.exists():
            raise FileNotFoundError(
                "Insect detector not found. Train it with "
                "`python -m ml.training.train_insect_detector`."
            )
        meta = json.loads(META_PATH.read_text(encoding="utf-8"))
        if meta.get("passed_bar") is not True:
            raise ModelDidNotShip(
                "insect_detector.pt did not clear its acceptance bar and must not be "
                "served. See ml/MODEL_RESULTS.md."
            )
        from ultralytics import YOLO

        _state["model"], _state["meta"] = YOLO(str(MODEL_PATH)), meta
        return _state["model"], meta


def detect_insects(source: ImageSource, crop: str) -> dict:
    """Detect and identify insect pests in a photo of `crop`.

    `source` may be a path, an open binary file object, or a PIL image; phone
    EXIF rotation is corrected first.
    """
    model, meta = _load()
    image = load_rgb(source)
    width, height = image.size
    result = model.predict(
        image, imgsz=meta["imgsz"], conf=meta["serving_conf"], device="cpu", verbose=False
    )[0]
    names = meta["class_names"]
    key = crop_key(crop)

    detections = []
    for box, cls, conf in zip(result.boxes.xyxy.tolist(), result.boxes.cls.tolist(), result.boxes.conf.tolist()):
        pest = pest_for(names[int(cls)])
        x1, y1, x2, y2 = box
        detections.append(
            {
                "key": pest.key,
                "display_name": pest.display_name,
                "confidence_label": confidence_label(float(conf)),
                "pest_of_this_crop": key in pest.hosts,
                "hosts": list(pest.hosts),
                "hosts_verified": False,
                "related_rules": list(pest.related_rules),
                "box": {
                    "x1": round(x1 / width, 4),
                    "y1": round(y1 / height, 4),
                    "x2": round(x2 / width, 4),
                    "y2": round(y2 / height, 4),
                },
            }
        )
    detections.sort(key=lambda d: (not d["pest_of_this_crop"],))

    caveats = [
        "Provisional: trained on close-up photos with one insect each. Wide "
        "field photos, several insects, or a photo with no insect are outside "
        "what it was measured on.",
    ]
    if any(not d["pest_of_this_crop"] for d in detections):
        caveats.append(
            "A detected insect is not a known pest of this crop and may be a "
            "misidentification."
        )
    return {
        "crop": crop,
        "crop_key": key,
        "detections": detections,
        # "No detection", not "no insect": the model never saw an insect-free
        # image, so an empty result is not evidence that none is present.
        "no_detection": not detections,
        "caveats": caveats,
        "model": "insect_detector",
    }
