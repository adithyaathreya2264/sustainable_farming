"""A logged field operation (spray, irrigation, labour, harvest)."""

from __future__ import annotations

import enum

from sqlalchemy import Date, Enum as SQLEnum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, SyncMixin, TimestampMixin


class InterventionType(str, enum.Enum):
    chemical = "chemical"
    irrigation = "irrigation"
    labor = "labor"
    harvest = "harvest"


class Intervention(Base, TimestampMixin, SyncMixin):
    __tablename__ = "interventions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    planting_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plantings.id"), nullable=False, index=True
    )
    type: Mapped[InterventionType] = mapped_column(
        SQLEnum(InterventionType), nullable=False
    )
    # Nullable: only chemical-type interventions reference a catalog entry —
    # labor/irrigation/harvest interventions have no agri_catalog row.
    product_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("agri_catalog.id"), nullable=True
    )
    quantity_metric: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    quantity_unit: Mapped[str | None] = mapped_column(String(24), nullable=True)
    # Money — always Numeric, never Float.
    cost_in_inr: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    intervention_date: Mapped[Date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
