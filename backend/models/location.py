"""State / district reference data for the onboarding location pickers.

Server-owned reference table — farmers select from it, they don't edit it
(same precedent as `Crop` / `GovtScheme`). One row per (state, district).
Seeded by `backend/scripts/seed_reference_data.py` from
`backend/scripts/seed_data/locations.json`.
"""

from __future__ import annotations

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin


class Location(Base, TimestampMixin):
    __tablename__ = "locations"
    __table_args__ = (UniqueConstraint("state", "district", name="uq_locations_state_district"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    state: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    district: Mapped[str] = mapped_column(String(80), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
