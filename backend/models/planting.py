"""A crop planting within a field."""

from __future__ import annotations

import enum

from sqlalchemy import Date, Enum as SQLEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, SyncMixin, TimestampMixin


class PlantingStatus(str, enum.Enum):
    active = "active"
    harvested = "harvested"


class Planting(Base, TimestampMixin, SyncMixin):
    __tablename__ = "plantings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    field_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("fields.id"), nullable=False, index=True
    )
    crop_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("crops.id"), nullable=False, index=True
    )
    variety_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("crop_varieties.id"), nullable=True
    )
    sowing_date: Mapped[Date] = mapped_column(Date, nullable=False)
    status: Mapped[PlantingStatus] = mapped_column(
        SQLEnum(PlantingStatus), nullable=False, default=PlantingStatus.active
    )
