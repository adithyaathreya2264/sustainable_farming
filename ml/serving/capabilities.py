"""What each crop can be offered, and the model roster, from artifact metadata.

Everything here reads small JSON/pickle metadata and the registries in `ml/` -
never a torch checkpoint - so `/v1/capabilities` is cheap enough to call on
every screen load. Crop lists are derived from the registries and artifacts,
not written out here, so a retrain or a new registry entry changes the answer
without an edit to this file.
"""

from __future__ import annotations

import json
from functools import lru_cache

from ml import paths
from ml.insect_pests import INSECT_PESTS
from ml.leaf_conditions import CONDITIONAL_CROPS, SUPPORTED_CROPS as LEAF_CROPS
from ml.prep.common import crop_key
from ml.serving import holds

WHEAT = "wheat"
TOBACCO = "tobacco"

# Photo checks served by the leaf-condition pipeline, one per part of the
# plant or produce. A part is offered for a crop when the registry has an
# entry "<crop key><suffix>" (ml/leaf_conditions.py) and its artifact shipped,
# so a new registry entry needs no edit here.
PHOTO_PARTS = {
    "leaf_diagnosis": "",          # coffee, tea, cauliflower, onion, potato, rice, pearl millet
    "curd_diagnosis": " curd",     # cauliflower curd (model 23)
    "bulb_diagnosis": " bulb",     # onion bulb (model 25)
    "fruit_grade": " fruit",       # tomato fruit grade (model 27)
}


def _flags(path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _leaf_shipped(crop: str) -> bool | None:
    metrics = paths.leaf_condition_model(crop).with_name(
        paths.leaf_condition_model(crop).stem + "_metrics.json"
    )
    if not metrics.exists():
        return None
    return _flags(metrics).get("passed_bar") is True


def _insects_shipped() -> bool:
    return _flags(paths.ARTIFACTS_DIR / "insect_detector_meta.json").get("passed_bar") is True


def _wheat_heading_shipped() -> bool:
    return _flags(paths.ARTIFACTS_DIR / "wheat_canopy_segmentation_metrics.json").get("heading_passed_bar") is True


def _tobacco_shipped() -> bool:
    return _flags(paths.ARTIFACTS_DIR / "tobacco_lesion_segmentation_metrics.json").get("passed_bar") is True


def _wheat_kernels_shipped() -> bool | None:
    metrics = paths.ARTIFACTS_DIR / "wheat_kernel_damage_metrics.json"
    if not metrics.exists():
        return None
    return _flags(metrics).get("passed_bar") is True


@lru_cache(maxsize=1)
def _disease_crop_keys() -> frozenset:
    from ml.algorithms.disease_info_retrieval import known_crops

    return frozenset(crop_key(c) for c in known_crops())


@lru_cache(maxsize=1)
def _fertilizer_keys() -> frozenset:
    from ml.algorithms.fertilizer_recommendation import _targets

    return frozenset(_targets())


def yield_crop_name(key: str) -> str | None:
    """The yield model's own spelling for an app crop key (Bajra, Cotton(lint), ...)."""
    from ml.algorithms.yield_prediction import yield_crop_names

    for name in yield_crop_names():
        if crop_key(name) == key:
            return name
    return None


def price_commodities_for(key: str) -> list[dict]:
    """Commodities that are this crop's produce: by the artifact's app mapping,
    or by the commodity's own crop key (bajra -> pearl millet, wheat -> wheat)."""
    from ml.algorithms.price_forecast import supported_commodities

    return [
        c for c in supported_commodities()
        if c["app_crop"] == key or crop_key(c["commodity"]) == key
    ]


def _entry(available: bool, reason: str | None = None, **extra) -> dict:
    out = {"available": bool(available), **extra}
    if not available and reason:
        out["reason"] = reason
    return out


def capabilities(crop: str) -> dict:
    key = crop_key(crop)
    caps: dict[str, dict] = {}

    # Photo checks served by the leaf pipeline, one entry per part.
    for name, suffix in PHOTO_PARTS.items():
        model_key = f"{key}{suffix}"
        if model_key in LEAF_CROPS:
            shipped = _leaf_shipped(model_key)
            caps[name] = _entry(
                shipped is True,
                "model_did_not_ship" if shipped is False else "artifact_missing",
                conditional=model_key in CONDITIONAL_CROPS,
                model_key=model_key,
            )
        else:
            caps[name] = _entry(False, "no_model_for_crop")

    hosts = {h for pest in INSECT_PESTS.values() for h in pest.hosts}
    caps["insect_detection"] = _entry(
        key in hosts and _insects_shipped(),
        "no_model_for_crop" if key not in hosts else "model_did_not_ship",
    )
    caps["wheat_heading"] = _entry(
        key == WHEAT and _wheat_heading_shipped(),
        "no_model_for_crop" if key != WHEAT else "model_did_not_ship",
    )
    if key != WHEAT:
        caps["wheat_kernels"] = _entry(False, "no_model_for_crop")
    elif "wheat_kernels" in holds.HELD:
        caps["wheat_kernels"] = _entry(False, holds.HELD["wheat_kernels"][0])
    else:
        shipped = _wheat_kernels_shipped()
        caps["wheat_kernels"] = _entry(
            shipped is True, "model_did_not_ship" if shipped is False else "artifact_missing"
        )
    caps["tobacco_lesions"] = _entry(
        key == TOBACCO and _tobacco_shipped(),
        "no_model_for_crop" if key != TOBACCO else "model_did_not_ship",
    )

    # Tabular / retrieval
    caps["disease_info"] = _entry(key in _disease_crop_keys(), "no_coverage_for_crop")
    caps["fertilizer"] = _entry(key in _fertilizer_keys(), "no_nutrient_target")
    caps["yield_outlook"] = _entry(yield_crop_name(key) is not None, "no_yield_history")

    commodities = price_commodities_for(key)
    caps["price"] = _entry(
        bool(commodities),
        "no_price_series",
        commodities=commodities,
    )
    return {"crop": crop, "crop_key": key, "capabilities": caps}


def roster() -> list[dict]:
    """Every model the app could reach, with its ship status from artifact metadata."""
    from ml.algorithms import _loader

    def pkl_status(path) -> str:
        if not path.exists():
            return "artifact_missing"
        try:
            bundle = _loader.load_artifact(path, enforce_bar=False)
        except Exception:  # noqa: BLE001
            return "unreadable"
        return "refused" if isinstance(bundle, dict) and bundle.get("passed_bar") is False else "shipped"

    def flag_status(ok: bool | None) -> str:
        return {True: "shipped", False: "refused", None: "artifact_missing"}[ok]

    models = [
        {"id": "crop_recommendation", "number": "1", "status": pkl_status(paths.CROP_RECOMMENDATION_MODEL)},
        {"id": "crop_soil_type", "number": "2", "status": pkl_status(paths.CROP_SOIL_TYPE_MODEL)},
        {"id": "fertilizer_targets", "number": "3",
         "status": "shipped" if paths.FERTILIZER_TARGETS.exists() else "artifact_missing"},
        {"id": "disease_qa_crop_scoped", "number": "4b", "status": pkl_status(paths.DISEASE_QA_INDEX)},
        # 5b is crop-independent (a soil property), so it is in the roster but
        # not in per-crop capabilities. Model 5 (soil_fertility_model.pkl)
        # failed its bar and is deliberately absent.
        {"id": "soil_fertility", "number": "5b", "status": pkl_status(paths.SOIL_FERTILITY_V2_MODEL)},
        {"id": "yield_percentile", "number": "6", "status": pkl_status(paths.YIELD_MODEL)},
        {"id": "soil_type_photo", "number": "7b",
         "status": "shipped" if (paths.ARTIFACTS_DIR / "soil_type_cnn_model.pt").exists() else "artifact_missing"},
        {"id": "leaf_condition_sugarcane", "number": "10", "status": flag_status(_leaf_shipped("sugarcane"))},
        {"id": "insect_detector", "number": "11", "status": flag_status(_insects_shipped() if (paths.ARTIFACTS_DIR / "insect_detector_meta.json").exists() else None)},
        {"id": "leaf_condition_rice", "number": "12", "status": flag_status(_leaf_shipped("rice"))},
        {"id": "leaf_condition_pearl_millet", "number": "13", "status": flag_status(_leaf_shipped("pearl millet"))},
        {"id": "wheat_heading", "number": "14b", "status": flag_status(_wheat_heading_shipped() if paths.WHEAT_SEGMENTATION_MODEL.exists() else None)},
        {"id": "tobacco_lesions", "number": "17", "status": flag_status(_tobacco_shipped() if paths.TOBACCO_LESION_MODEL.exists() else None)},
        {"id": "price_forecast", "number": "18",
         "status": "shipped" if paths.PRICE_FORECAST_MODEL.exists() else "artifact_missing"},
        *[
            {"id": f"leaf_condition_{key.replace(' ', '_')}", "number": number,
             "status": flag_status(_leaf_shipped(key))}
            for number, key in (
                ("20", "coffee"), ("21", "tea"), ("22", "cauliflower"), ("23", "cauliflower curd"),
                ("24", "onion"), ("25", "onion bulb"), ("26", "potato"), ("27", "tomato fruit"),
            )
        ],
        # Cleared its bar; withheld from serving by ml/serving/holds.py.
        {"id": "wheat_kernel_damage", "number": "28",
         "status": "held" if "wheat_kernels" in holds.HELD else flag_status(_wheat_kernels_shipped())},
    ]
    return models


def model_classes(model_id: str) -> list[str]:
    """App crop keys a crop-recommendation model can ever return."""
    from ml.algorithms import crop_recommendation as cr

    if model_id == "crop_recommendation":
        labels = cr._npk_bundle()["classes"]
    elif model_id == "crop_soil_type":
        labels = cr._soil_bundle()["model"].classes_
    else:
        raise ValueError(f"no class list for {model_id!r}")
    return sorted({crop_key(str(label)) for label in labels})
