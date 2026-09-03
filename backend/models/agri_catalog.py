"""Agricultural input catalog (seeds, fertilizers, pesticides, ...).

Resolves the `Intervention.product_id` half of Slice 1's `TODO(agri-catalog)`
(the crop half is `models/crop.py`). Server-owned reference, not synced —
same precedent as `GovtScheme`.

Deliberately holds product IDENTITY only — no baked-in dosage number.
Dosage is context-dependent (season, soil, irrigation) and belongs in the
rule engine (Task 2.5's rule matrix), not a fixed catalog field;
`typical_dosage_per_hectare` exists for the rule engine to cross-check
against, not as the recommendation itself.
"""

from __future__ import annotations

import enum

from sqlalchemy import Boolean, Enum as SQLEnum, Numeric, String
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin


class AgriCatalogCategory(str, enum.Enum):
    seed = "seed"
    fertilizer = "fertilizer"
    pesticide = "pesticide"
    herbicide = "herbicide"
    fungicide = "fungicide"
    biocontrol = "biocontrol"


class AgriCatalog(Base, TimestampMixin):
    __tablename__ = "agri_catalog"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    category: Mapped[AgriCatalogCategory] = mapped_column(
        SQLEnum(AgriCatalogCategory), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    # List of crop names this input applies to; null = universal.
    crop_applicability: Mapped[list | None] = mapped_column(JSON, nullable=True)
    unit_of_measure: Mapped[str] = mapped_column(String(24), nullable=False)
    typical_dosage_per_hectare: Mapped[float | None] = mapped_column(
        Numeric(14, 4), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
