"""Crop growth-stage reference windows (Task 4.1).

Server-owned reference, not synced — same precedent as GovtScheme/AgriCatalog/
Crop. `typical_days_from_sowing_*` is explicitly a heuristic default, not
ground truth — real timing varies with weather. Confidence/source are
structural (not just documentation) for the same reason the rule matrix
carries them: don't let an unverified number look as solid as a verified one.
"""

from __future__ import annotations

import enum

from sqlalchemy import Enum as SQLEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin


class DataConfidence(str, enum.Enum):
    low = "low"
    medium = "medium"
    verified = "verified"


class CropGrowthStage(Base, TimestampMixin):
    __tablename__ = "crop_growth_stages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    crop_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("crops.id"), nullable=False, index=True
    )
    stage_name: Mapped[str] = mapped_column(String(80), nullable=False)
    stage_order: Mapped[int] = mapped_column(Integer, nullable=False)
    typical_days_from_sowing_start: Mapped[int] = mapped_column(Integer, nullable=False)
    typical_days_from_sowing_end: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[DataConfidence] = mapped_column(
        SQLEnum(DataConfidence), nullable=False
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
