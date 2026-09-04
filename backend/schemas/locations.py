"""Response shape for GET /api/v1/locations (onboarding state/district pickers)."""

from __future__ import annotations

from pydantic import BaseModel


class StateDistrictsOut(BaseModel):
    state: str
    districts: list[str]


class LocationsListOut(BaseModel):
    items: list[StateDistrictsOut]
