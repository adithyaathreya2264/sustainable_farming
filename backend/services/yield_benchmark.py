"""Typical-yield lookup, with the same 3-tier fallback as `soil_lookup`.

    state_season  ->  state  ->  national  ->  None

## What this deliberately does not return

An absolute yield figure with a unit. The source dataset's yield column has no
usable unit — it is not `production / area` (they disagree in 69% of rows) and
its scale differs per crop (Coconut ~8,466, Sugarcane ~53, Rice ~2.2). See
`datasets/README.md` and `models/yield_benchmark.py`.

Within one crop the numbers are consistent, so this module answers a
*relative* question — where a farmer's own figure sits in the distribution for
their crop, state and season — and hands back `unit_note` so a caller that
renders a raw median cannot do so without the caveat in hand. `position_of()`
is the intended entry point for anything user-facing; `get_benchmark()` is
there for callers that need the band itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.yield_benchmark import YieldBenchmark

Scope = Literal["state_season", "state", "national"]


@dataclass(frozen=True)
class BenchmarkResult:
    crop_key: str
    display_name: str
    scope: Scope
    state: str | None
    season: str | None
    median: Decimal
    p25: Decimal
    p75: Decimal
    sample_count: int
    year_from: int
    year_to: int
    unit_note: str


@dataclass(frozen=True)
class YieldPosition:
    """Where an observed yield sits relative to its benchmark band."""

    benchmark: BenchmarkResult
    observed: Decimal
    # Coarse and honest. The stored band is only p25/median/p75, so a precise
    # percentile would be interpolation dressed up as measurement.
    band: Literal["below_typical", "typical", "above_typical"]


def _to_result(row: YieldBenchmark) -> BenchmarkResult:
    return BenchmarkResult(
        crop_key=row.crop_key,
        display_name=row.display_name,
        scope=row.scope,  # type: ignore[arg-type]
        state=row.state,
        season=row.season,
        median=row.median,
        p25=row.p25,
        p75=row.p75,
        sample_count=row.sample_count,
        year_from=row.year_from,
        year_to=row.year_to,
        unit_note=row.unit_note,
    )


def get_benchmark(
    db: Session,
    crop_key: str,
    state: str | None = None,
    season: str | None = None,
) -> BenchmarkResult | None:
    """Narrowest available band for this crop, widening until one is found."""
    attempts: list[tuple[Scope, str | None, str | None]] = []
    if state and season:
        attempts.append(("state_season", state, season))
    if state:
        attempts.append(("state", state, None))
    attempts.append(("national", None, None))

    for scope, scope_state, scope_season in attempts:
        row = db.scalar(
            select(YieldBenchmark).where(
                YieldBenchmark.crop_key == crop_key,
                YieldBenchmark.scope == scope,
                YieldBenchmark.state.is_(None)
                if scope_state is None
                else YieldBenchmark.state == scope_state,
                YieldBenchmark.season.is_(None)
                if scope_season is None
                else YieldBenchmark.season == scope_season,
            )
        )
        if row is not None:
            return _to_result(row)

    return None


def position_of(
    db: Session,
    crop_key: str,
    observed_yield: Decimal | float | int,
    state: str | None = None,
    season: str | None = None,
) -> YieldPosition | None:
    """Place an observed yield against the narrowest available band.

    Returns None when no band exists for the crop — the caller shows nothing
    rather than comparing against a national figure that doesn't apply.
    """
    benchmark = get_benchmark(db, crop_key, state, season)
    if benchmark is None:
        return None

    observed = Decimal(str(observed_yield))
    if observed < benchmark.p25:
        band: Literal["below_typical", "typical", "above_typical"] = "below_typical"
    elif observed > benchmark.p75:
        band = "above_typical"
    else:
        band = "typical"

    return YieldPosition(benchmark=benchmark, observed=observed, band=band)
