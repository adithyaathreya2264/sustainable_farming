"""Response shapes for GET /api/v1/catalog/crops and /api/v1/catalog/agri-inputs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CropVarietyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str


class GrowthStageOut(BaseModel):
    """A crop's growth-stage window. The frontend uses this to compute a
    planting's current stage from its sowing date (for the scouting form) —
    same day-range data `services/growth_stage.py` uses server-side. Timing is
    a heuristic default, not ground truth (see the model docstring)."""

    model_config = ConfigDict(from_attributes=True)

    stage_name: str
    stage_order: int
    typical_days_from_sowing_start: int
    typical_days_from_sowing_end: int


class CropOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    varieties: list[CropVarietyOut]
    growth_stages: list[GrowthStageOut] = []


class AgriCatalogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    category: str  # enum value as string
    name: str
    unit_of_measure: str
    crop_applicability: list[str] | None
    # Still null for every seeded row per Task 3.4 — shaped now so the rule
    # engine (Task 2.5) can start reading it without a schema change later.
    typical_dosage_per_hectare: float | None


class CropsListOut(BaseModel):
    items: list[CropOut]


class AgriCatalogListOut(BaseModel):
    items: list[AgriCatalogOut]
