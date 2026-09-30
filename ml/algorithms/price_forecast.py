"""Mandi price outlook for Karnataka: seasonal ranges plus a 13-week forecast (model 18).

## Two outputs, two levels of trust

- **Seasonal outlook** (always, when history exists): for each calendar month,
  the median and interquartile range of weekly modal prices, 2023 to early
  2026, for the district (or Karnataka when the district reports too rarely).
  It is history, not a forecast, and it under-covered the 2026 test months
  (36% of prices inside the IQR against 50% expected), so it is labelled as
  past ranges.
- **13-week forecast** (only for crops that cleared their bar: see
  `shipped_crops` in the artifact and MODEL_RESULTS.md section 18): the
  expected price change from the latest week in the data, with a range from
  that crop's measured test error.

## What the forecast cannot do

- It starts from the **last week in the dataset** (`data_end`). It is only as
  current as the data; without new data it goes stale, and every response
  carries the origin date.
- It passed on one half-season (April-September 2026). On the half-season
  before it, it was barely better than "price stays the same". The response
  says so.
- "rice" is **milled rice**. Paddy, which farmers sell, has no verdict because
  Karnataka paddy markets do not trade in the test months.

Prices are Rs per quintal. No sell/hold recommendation is made.
"""

from __future__ import annotations

import threading

import numpy as np
import pandas as pd

from ml import paths
from ml.algorithms._loader import ModelDidNotShip

_state: dict = {}
_lock = threading.Lock()


def _load() -> dict:
    with _lock:
        if "artifact" not in _state:
            import joblib
            import json

            path = paths.PRICE_FORECAST_MODEL
            if not path.exists():
                raise FileNotFoundError(
                    f"{path.name} not found. Train it with `python -m ml.training.train_price_forecast`."
                )
            artifact = joblib.load(path)
            metrics = json.loads(path.with_name("price_forecast_metrics.json").read_text(encoding="utf-8"))
            artifact["test_mae"] = {c: s["mae"] for c, s in metrics["test_per_crop"].items()}
            _state["artifact"] = artifact
        return _state["artifact"]


def price_commodities() -> list[str]:
    return sorted(key for key, _ in _load()["commodities"].values())


def _series_for(artifact, crop: str, district: str | None):
    from ml.training.train_price_forecast import STATE_SERIES

    columns = set(artifact["series_columns"])
    if district and (crop, district) in columns:
        return (crop, district), "district"
    if (crop, STATE_SERIES) in columns:
        return (crop, STATE_SERIES), "state"
    return None, None


def price_outlook(commodity: str, district: str | None = None) -> dict:
    """Seasonal price ranges, and a 13-week forecast where the crop shipped."""
    from ml.training.train_price_forecast import _rows

    artifact = _load()
    known = {key: app for key, app in artifact["commodities"].values()}
    if commodity not in known:
        return {"commodity": commodity, "reason": "unknown_commodity", "supported": sorted(known)}

    column, level = _series_for(artifact, commodity, district)
    if column is None:
        return {"commodity": commodity, "reason": "no_price_history"}

    outlook = {
        int(month): {"median": round(v["median"]), "p25": round(v["p25"]), "p75": round(v["p75"]), "years": v["years"]}
        for month, v in sorted(artifact["outlook"].get(column, {}).items())
    }
    response = {
        "commodity": commodity,
        "app_crop": known[commodity],
        "district": district,
        "level": level,  # "district" or "state" (Karnataka-wide fallback)
        "unit": "Rs/quintal (modal)",
        "seasonal_outlook": outlook,
        "seasonal_outlook_note": "Historical ranges 2023 to early 2026, not a forecast.",
        "forecast": None,
        "caveats": [],
    }
    if commodity == "rice":
        response["caveats"].append("'rice' is milled rice; paddy prices have no validated forecast.")

    if commodity not in artifact["shipped_crops"]:
        response["forecast_reason"] = "not_validated_for_this_commodity"
        return response

    rows = _rows(artifact["recent_series"], [column], artifact["feature_profile"])
    rows["crop_code"] = rows["crop"].map(artifact["crop_codes"])
    rows["is_state"] = rows["is_state"].astype(int)
    latest = rows[rows["week"] == artifact["recent_series"].index.max()]
    if latest.empty:
        response["forecast_reason"] = "no_recent_price"
        return response
    row = latest.iloc[0]
    change = float(artifact["model"].predict(latest[artifact["features"]])[0])
    error = artifact["test_mae"][commodity]
    now = float(np.exp(row["now"]))
    response["forecast"] = {
        "origin_week": str(pd.Timestamp(row["week"]).date()),
        "target_week": str(pd.Timestamp(row["target_week"]).date()),
        "current_price": round(now),
        "expected_price": round(now * np.exp(change)),
        "range": [round(now * np.exp(change - error)), round(now * np.exp(change + error))],
        "direction": "up" if change >= np.log(1.05) else "down" if change <= -np.log(1.05) else "flat",
        "confidence_label": "provisional",
    }
    response["caveats"] += [
        f"Forecast from the latest data week ({response['forecast']['origin_week']}); it does not know newer prices.",
        "Validated on one half-season (Apr-Sep 2026); on the half-season before it the model was "
        "barely better than assuming prices stay the same.",
        "Not a sell/hold recommendation.",
    ]
    return response


def supported_commodities() -> list[dict]:
    """Every modelled commodity, its app crop (or None), and whether its
    13-week forecast shipped. Outlook-only commodities still get seasonal ranges."""
    artifact = _load()
    shipped = set(artifact["shipped_crops"])
    return sorted(
        (
            {"commodity": key, "app_crop": app, "forecast_shipped": key in shipped}
            for key, app in artifact["commodities"].values()
        ),
        key=lambda c: c["commodity"],
    )
