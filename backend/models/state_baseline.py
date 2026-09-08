"""State-level environmental baselines: soil nutrients and climate normals.

Both are server-owned reference data seeded from `backend/scripts/seed_data/`
(see `datasets/README.md` for provenance) — farmers never edit them, so
neither carries `SyncMixin`.

These answer "what is normal here", not "what is true on this field". A state
average is several orders of magnitude coarser than a soil test, and every
consumer is expected to present it as an estimate. `SoilBaseline` exists so
`services/soil_lookup.py` has something to fall back on when a farmer has no
soil report at all, not to substitute for one.
"""

from __future__ import annotations

from sqlalchemy import Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin


class SoilBaseline(Base, TimestampMixin):
    """Average N/P/K/pH for a state. One row per state."""

    __tablename__ = "soil_baselines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # unique=True already creates the index; index=True would add a second.
    state: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    n: Mapped[int] = mapped_column(Integer, nullable=False)
    p: Mapped[int] = mapped_column(Integer, nullable=False)
    k: Mapped[int] = mapped_column(Integer, nullable=False)
    # Numeric, not Float: pH is compared against crop targets and shown to the
    # farmer, and binary float drift on a value like 6.9 is avoidable noise.
    ph: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)


class StateClimateNormal(Base, TimestampMixin):
    """Multi-year climate normal for a state, with a rainfall spread.

    The p25/p75 rainfall band is the reason this table exists: `core/weather.py`
    already reports what the weather *is*, and a mean alone can't say whether a
    season is unusually dry. Comparing a live total against the band can.
    """

    __tablename__ = "state_climate_normals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # unique=True already creates the index; index=True would add a second.
    state: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    year_from: Mapped[int] = mapped_column(Integer, nullable=False)
    year_to: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_years: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_temp_c: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    avg_humidity_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    avg_rainfall_mm: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    rainfall_p25_mm: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    rainfall_p75_mm: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
