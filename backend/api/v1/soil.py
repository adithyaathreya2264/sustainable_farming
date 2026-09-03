"""Soil-type lookup endpoint (Task 3.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.core.deps import get_current_user
from backend.models.user import User
from backend.schemas.soil import SoilLookupOut
from backend.services.soil_lookup import get_soil_type

router = APIRouter(prefix="/api/v1", tags=["soil"])


@router.get("/soil-lookup", response_model=SoilLookupOut)
def soil_lookup(
    state: str = Query(...),
    district: str = Query(...),
    taluk: str | None = Query(None),
    current_user: User = Depends(get_current_user),
) -> SoilLookupOut:
    result = get_soil_type(state, district, taluk)
    if result is None:
        return SoilLookupOut(soil_type=None, confidence="none", source=None)
    return SoilLookupOut(
        soil_type=result.soil_type,
        confidence=result.confidence,
        source=result.source,
    )
