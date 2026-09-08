"""Mandi (wholesale market) price listings.

Seeded from `market_prices.json`. Server-owned reference data.

Two properties of the seeded source constrain every consumer, and both are
recorded on the row rather than left to documentation:

- `snapshot_date` — the dump is a **single day** (2019-03-04), so no trend,
  average or direction-of-travel claim can be drawn from it, and any displayed
  price must carry its date.
- `price_unit` — INR per quintal (100 kg). Unlike the yield dataset this unit
  *is* documented upstream and consistent, so it is stated rather than null.

`district` keeps the mandi's local name; `district_canonical` is the
`locations.json` spelling and is what a district filter joins on. It is
nullable on purpose: the dump uses pre-rename district names, and two of them
could not be placed without guessing (see `ml/prep/common.py`). Those rows
stay reachable by state rather than being dropped or misfiled.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin


class MarketPrice(Base, TimestampMixin):
    __tablename__ = "market_prices"
    __table_args__ = (
        # "what does this commodity fetch near me" — commodity first, then
        # place, which is the order every query narrows in.
        Index("ix_market_prices_lookup", "commodity_key", "state", "district_canonical"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    state: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    district: Mapped[str] = mapped_column(String(120), nullable=False)
    district_canonical: Mapped[str | None] = mapped_column(String(120), nullable=True)
    market: Mapped[str] = mapped_column(String(160), nullable=False)

    commodity: Mapped[str] = mapped_column(String(160), nullable=False)
    commodity_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    variety: Mapped[str | None] = mapped_column(String(160), nullable=True)

    min_price: Mapped[int] = mapped_column(Integer, nullable=False)
    max_price: Mapped[int] = mapped_column(Integer, nullable=False)
    modal_price: Mapped[int] = mapped_column(Integer, nullable=False)

    price_unit: Mapped[str] = mapped_column(String(40), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
