"""Crop master + variety reference tables.

Resolves the `Planting.crop_id`/`variety_id` half of Slice 1's
`TODO(agri-catalog)` — the other half is `models/agri_catalog.py` (inputs,
a distinct concept from crops). Server-owned reference data, not synced —
same precedent as `GovtScheme`: farmers select from it, they don't edit it.
"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class Crop(Base, TimestampMixin):
    __tablename__ = "crops"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Needed for GET /api/v1/catalog/crops to eager-load via joinedload() —
    # no relationship existed before that endpoint required nesting varieties
    # under their crop in one response.
    varieties: Mapped[list["CropVariety"]] = relationship(
        back_populates="crop", order_by="CropVariety.name"
    )


class CropVariety(Base, TimestampMixin):
    __tablename__ = "crop_varieties"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    crop_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("crops.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    crop: Mapped["Crop"] = relationship(back_populates="varieties")
