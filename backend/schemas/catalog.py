"""Response shapes for GET /api/v1/catalog/crops and /api/v1/catalog/agri-inputs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CropVarietyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str


class CropOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    varieties: list[CropVarietyOut]


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
