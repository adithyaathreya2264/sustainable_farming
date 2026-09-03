"""Response shape for GET /api/v1/soil-lookup."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SoilLookupOut(BaseModel):
    soil_type: str | None
    confidence: Literal["taluk", "district", "none"]
    source: str | None
