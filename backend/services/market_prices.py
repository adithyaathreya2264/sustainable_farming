"""Mandi price lookup.

The seeded data is a **single-day snapshot from 2019-03-04** of unverified
provenance. Two rules follow, and both are enforced here rather than left to
callers:

- No trend, average or direction-of-travel is computed or exposed. One day of
  data cannot support any of them.
- Every result carries its `snapshot_date` and `price_unit`, so a caller
  cannot render a price without having the date to render beside it.

This module is the seam for a live Agmarknet feed later: swap the query for a
client call and callers stay unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.market_price import MarketPrice


@dataclass(frozen=True)
class MarketPriceRow:
    state: str
    district: str
    market: str
    commodity: str
    variety: str | None
    min_price: int
    max_price: int
    modal_price: int
    price_unit: str
    snapshot_date: date
    # True when this listing is in the caller's own district, so the UI can
    # show local markets before the rest of the state without a second query.
    is_local: bool


def lookup(
    db: Session,
    *,
    commodity_key: str | None = None,
    commodity: str | None = None,
    state: str | None = None,
    district: str | None = None,
    limit: int = 50,
) -> list[MarketPriceRow]:
    """Listings for a commodity, best price first.

    `district` narrows but never excludes: markets elsewhere in the state are
    still returned, flagged `is_local=False`, because the nearest mandi is not
    always the one worth travelling to and a farmer comparing them needs both.
    Rows whose district could not be reconciled against `locations.json` are
    reachable through the state filter for exactly this reason.
    """
    statement = select(MarketPrice)

    if commodity_key:
        statement = statement.where(MarketPrice.commodity_key == commodity_key)
    elif commodity:
        statement = statement.where(MarketPrice.commodity == commodity)

    if state:
        statement = statement.where(MarketPrice.state == state)

    statement = statement.order_by(MarketPrice.modal_price.desc()).limit(limit)

    rows = db.scalars(statement).all()
    return [
        MarketPriceRow(
            state=row.state,
            district=row.district,
            market=row.market,
            commodity=row.commodity,
            variety=row.variety,
            min_price=row.min_price,
            max_price=row.max_price,
            modal_price=row.modal_price,
            price_unit=row.price_unit,
            snapshot_date=row.snapshot_date,
            is_local=bool(district) and row.district_canonical == district,
        )
        for row in rows
    ]


def commodities_for_state(db: Session, state: str) -> list[str]:
    """Distinct commodities quoted anywhere in a state, for a picker."""
    rows = db.scalars(
        select(MarketPrice.commodity)
        .where(MarketPrice.state == state)
        .distinct()
        .order_by(MarketPrice.commodity)
    ).all()
    return list(rows)
