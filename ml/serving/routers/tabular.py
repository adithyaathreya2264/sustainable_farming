"""Endpoints for the non-image models: 1, 2, 3, 4b, 5b, 6."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from ml.algorithms import crop_recommendation as cr
from ml.algorithms import disease_info_retrieval as dq
from ml.algorithms import fertilizer_recommendation as fr
from ml.algorithms import soil_fertility_prediction as sf
from ml.algorithms import yield_prediction as yp
from ml.prep.common import crop_key
from ml.serving.capabilities import yield_crop_name
from ml.serving.sanitize import public

router = APIRouter(prefix="/v1")


class Weather(BaseModel):
    temperature: float
    humidity: float = Field(ge=0, le=100)
    ph: float = Field(ge=0, le=14)
    rainfall: float = Field(ge=0)


class NpkRequest(Weather):
    N: float = Field(ge=0)
    P: float = Field(ge=0)
    K: float = Field(ge=0)


class SoilTypeRequest(Weather):
    soil_type: str


@router.post("/crop-recommendation")
def crop_recommendation(body: NpkRequest) -> dict:
    return public(cr.recommend_crop(**body.model_dump()))


@router.get("/crop-recommendation/soil-types")
def soil_types() -> dict:
    return {"soil_types": cr.known_soil_types()}


@router.post("/crop-recommendation/soil-type")
def crop_recommendation_soil_type(body: SoilTypeRequest) -> dict:
    return public(cr.recommend_crop_from_soil_type(**body.model_dump()))


class SoilSample(BaseModel):
    N: float
    P: float
    K: float
    pH: float


class FertilizerRequest(BaseModel):
    crop: str
    soil_sample: SoilSample | None = None
    state: str | None = None


@router.post("/fertilizer")
def fertilizer(body: FertilizerRequest) -> dict:
    if body.soil_sample is not None:
        return public(fr.recommend_from_soil_test(body.crop, body.soil_sample.model_dump()))
    if body.state:
        return public(fr.recommend_from_state_average(body.crop, body.state))
    raise ValueError("either soil_sample or state is required")


class YieldRequest(BaseModel):
    crop: str
    season: str
    state: str
    year: int = Field(ge=1990, le=date.today().year + 1)


@router.post("/yield")
def yield_outlook(body: YieldRequest) -> dict:
    """Percentile band only.

    Input rates are always the crop's training-period medians: the source
    data's fertilizer/pesticide units are undocumented, so a farmer's logged
    quantities cannot be converted into them honestly. (In the source data the
    per-hectare fertilizer rate is also near-identical across crops, so this
    costs little.)
    """
    key = crop_key(body.crop)
    name = yield_crop_name(key)
    if name is None:
        raise ValueError(f"no yield history for crop {body.crop!r}")
    inputs = yp.typical_inputs(name)
    result = yp.predict_yield(name, body.season, body.state, body.year, **inputs)
    result["inputs_basis"] = "typical"
    result["caveats"] = list(result.get("caveats", [])) + [
        "Uses typical fertilizer and pesticide rates for this crop, not your logged "
        "inputs: the source data does not document its units.",
    ]
    return public(result)


@router.get("/disease/search")
def disease_search(
    crop: str,
    q: str = Query(min_length=2, max_length=500),
    top_k: int = Query(3, ge=1, le=5),
) -> dict:
    return public(dq.find_disease_info(q, crop, top_k=top_k))


@router.get("/disease/list")
def disease_list(crop: str) -> dict:
    return public(dq.list_diseases(crop))


@router.get("/disease/detail")
def disease_detail(crop: str, disease: str) -> dict:
    return public(dq.disease_detail(crop, disease))


class SoilCard(BaseModel):
    """The 12 values of a soil-test card. Units as printed on Indian soil
    health cards: N/P/K kg/ha, EC dS/m, OC %, S/Zn/Fe/Cu/Mn/B ppm. Any may be
    missing; the response then names what is missing instead of guessing."""

    N: float | None = Field(None, ge=0)
    P: float | None = Field(None, ge=0)
    K: float | None = Field(None, ge=0)
    pH: float | None = Field(None, ge=0, le=14)
    EC: float | None = Field(None, ge=0)
    OC: float | None = Field(None, ge=0)
    S: float | None = Field(None, ge=0)
    Zn: float | None = Field(None, ge=0)
    Fe: float | None = Field(None, ge=0)
    Cu: float | None = Field(None, ge=0)
    Mn: float | None = Field(None, ge=0)
    B: float | None = Field(None, ge=0)


@router.post("/soil-fertility")
def soil_fertility(body: SoilCard) -> dict:
    """Model 5b. Reproduces the training labs' Low/Medium/High rating; not a
    fertiliser recommendation (model 3 does that) and provenance unverified."""
    return public(sf.predict_soil_fertility(body.model_dump()))
