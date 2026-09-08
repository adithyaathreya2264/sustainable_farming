"""Response shapes for GET /api/v1/market/*.

`snapshot_date` and `price_unit` are required on every price row, not
optional. The seeded data is a single stale day (see
`services/market_prices.py`), and a schema that let a client render a price
without its date would make it easy to present 2019 figures as current.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class MarketPriceOut(BaseModel):
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
    is_local: bool


class MarketPriceListOut(BaseModel):
    prices: list[MarketPriceOut]
    # Repeated at the envelope level so a client showing a header ("Prices as
    # of ...") doesn't have to reach into the first row for it.
    snapshot_date: date | None
    is_live: bool
    note: str


class CommodityListOut(BaseModel):
    commodities: list[str]
