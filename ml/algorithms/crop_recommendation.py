"""Crop recommendation. Two models, two entry points.

- `recommend_crop()`            N/P/K + weather -> crop (51 classes)
- `recommend_crop_from_soil_type()`  soil type + weather -> crop (31 classes)

## What changed from the inherited version

1. **Lazy loading** rather than `joblib.load` at import scope, via `_loader`,
   which also refuses to serve a model that missed its bar.

2. **No probabilities cross this boundary.** The inherited version returned
   `"confidence": 0.87`. `backend/plan/phase4-part2.txt` line 33 directs that
   numeric confidence be dropped for a categorical badge, "rather than a
   numeric score that implies false precision" — and a random forest's 0.87 is
   the fraction of its trees that voted one way on synthetic training data, not
   an 87% chance of being right. The float is mapped to a label in
   `ml/labels.py` and discarded here.

3. **Results speak the app's crop vocabulary.** The models emit their training
   labels (`rice`, `cotton`). Every result now carries `crop_key`,
   `display_name` and `is_seeded_crop`, mapped through `ml/prep/common.py` —
   the same table the rest of the repo uses.

4. **`is_seeded_crop` is on every result** because a recommendation the app
   cannot act on is a different thing from one it can. Only five crops exist in
   the `crops` table; a confident "jute" has no planting flow behind it. This
   module makes that visible rather than deciding for the caller.

## Sugarcane cannot be recommended by the N/P/K model

`merged_crop_dataset.csv` has no sugarcane among its 51 labels, so
`recommend_crop()` can never return one of the five seeded crops. The
soil-type model's dataset does contain it. `unreachable_seeded_crops()` reports
this rather than leaving a caller to discover it from an empty result.

## Both models ship provisional

Their training data is synthetically sampled from per-crop distributions and is
highly separable — the N/P/K model scores weighted-F1 0.997 on held-out data,
which evidences a correct pipeline rather than field accuracy. Neither has been
reviewed by an agronomist. See `ml/MODEL_RESULTS.md`.
"""

from __future__ import annotations

import pandas as pd

from ml import paths
from ml.algorithms._loader import load_artifact
from ml.labels import rank_predictions
from ml.prep.common import SEEDED_CROPS, crop_key

TOP_K = 4


def _npk_bundle() -> dict:
    return load_artifact(paths.CROP_RECOMMENDATION_MODEL)


def _soil_bundle() -> dict:
    return load_artifact(paths.CROP_SOIL_TYPE_MODEL)


def recommend_crop(
    N: float,
    P: float,
    K: float,
    temperature: float,
    humidity: float,
    ph: float,
    rainfall: float,
) -> dict:
    """Recommend a crop from a soil test and local weather.

    Returns the top recommendation plus ranked alternatives. Every entry
    carries a categorical confidence label; no probability is returned.
    """
    bundle = _npk_bundle()
    model, features = bundle["model"], bundle["features"]
    row = pd.DataFrame([[N, P, K, temperature, humidity, ph, rainfall]], columns=features)

    ranked = rank_predictions(model.classes_, model.predict_proba(row)[0], top_k=TOP_K)
    return {
        "recommended": ranked[0],
        "alternatives": ranked[1:],
        "model": "crop_recommendation",
        "unreachable_seeded_crops": unreachable_seeded_crops(),
    }


def recommend_crop_from_soil_type(
    soil_type: str, temperature: float, humidity: float, ph: float, rainfall: float
) -> dict:
    """Recommend a crop from a soil-type name and local weather.

    Raises ValueError for a soil type the model was never fitted on, rather
    than returning a confident answer from an unseen category. `known_soil_types()`
    lists what it accepts.
    """
    bundle = _soil_bundle()
    vocabulary = bundle.get("soil_type_vocab") or []
    if soil_type not in vocabulary:
        raise ValueError(
            f"Soil type {soil_type!r} was not in this model's training vocabulary. "
            f"Known types: {sorted(vocabulary)}"
        )

    model = bundle["model"]
    row = pd.DataFrame(
        [
            {
                "Soil type": soil_type,
                "temperature": temperature,
                "humidity": humidity,
                "ph": ph,
                "rainfall": rainfall,
            }
        ]
    )
    ranked = rank_predictions(model.classes_, model.predict_proba(row)[0], top_k=TOP_K)
    return {
        "recommended": ranked[0],
        "alternatives": ranked[1:],
        "model": "crop_soil_type",
        "soil_type": soil_type,
    }


def known_soil_types() -> list[str]:
    """Soil-type names `recommend_crop_from_soil_type` accepts."""
    return sorted(_soil_bundle().get("soil_type_vocab") or [])


def unreachable_seeded_crops() -> list[str]:
    """Seeded crops the N/P/K model can never recommend, because its training
    data contains no examples of them. Currently sugarcane."""
    reachable = {crop_key(label) for label in _npk_bundle()["classes"]}
    return sorted(set(SEEDED_CROPS) - reachable)
