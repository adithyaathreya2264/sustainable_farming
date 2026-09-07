"""Mandi price endpoints.

New capability — the app had no market/price feature at all before this.

Behind normal farmer auth. Both routes default their `state` to the caller's
own profile state, so the common case ("what is my crop fetching near me")
needs no query parameters beyond the commodity.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.deps import get_current_user
from backend.models.user import User
from backend.schemas.market import (
    CommodityListOut,
    MarketPriceListOut,
    MarketPriceOut,
)
from backend.services.market_prices import commodities_for_state, lookup

router = APIRouter(prefix="/api/v1/market", tags=["market"])

_STALE_NOTE = (
    "Prices are from a static snapshot of unverified provenance, not a live "
    "feed. Check your local mandi before acting on them."
)


@router.get("/prices", response_model=MarketPriceListOut)
def market_prices(
    commodity_key: str | None = Query(
        None, description="Normalised crop slug, e.g. 'okra'"
    ),
    commodity: str | None = Query(None, description="Exact commodity name"),
    state: str | None = Query(None),
    district: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MarketPriceListOut:
    # Default to the farmer's own location rather than returning all-India:
    # a national list sorted by price is noise to someone deciding where to
    # cart their harvest.
    effective_state = state or current_user.state
    effective_district = district or current_user.district

    rows = lookup(
        db,
        commodity_key=commodity_key,
        commodity=commodity,
        state=effective_state,
        district=effective_district,
        limit=limit,
    )

    return MarketPriceListOut(
        prices=[MarketPriceOut(**row.__dict__) for row in rows],
        snapshot_date=rows[0].snapshot_date if rows else None,
        is_live=False,
        note=_STALE_NOTE,
    )


@router.get("/commodities", response_model=CommodityListOut)
def market_commodities(
    state: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CommodityListOut:
    effective_state = state or current_user.state
    if not effective_state:
        return CommodityListOut(commodities=[])
    return CommodityListOut(commodities=commodities_for_state(db, effective_state))
