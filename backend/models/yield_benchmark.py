"""Typical-yield bands per crop, at three geographic/seasonal scopes.

Seeded from `crop_yield_benchmarks.json`. Server-owned reference data, not
synced.

## The unit caveat is structural, not advisory

The source dataset's yield column has **no usable unit** — it is not
`production / area` (they disagree in 69% of rows) and its scale differs per
crop (Coconut ~8,466, Sugarcane ~53, Rice ~2.2). See `datasets/README.md`.

Within a crop the values are consistent, so a band supports a *relative*
answer ("your yield sits around the 60th percentile for Rice in Karnataka,
Kharif"). It does not support an absolute one, which is why there is no
`unit` column to populate and `unit_note` is carried on every row: a
downstream reader who never opens the README still cannot miss it.

`scope` supports the same 3-tier fallback `services/soil_lookup.py` uses:

    state_season  ->  state  ->  national
"""

from __future__ import annotations

from sqlalchemy import Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin


class YieldBenchmark(Base, TimestampMixin):
    __tablename__ = "yield_benchmarks"
    __table_args__ = (
        # The lookup is always "this crop, narrowing by place then season",
        # so the index leads with crop_key.
        Index("ix_yield_benchmarks_lookup", "crop_key", "state", "season"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # Normalised slug from ml/prep/common.crop_key — joins a planting's crop to
    # a benchmark without either side knowing the other's naming style.
    # No index=True: ix_yield_benchmarks_lookup already leads with crop_key,
    # so a standalone index on it would be a redundant leftmost prefix.
    crop_key: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Set only for crops that exist in the `crops` table; free-text crops from
    # the dataset still get benchmarks, they just don't join to a Crop row.
    seeded_crop_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    scope: Mapped[str] = mapped_column(String(16), nullable=False)  # see module doc
    state: Mapped[str | None] = mapped_column(String(80), nullable=True)
    season: Mapped[str | None] = mapped_column(String(24), nullable=True)

    median: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    p25: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    p75: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)

    year_from: Mapped[int] = mapped_column(Integer, nullable=False)
    year_to: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_note: Mapped[str] = mapped_column(Text, nullable=False)
