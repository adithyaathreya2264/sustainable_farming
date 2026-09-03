"""Farm field / plot."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, SyncMixin, TimestampMixin


class Field(Base, TimestampMixin, SyncMixin):
    __tablename__ = "fields"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Canonical area in hectares, derived in Python (Shapely) from `boundary`.
    area_size_hectares: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    # `lat`/`long` are a display-only map pin (centroid of `boundary`). The actual
    # field shape lives in `boundary` — a field has BOTH a point and a polygon on
    # purpose: the point for cheap list/map rendering without parsing the polygon.
    # Plain Numeric lat/long avoids SRID / ST_Area friction vs a native POINT.
    lat: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    long: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    # Polygon vertices as a list of {"lat": .., "long": ..}, in the order drawn
    # (>= 3). This is the source of truth for the field's shape and area.
    boundary: Mapped[list] = mapped_column(JSON, nullable=False)
    soil_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
