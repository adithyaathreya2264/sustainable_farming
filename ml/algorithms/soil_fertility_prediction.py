"""Soil fertility class (Low / Medium / High) from a soil-test card (model 5b).

Takes the 12 values printed on a soil-test report (N, P, K in kg/ha; pH; EC
in dS/m; OC in %; S, Zn, Fe, Cu, Mn, B in ppm) and returns the fertility class
the training labs' rating scheme would assign.

## What it is and is not

The training labels are a threshold of a nutrient index computed from these
same values, so the model reproduces that rating scheme (test macro-F1 0.98).
It does not predict yield or recommend fertiliser. The source of the training
data was not disclosed, so every response carries `provenance_verified: False`.

Replaces model 5 (`soil_fertility.csv`), which failed its bar and was never
served. See MODEL_RESULTS.md section 5b.
"""

from __future__ import annotations

import threading

import pandas as pd

from ml import paths
from ml.algorithms._loader import ModelDidNotShip
from ml.labels import confidence_label

_state: dict = {}
_lock = threading.Lock()


def _load() -> dict:
    with _lock:
        if "artifact" not in _state:
            import joblib

            path = paths.SOIL_FERTILITY_V2_MODEL
            if not path.exists():
                raise FileNotFoundError(
                    f"{path.name} not found. Train it with "
                    f"`python -m ml.training.train_soil_fertility_v2_model`."
                )
            artifact = joblib.load(path)
            if artifact.get("passed_bar") is not True:
                raise ModelDidNotShip(f"{path.name} did not clear its acceptance bar. See ml/MODEL_RESULTS.md.")
            _state["artifact"] = artifact
        return _state["artifact"]


def predict_soil_fertility(soil_test: dict) -> dict:
    """Fertility class for one soil test; `soil_test` maps each feature to a number."""
    artifact = _load()
    missing = [f for f in artifact["features"] if soil_test.get(f) is None]
    if missing:
        return {"reason": "missing_values", "missing": missing}

    row = pd.DataFrame([{f: float(soil_test[f]) for f in artifact["features"]}])
    model = artifact["model"]
    probabilities = model.predict_proba(row)[0]
    best = int(probabilities.argmax())
    return {
        "fertility_class": str(model.classes_[best]).lower(),
        "confidence_label": confidence_label(float(probabilities[best])),
        "provenance_verified": False,
        "caveats": [
            "Reproduces the rating scheme of the soil-test labs in the training data; "
            "the data's source is unverified.",
            "A fertility class is not a fertiliser recommendation.",
        ],
        "model": "soil_fertility_v2",
    }
