"""Model 18: Karnataka mandi price outlook."""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter

from ml.algorithms import price_forecast as pf
from ml.prep.common import crop_key, normalize_district
from ml.serving.sanitize import public

router = APIRouter(prefix="/v1/price")

STATE = "Karnataka"

# Market-data spellings that `normalize_district` does not resolve but that
# name exactly one current district. "Bangalore" is deliberately absent: it
# could be Bengaluru Urban or Rural, so those farmers get the Karnataka series
# (the same call DATASETS_STATUS.md records for the market cleaner).
_UNAMBIGUOUS_ALIASES = {
    "Chamrajnagar": "Chamarajanagar",
    "Davangere": "Davanagere",
    "Kalburgi": "Kalaburagi",
    "Karwar(Uttar Kannad)": "Uttara Kannada",
}


@lru_cache(maxsize=1)
def _app_to_model_district() -> dict[str, str]:
    """App district name (lower-cased) -> the model's series name."""
    artifact = pf._load()
    model_districts = {d for (_, d) in artifact["series_columns"]} - {"__state__"}
    mapping = {}
    for name in model_districts:
        app_name = normalize_district(STATE, name) or _UNAMBIGUOUS_ALIASES.get(name)
        if app_name:
            mapping[app_name.lower()] = name
        mapping.setdefault(name.lower(), name)  # the model's own spelling also works
    return mapping


def model_district(app_district: str | None) -> str | None:
    if not app_district:
        return None
    return _app_to_model_district().get(app_district.strip().lower())


@router.get("/commodities")
def commodities() -> dict:
    # crop_key lets the app match a commodity to a planting's crops.ml_key even
    # where the artifact predates the crop (bajra -> "pearl millet").
    items = [
        {**c, "crop_key": c["app_crop"] or crop_key(c["commodity"])}
        for c in pf.supported_commodities()
    ]
    return public({"commodities": items, "state": STATE})


@router.get("/outlook")
def outlook(commodity: str, district: str | None = None) -> dict:
    result = pf.price_outlook(commodity, model_district(district))
    if result.get("reason") == "unknown_commodity":
        raise ValueError(f"unknown commodity {commodity!r}; supported: {result['supported']}")
    # Report the district the farmer asked about, not the market-data spelling.
    if result.get("level") == "district":
        result["district"] = district
    elif "district" in result:
        result["requested_district"] = district
        result["district"] = None
    return public(result)
