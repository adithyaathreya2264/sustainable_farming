"""Nutrient deficit between a soil reading and a crop's target. No products.

## What this returns, and what it deliberately does not

It returns the gap: how far this soil sits from what the crop wants, per
nutrient, plus whether pH is inside the crop's acceptable band. That gap is the
whole feature.

It does **not** name a fertiliser or state a dose. The inherited version
returned prose like `"Add nitrogen (~45.0 kg/ha shortfall) - e.g. Urea."`,
which duplicated work the app already does better:

- Product identity lives in the `agri_catalog` table, served by
  `GET /api/v1/catalog/agri-inputs`, whose stated convention is "product
  identity only, no baked-in dosage". Hardcoding "Urea" in a model response
  means two sources of truth for what a farmer should buy.
- The catalog already carries `typical_dosage_per_hectare`, and dosage scales
  with field area (`docs/unit-conversions.md`), which this module has no
  knowledge of.
- Those strings are English. The app ships 10 locales. A localisable app
  cannot have its advice text generated inside a model.

So this emits structured numbers and the serving layer joins them to the
catalog. Same discipline as the categorical confidence labels.

## The fertility classifier was removed, and it was never load-bearing

The inherited version computed `fertility_class` from `soil_fertility_model.pkl`
and returned it — but the advice came entirely from `target - current > 10`
thresholds. The model output influenced nothing; it was decorative.

That model then failed its acceptance bar (macro-F1 0.6944 against 0.75, and
recall 0.50 on the high-fertility class it exists to detect), and
`MODEL_BARS.md` says a model that misses its bar does not ship. Removing it
costs this module nothing, because the deficit arithmetic never depended on it.

The inherited code also had `FERTILITY_LABELS[fertility_class]`, which would
raise `KeyError` on any class outside {0,1,2} — a latent crash that is now moot.

## The state-average fallback is a rough estimate and says so

`recommend_from_state_average()` exists for a farmer with no soil test. It uses
`state_soil_data.csv`, which is one row per state with suspiciously round values
across all 30 states — it reads as hand-authored rather than survey-derived, and
its provenance is unrecorded. The result is labelled accordingly and is not a
substitute for a real sample.
"""

from __future__ import annotations

import json
from functools import lru_cache

import pandas as pd

from ml import paths
from ml.prep.common import crop_key

NUTRIENTS = ("N", "P", "K")

# Below this, the gap is within the noise of a soil test and is not worth
# acting on. Inherited value, kept: it is a sensible agronomic rounding rather
# than something tuned, and nothing here has been agronomist-reviewed anyway.
ACTIONABLE_DEFICIT = 10.0


@lru_cache(maxsize=1)
def _targets() -> dict:
    return json.loads(paths.require(paths.FERTILIZER_TARGETS).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _state_soil() -> pd.DataFrame:
    # The header carries a UTF-8 BOM, hence utf-8-sig.
    df = pd.read_csv(paths.require(paths.STATE_SOIL_CSV), encoding="utf-8-sig")
    df.columns = df.columns.str.strip()
    df["state"] = df["state"].str.strip()
    return df


def _ph_status(ph: float, target: dict) -> str:
    if ph < target["ph_min"]:
        return "below_range"
    if ph > target["ph_max"]:
        return "above_range"
    return "within_range"


def _assess(crop: str, reading: dict, basis: str) -> dict:
    key = crop_key(crop)
    target = _targets().get(key) if key else None
    if target is None:
        return {
            "crop_key": key,
            "error": "no_nutrient_target",
            "detail": (
                f"No nutrient target exists for {crop!r}. Fertilizer.csv covers "
                f"{len(_targets())} crops; sugarcane is a known gap."
            ),
        }

    deficits = {
        nutrient: round(target[nutrient] - float(reading[nutrient]), 1)
        for nutrient in NUTRIENTS
    }
    return {
        "crop_key": target["crop_key"],
        "display_name": target["display_name"],
        "is_seeded_crop": target["is_seeded_crop"],
        "basis": basis,
        # Positive means short of target; negative means already above it.
        "deficits": deficits,
        "actionable": {n: deficits[n] > ACTIONABLE_DEFICIT for n in NUTRIENTS},
        "actionable_threshold": ACTIONABLE_DEFICIT,
        "ph": {
            "value": round(float(reading["pH"]), 2),
            "target_min": target["ph_min"],
            "target_max": target["ph_max"],
            "status": _ph_status(float(reading["pH"]), target),
        },
        "confidence_label": "unverified",
        "note": (
            "Nutrient targets come from a synthetically expanded source with "
            "unrecorded provenance and have not been agronomist-reviewed. "
            "Product identity and dosage are not supplied here - join to "
            "agri_catalog at the serving layer."
        ),
    }


def recommend_from_soil_test(crop: str, soil_sample: dict) -> dict:
    """Nutrient gap from an actual soil test.

    `soil_sample` needs at least N, P, K and pH. The full 12-element chemistry
    panel the inherited version demanded is no longer required, because the
    fertility classifier that consumed the micronutrients has been removed.
    """
    missing = [field for field in (*NUTRIENTS, "pH") if field not in soil_sample]
    if missing:
        raise ValueError(f"soil_sample is missing required field(s): {missing}")
    return _assess(crop, soil_sample, basis="soil_test")


def recommend_from_state_average(crop: str, state: str) -> dict:
    """Nutrient gap estimated from a state average, for a farmer with no test.

    Far less reliable than `recommend_from_soil_test`. The underlying table is
    one hand-authored-looking row per state with no provenance.
    """
    rows = _state_soil()
    match = rows[rows["state"] == state]
    if match.empty:
        raise ValueError(
            f"No state-average soil data for {state!r}. "
            f"Known states: {sorted(rows['state'].unique())}"
        )
    row = match.iloc[0]
    result = _assess(
        crop,
        {"N": row["N"], "P": row["P"], "K": row["K"], "pH": row["pH"]},
        basis=f"{state} state average - NOT a soil test",
    )
    if "error" not in result:
        result["note"] = (
            "Estimated from a single state-average row, not a soil sample. "
            "state_soil_data.csv has unrecorded provenance and round values "
            "across all 30 states, consistent with hand-authored data. Results "
            "will be far less accurate than an actual test. " + result["note"]
        )
    return result
