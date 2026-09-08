"""Soil-type lookup by location, with graceful degradation.

This is the seam: callers (the soil-lookup endpoint, and eventually
recommendation logic) only ever call `get_soil_type()` — never touch the
underlying data source directly. When a real soil-survey table exists, only
this file changes.

# TODO(real-soil-db): replace _PLACEHOLDER_ROWS + the lookup below with a
# real query once the actual soil-survey schema/data source is confirmed.
The 3-tier fallback logic (taluk -> district -> none) is the real, considered
design here and should carry over unchanged; only the data source swaps.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.state_baseline import SoilBaseline


@dataclass(frozen=True)
class SoilLookupResult:
    soil_type: str
    confidence: Literal["taluk", "district"]
    source: str


@dataclass(frozen=True)
class SoilNutrients:
    n: int
    p: int
    k: int
    ph: Decimal
    # Only "state" today. Named rather than hardcoded so that when a real
    # soil-survey source arrives, a caller can tell a district-level reading
    # from a state average without inspecting where it came from.
    confidence: Literal["state"]
    source: str


@dataclass(frozen=True)
class _Row:
    state: str
    district: str
    taluk: str | None  # None = district-representative row (the fallback tier)
    soil_type: str


# Placeholder data — a handful of real Karnataka districts, enough to
# exercise all three fallback tiers:
#   - Mysuru: has taluk-level rows AND an explicit district-representative
#     row (taluk=None) for taluks not individually listed.
#   - Mandya: same shape, different soil.
#   - Belagavi: district-representative row ONLY — demonstrates a district
#     with no taluk-level data at all, still resolving via the district tier.
_PLACEHOLDER_ROWS: list[_Row] = [
    _Row("Karnataka", "Mysuru", "Mysuru", "Red Sandy Loam"),
    _Row("Karnataka", "Mysuru", "T. Narasipura", "Red Loamy Soil"),
    _Row("Karnataka", "Mysuru", None, "Red Loamy Soil"),
    _Row("Karnataka", "Mandya", "Mandya", "Black Cotton Soil"),
    _Row("Karnataka", "Mandya", None, "Black Cotton Soil"),
    _Row("Karnataka", "Belagavi", None, "Black Soil"),
]


def _norm(value: str | None) -> str | None:
    return value.strip().lower() if value else None


def get_soil_type(
    state: str, district: str, taluk: str | None = None
) -> SoilLookupResult | None:
    """3-tier fallback: exact (state+district+taluk) -> district-representative
    row -> any row for that district -> None (no suggestion available).
    """
    n_state, n_district, n_taluk = _norm(state), _norm(district), _norm(taluk)

    district_rows = [
        row
        for row in _PLACEHOLDER_ROWS
        if _norm(row.state) == n_state and _norm(row.district) == n_district
    ]
    if not district_rows:
        return None

    if n_taluk:
        for row in district_rows:
            if _norm(row.taluk) == n_taluk:
                return SoilLookupResult(row.soil_type, "taluk", "placeholder")

    # No taluk match (or none given) — prefer an explicit district-representative
    # row; fall back to any row for the district if no such row exists.
    representative = next((r for r in district_rows if r.taluk is None), None)
    row = representative or district_rows[0]
    return SoilLookupResult(row.soil_type, "district", "placeholder")


def get_soil_nutrients(db: Session, state: str) -> SoilNutrients | None:
    """Average N/P/K/pH for a state, or None if the state isn't covered.

    Separate from `get_soil_type` on purpose. Soil *type* is a categorical
    property that varies by taluk and comes from the placeholder table above;
    soil *nutrients* are a numeric state average from a seeded dataset
    (`soil_baselines`). They have different sources, different granularity and
    different failure modes, so folding them into one call would misrepresent
    the nutrient figure as being as local as the type.

    This is emphatically not a soil test — 30 rows covering all of India. It
    exists so a form can be pre-filled and so `fertilizer_advice` has an input
    when the farmer has no soil report, and callers must label it an estimate.
    """
    row = db.scalar(select(SoilBaseline).where(SoilBaseline.state == state))
    if row is None:
        return None
    return SoilNutrients(
        n=row.n,
        p=row.p,
        k=row.k,
        ph=row.ph,
        confidence="state",
        source="state-average dataset",
    )
