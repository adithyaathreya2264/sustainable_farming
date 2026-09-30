"""Yield prediction, expressed as a percentile within the crop's own history.

## The output is a position, not a number

`DATASETS_STATUS.md` section 2.1 established that the source `yield` column is
not production divided by area — recomputing disagrees in 13,663 of 19,689 rows
— and that its scale differs per crop (median 8,466 for coconut, 53 for
sugarcane, 2.2 for rice). There is no unit that applies across crops, and there
is no way to recover one.

Within a single crop the values are internally consistent, so a crop's own
distribution is a sound basis for comparison. What is not sound is printing a
bare number: "2.34" on a screen will be read as tonnes per hectare no matter
what the surrounding caveat says.

So the primary field is `percentile_within_crop`, computed against percentile
bands built from the same data. The raw model output is retained under
`_raw_model_output` for debugging, and **must not be forwarded past the
serving boundary**. It is prefixed and flagged for that reason.

## The year problem, which the inherited version hid

The model is trained on 1997-2020 and the weather table ends at 2020. The
inherited `_lookup_weather` silently fell back to a state's all-years mean
whenever it had no row for the requested year, and said nothing about it. In
2026 that fallback fires on **every single call**, and the caller has no way to
know: they asked about this year and got an average of the 1997-2020 period.

Worse, the model cannot extrapolate. Gradient-boosted trees partition the
feature space; asked for year 2026 they return whatever leaf 2020 fell into.
The answer is not a forecast for 2026, it is the model's 2020 answer wearing a
2026 label.

Both facts are now reported in the response (`weather_source`,
`year_in_training_range`, `caveats`) instead of being invisible. Nothing is
refused — a 2020-shaped answer is still informative — but the caller is told
what they actually received.
"""

from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import pandas as pd

from ml import paths
from ml.algorithms._loader import load_artifact
from ml.labels import describe_crop
from ml.prep.common import normalize_season, normalize_state


@lru_cache(maxsize=1)
def _weather() -> pd.DataFrame:
    df = pd.read_csv(paths.require(paths.STATE_WEATHER_CSV))
    df["state"] = df["state"].str.strip()
    return df


@lru_cache(maxsize=1)
def _benchmarks() -> list[dict]:
    path = paths.require(paths.YIELD_BENCHMARKS)
    return json.loads(path.read_text(encoding="utf-8"))["bands"]


def _lookup_weather(state: str, year: int) -> tuple[dict, str]:
    """Return (weather, source). `source` says whether it is the real year."""
    table = _weather()
    exact = table[(table["state"] == state) & (table["year"] == year)]
    if not exact.empty:
        row = exact.iloc[0]
        return (
            {
                "avg_temp_c": float(row["avg_temp_c"]),
                "total_rainfall_mm": float(row["total_rainfall_mm"]),
                "avg_humidity_percent": float(row["avg_humidity_percent"]),
            },
            f"observed {state} {year}",
        )

    state_rows = table[table["state"] == state]
    if state_rows.empty:
        raise ValueError(
            f"No weather data for state {state!r}. "
            f"Known states: {sorted(table['state'].unique())}"
        )
    return (
        {
            "avg_temp_c": float(state_rows["avg_temp_c"].mean()),
            "total_rainfall_mm": float(state_rows["total_rainfall_mm"].mean()),
            "avg_humidity_percent": float(state_rows["avg_humidity_percent"].mean()),
        },
        f"MEAN of {state} {int(state_rows['year'].min())}-{int(state_rows['year'].max())} "
        f"(no data for {year})",
    )


def _band_for(crop: str, state: str | None, season: str | None) -> dict | None:
    """Most specific percentile band available, widening on miss.

    Same three-tier fallback as `ml/prep/clean_crop_yield.py` and
    `soilLookup.js`: crop+state+season, then crop+state, then crop alone.
    """
    bands = _benchmarks()
    for scope, match in (
        ("crop_state_season", lambda b: b["state"] == state and b["season"] == season),
        ("crop_state", lambda b: b["state"] == state),
        ("crop", lambda b: True),
    ):
        for band in bands:
            if band["scope"] == scope and band["crop"] == crop and match(band):
                return band
    return None


def _percentile_of(value: float, band: dict) -> int:
    """Where `value` sits in the band, interpolated between known percentiles.

    Only the five stored percentiles are real; everything between them is a
    straight-line estimate, which is why the result is rounded to a whole
    number rather than presented with decimals it has not earned.
    """
    points = [(0.0, 0), (band["p10"], 10), (band["p25"], 25), (band["median"], 50),
              (band["p75"], 75), (band["p90"], 90)]
    if value >= band["p90"]:
        return 95
    for (low_v, low_p), (high_v, high_p) in zip(points, points[1:]):
        if low_v <= value <= high_v:
            if high_v == low_v:
                return int(high_p)
            fraction = (value - low_v) / (high_v - low_v)
            return int(round(low_p + fraction * (high_p - low_p)))
    return 5


def _describe_position(percentile: int) -> str:
    if percentile >= 75:
        return "above typical"
    if percentile >= 40:
        return "around typical"
    if percentile >= 20:
        return "below typical"
    return "well below typical"


def predict_yield(
    crop: str,
    season: str,
    state: str,
    year: int,
    fertilizer_per_ha: float,
    pesticide_per_ha: float,
) -> dict:
    """Predict yield and express it as a percentile within this crop's history.

    `fertilizer_per_ha` and `pesticide_per_ha` are per-hectare rates a farmer
    can actually answer, not the state-level absolute totals the source data
    stores. See `ml/training/train_yield_model.py`.
    """
    bundle = load_artifact(paths.YIELD_MODEL)
    model = bundle["model"]
    trained_through = bundle.get("trained_through_year", paths.STATE_WEATHER_LAST_YEAR)

    canonical_state = normalize_state(state) or state
    canonical_season = normalize_season(season) or season

    weather, weather_source = _lookup_weather(canonical_state, year)
    row = pd.DataFrame(
        [
            {
                "crop": crop,
                "season": canonical_season,
                "state": canonical_state,
                "year": year,
                "fertilizer_per_ha": fertilizer_per_ha,
                "pesticide_per_ha": pesticide_per_ha,
                **weather,
            }
        ]
    )

    # The model is fitted on log1p(yield); this inverts it. Kept in step with
    # ml/training/train_yield_model.py's _predict.
    raw = float(np.expm1(model.predict(row[bundle["features"]])[0]).clip(min=0.0))

    caveats: list[str] = []
    in_range = year <= trained_through
    if not in_range:
        caveats.append(
            f"Year {year} is beyond the model's training range (through "
            f"{trained_through}). Tree models cannot extrapolate, so this is "
            f"effectively the model's {trained_through} answer."
        )
    if weather_source.startswith("MEAN"):
        caveats.append(
            f"No weather observations exist for {year}; a multi-year average "
            f"for {canonical_state} was substituted."
        )

    band = _band_for(crop, canonical_state, canonical_season)
    result = {
        **describe_crop(crop),
        "state": canonical_state,
        "season": canonical_season,
        "year": year,
        "weather_source": weather_source,
        "year_in_training_range": in_range,
        "caveats": caveats,
        "unit": None,
        "unit_note": (
            "The source yield column has no documented unit and its scale differs "
            "per crop. Only the percentile is meaningful; never present an "
            "absolute figure."
        ),
        # Debug only. Must not be forwarded past the serving boundary - it is a
        # unitless number that will be read as tonnes per hectare if it reaches
        # a screen. See MODEL_BARS.md section 6.
        "_raw_model_output": round(raw, 4),
        "_raw_not_for_display": True,
    }

    if band is None:
        result["percentile_within_crop"] = None
        result["position"] = None
        result["caveats"] = caveats + [
            f"No historical yield band exists for {crop!r}, so the prediction "
            f"cannot be placed in context and is not reportable."
        ]
        return result

    percentile = _percentile_of(raw, band)
    result["percentile_within_crop"] = percentile
    result["position"] = _describe_position(percentile)
    result["comparison_scope"] = {
        "scope": band["scope"],
        "state": band["state"],
        "season": band["season"],
        "sample_count": band["sample_count"],
    }
    return result


@lru_cache(maxsize=1)
def _typical_input_table() -> dict:
    """Median per-hectare input rates per crop over the training years.

    Computed the same way `ml/training/train_yield_model.py:_load` derives its
    features (state totals / area), restricted to the years the model was
    fitted on so the fallback never reflects held-out data.
    """
    trained_through = load_artifact(paths.YIELD_MODEL).get(
        "trained_through_year", paths.STATE_WEATHER_LAST_YEAR
    )
    df = pd.read_csv(paths.require(paths.CROP_YIELD_CSV))
    df["crop"] = df["crop"].str.strip()
    df = df.dropna(subset=["area", "fertilizer", "pesticide", "year"])
    df = df[(df["area"] > 0) & (df["year"] <= trained_through)]
    df["fertilizer_per_ha"] = df["fertilizer"] / df["area"]
    df["pesticide_per_ha"] = df["pesticide"] / df["area"]
    medians = df.groupby("crop")[["fertilizer_per_ha", "pesticide_per_ha"]].median()
    return {crop: {k: float(v) for k, v in row.items()} for crop, row in medians.iterrows()}


def yield_crop_names() -> list[str]:
    """Crop names as the yield model and its benchmarks spell them."""
    return sorted({band["crop"] for band in _benchmarks()})


def typical_inputs(crop: str) -> dict:
    """Training-period median fertilizer/pesticide rates for `crop`.

    The fallback for a farmer whose logged inputs cannot be expressed in the
    source data's units - which are undocumented, so in practice always.
    """
    table = _typical_input_table()
    if crop not in table:
        raise ValueError(f"No input history for crop {crop!r}.")
    return table[crop]
