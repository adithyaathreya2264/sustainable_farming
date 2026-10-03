"""Serving-boundary tests for the ML sidecar.

Run from the repo root:

    .venv/Scripts/python.exe -m pytest ml/serving/tests -q

These load the real artifacts (tabular models load in seconds; image models
are exercised on one dataset image each and skipped when the raw dataset is
absent). They check the contract Node depends on - status codes, `reason`
values, and that nothing internal or probability-like leaves the process -
not model quality, which MODEL_RESULTS.md already records.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from ml import paths
from ml.serving.app import app
from ml.serving.sanitize import LeakedProbability, public

client = TestClient(app)

WEATHER = {"temperature": 25, "humidity": 70, "ph": 6.5, "rainfall": 150}
FORBIDDEN = ("probability", "_raw", '"score"', "proba")


def _clean(response) -> dict:
    text = response.text
    for token in FORBIDDEN:
        assert token not in text, f"{token!r} crossed the serving boundary"
    return response.json()


def _first_image(root: Path, pattern: str = "*.jp*g") -> Path | None:
    if not root.exists():
        return None
    return next(iter(sorted(root.rglob(pattern))), None)


def _jpeg_bytes(size=(64, 64)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (120, 90, 60)).save(buffer, format="JPEG")
    return buffer.getvalue()


# --- sanitize ---------------------------------------------------------------

def test_sanitize_strips_private_keys_and_blocks_probabilities():
    assert public({"a": 1, "_raw_model_output": 2.5, "nested": [{"_x": 1, "y": 2}]}) == {
        "a": 1,
        "nested": [{"y": 2}],
    }
    with pytest.raises(LeakedProbability):
        public({"probability": 0.87})


# --- meta -------------------------------------------------------------------

def test_health_and_roster():
    assert client.get("/health").json() == {"status": "ok"}
    roster = {m["id"]: m["status"] for m in _clean(client.get("/v1/models"))["models"]}
    assert roster["leaf_condition_sugarcane"] == "refused"
    assert roster["soil_fertility"] == "shipped"
    assert roster["wheat_kernel_damage"] == "held"
    assert sum(status == "shipped" for status in roster.values()) == 21


@pytest.mark.parametrize(
    "crop, expected",
    [
        ("rice", {"leaf_diagnosis", "insect_detection", "disease_info", "fertilizer", "yield_outlook", "price"}),
        ("sugarcane", {"disease_info", "yield_outlook", "price"}),
        ("wheat", {"wheat_heading", "insect_detection", "disease_info", "yield_outlook", "price"}),
        ("tobacco", {"tobacco_lesions", "yield_outlook"}),
        ("Pearl Millet (Bajra)", {"leaf_diagnosis", "yield_outlook", "price"}),
        # Models 20-27 (2026-09-26): one entry per part, derived from the registry.
        ("coffee", {"leaf_diagnosis", "fertilizer"}),
        ("tea", {"leaf_diagnosis"}),
        ("cauliflower", {"leaf_diagnosis", "curd_diagnosis", "fertilizer"}),
        ("onion", {"leaf_diagnosis", "bulb_diagnosis", "disease_info", "fertilizer", "yield_outlook"}),
        ("potato", {"leaf_diagnosis", "disease_info", "fertilizer", "yield_outlook"}),
        ("tomato", {"fruit_grade", "disease_info", "fertilizer"}),
    ],
)
def test_capabilities(crop, expected):
    caps = _clean(client.get("/v1/capabilities", params={"crop": crop}))["capabilities"]
    assert {name for name, entry in caps.items() if entry["available"]} == expected


def test_sugarcane_leaf_is_refused_as_did_not_ship():
    caps = client.get("/v1/capabilities", params={"crop": "sugarcane"}).json()["capabilities"]
    assert caps["leaf_diagnosis"]["reason"] == "model_did_not_ship"


# --- tabular ----------------------------------------------------------------

def test_crop_recommendation_npk():
    body = _clean(client.post("/v1/crop-recommendation", json={"N": 90, "P": 42, "K": 43, **WEATHER}))
    assert body["recommended"]["confidence_label"] in {"unverified", "provisional"}
    assert len(body["alternatives"]) == 3


def test_crop_recommendation_soil_type_and_unknown_type():
    body = _clean(client.post("/v1/crop-recommendation/soil-type", json={"soil_type": "Black", **WEATHER}))
    assert body["model"] == "crop_soil_type"
    bad = client.post("/v1/crop-recommendation/soil-type", json={"soil_type": "Moon dust", **WEATHER})
    assert bad.status_code == 422 and bad.json()["reason"] == "invalid_input"


def test_fertilizer_soil_test_state_average_and_gap():
    test = _clean(client.post("/v1/fertilizer", json={"crop": "rice", "soil_sample": {"N": 40, "P": 30, "K": 20, "pH": 6.2}}))
    assert set(test["deficits"]) == {"N", "P", "K"} and test["basis"] == "soil_test"
    state = _clean(client.post("/v1/fertilizer", json={"crop": "maize", "state": "Karnataka"}))
    assert "NOT a soil test" in state["basis"]
    gap = _clean(client.post("/v1/fertilizer", json={"crop": "sugarcane", "state": "Karnataka"}))
    assert gap["error"] == "no_nutrient_target"


def test_yield_is_a_band_never_a_number():
    body = _clean(client.post("/v1/yield", json={"crop": "Rice", "season": "Kharif", "state": "Karnataka", "year": 2026}))
    assert body["unit"] is None
    assert body["position"] in {"above typical", "around typical", "below typical", "well below typical"}
    assert body["year_in_training_range"] is False
    assert body["inputs_basis"] == "typical"


def test_disease_search_list_detail():
    search = _clean(client.get("/v1/disease/search", params={"crop": "rice", "q": "brown spots on leaves"}))
    assert search["scope"] == "crop_scoped" and search["matches"]
    listing = _clean(client.get("/v1/disease/list", params={"crop": "rice"}))
    assert len(listing["diseases"]) == 8
    detail = _clean(client.get("/v1/disease/detail", params={"crop": "rice", "disease": "Rice Blast"}))
    assert detail["remedies"]
    assert client.get("/v1/disease/list", params={"crop": "ragi"}).json()["reason"] == "no_coverage_for_crop"


# --- market (mirrors the checks in MODEL_RESULTS.md section 18) --------------

def test_price_outlook_contract():
    maize = _clean(client.get("/v1/price/outlook", params={"commodity": "maize", "district": "Davanagere"}))
    assert maize["level"] == "district" and maize["forecast"]["direction"] in {"up", "down", "flat"}
    unknown = client.get("/v1/price/outlook", params={"commodity": "maize", "district": "Nowhere"}).json()
    assert unknown["level"] == "state"
    paddy = _clean(client.get("/v1/price/outlook", params={"commodity": "paddy"}))
    assert paddy["forecast"] is None and paddy["seasonal_outlook"]
    tomato = client.get("/v1/price/outlook", params={"commodity": "tomato"})
    assert tomato.status_code == 422


# --- images -----------------------------------------------------------------

def test_upload_guards():
    not_image = client.post("/v1/soil-type", files={"photo": ("x.jpg", b"hello", "image/jpeg")})
    assert not_image.status_code == 422 and not_image.json()["reason"] == "invalid_image"
    huge = b"\xff\xd8\xff" + b"0" * (8 * 1024 * 1024 + 10)
    too_big = client.post("/v1/soil-type", files={"photo": ("x.jpg", huge, "image/jpeg")})
    assert too_big.status_code == 413


def test_rice_leaf_requires_symptom_then_diagnoses():
    image = _first_image(paths.RICE_LEAF_IMAGES)
    if image is None:
        pytest.skip("rice leaf dataset absent")
    files = {"photo": ("leaf.jpg", image.read_bytes(), "image/jpeg")}
    gated = _clean(client.post("/v1/leaf", files=files, data={"crop": "rice"}))
    assert gated["reason"] == "symptom_required"
    files = {"photo": ("leaf.jpg", image.read_bytes(), "image/jpeg")}
    body = _clean(client.post("/v1/leaf", files=files, data={"crop": "rice", "symptom_reported": "true"}))
    assert body["condition"]["category"] == "disease"


def test_sugarcane_leaf_upload_is_409():
    response = client.post("/v1/leaf", files={"photo": ("x.jpg", _jpeg_bytes(), "image/jpeg")},
                           data={"crop": "sugarcane", "symptom_reported": "true"})
    assert response.status_code == 409 and response.json()["reason"] == "model_did_not_ship"


@pytest.mark.parametrize(
    "endpoint, root, pattern, data, key",
    [
        ("/v1/insects", paths.INSECTS_YOLO_ROOT / "test" / "images", "*.jpg", {"crop": "rice"}, "detections"),
        ("/v1/wheat-heading", paths.WHEAT_SEGMENTATION_ROOT, "*.jpg", {}, "heading_detected"),
        ("/v1/tobacco-lesions", paths.TOBACCO_SEGMENTATION_ROOT, "*.png", {}, "lesion_area_percent"),
    ],
)
def test_image_models(endpoint, root, pattern, data, key):
    image = _first_image(root, pattern)
    if image is None:
        pytest.skip(f"{root} absent")
    mime = "image/png" if image.suffix.lower() == ".png" else "image/jpeg"
    body = _clean(client.post(endpoint, files={"photo": (image.name, image.read_bytes(), mime)}, data=data))
    assert key in body


def test_soil_type_photo():
    body = _clean(client.post("/v1/soil-type", files={"photo": ("s.jpg", _jpeg_bytes((224, 224)), "image/jpeg")}))
    assert body["predicted_soil_type"] in {"Alluvial Soil", "Black Soil", "Cinder Soil", "Red Soil"}
    json.dumps(body)


# --- soil fertility (model 5b) ------------------------------------------------

CARD = {"N": 280, "P": 22, "K": 250, "pH": 6.8, "EC": 0.4, "OC": 0.62,
        "S": 12, "Zn": 0.9, "Fe": 6.5, "Cu": 0.8, "Mn": 5.0, "B": 0.6}


def test_soil_fertility_full_card():
    body = _clean(client.post("/v1/soil-fertility", json=CARD))
    assert body["fertility_class"] in {"low", "medium", "high"}
    assert body["confidence_label"] in {"unverified", "provisional"}
    assert body["provenance_verified"] is False


def test_soil_fertility_names_missing_values():
    body = _clean(client.post("/v1/soil-fertility", json={"N": 280, "P": 22, "K": 250, "pH": 6.8}))
    assert body["reason"] == "missing_values"
    assert set(body["missing"]) == {"EC", "OC", "S", "Zn", "Fe", "Cu", "Mn", "B"}


def test_soil_fertility_rejects_bad_values():
    assert client.post("/v1/soil-fertility", json={**CARD, "pH": 20}).status_code == 422


# --- models 20-28 ---------------------------------------------------------------

def test_part_capabilities_carry_the_registry_key():
    caps = _clean(client.get("/v1/capabilities", params={"crop": "cauliflower"}))["capabilities"]
    assert caps["curd_diagnosis"]["model_key"] == "cauliflower curd"
    assert caps["curd_diagnosis"]["conditional"] is False


def test_wheat_kernels_are_held():
    caps = _clean(client.get("/v1/capabilities", params={"crop": "wheat"}))["capabilities"]
    assert caps["wheat_kernels"] == {"available": False, "reason": "awaiting_lighting_check"}
    response = client.post("/v1/wheat-kernels", files={"photo": ("k.jpg", _jpeg_bytes(), "image/jpeg")})
    assert response.status_code == 409
    assert response.json()["reason"] == "model_on_hold"


@pytest.mark.parametrize(
    "model_key",
    ["coffee", "tea", "cauliflower", "cauliflower curd", "onion", "onion bulb", "potato", "tomato fruit"],
)
def test_new_leaf_models_classify_a_real_image(model_key):
    root = paths.LEAF_IMAGE_ROOTS[model_key]
    image = _first_image(root) or _first_image(root, "*.png")
    if image is None:
        pytest.skip(f"{root} absent")
    mime = "image/png" if image.suffix.lower() == ".png" else "image/jpeg"
    body = _clean(client.post("/v1/leaf", files={"photo": (image.name, image.read_bytes(), mime)},
                              data={"crop": model_key}))
    assert body["condition"]["confidence_label"] in {"unverified", "provisional"}
    if model_key == "tomato fruit":
        assert body["condition"]["category"] == "grade"
        assert body["offer_none_of_these"] is False
    if model_key.startswith("onion") and body["condition"]["key"] == "unhealthy":
        assert body["condition"]["qa_disease"] is None
