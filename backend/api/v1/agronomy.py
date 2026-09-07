"""Yield-benchmark and fertiliser-gap endpoints.

Both take a `crop_key` (the normalised slug from `ml/prep/common.crop_key`)
rather than a `crop_id`, because the seeded reference data covers far more
crops than the five rows in the `crops` table — keying off `Crop.id` would
make 90+ crops' benchmarks unreachable for no benefit.

`/fertilizer-advice` resolves the soil reading itself: a caller-supplied
reading wins, otherwise it falls back to the state average via
`services/soil_lookup.get_soil_nutrients`. Which source was used is reported
back in `soil_source`, because the advice means something quite different
depending on the answer.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.deps import get_current_user
from backend.models.user import User
from backend.schemas.agronomy import (
    FertilizerAdviceOut,
    SoilNutrientsOut,
    YieldBenchmarkOut,
    YieldPositionOut,
)
from backend.services.fertilizer_advice import advise
from backend.services.soil_lookup import get_soil_nutrients
from backend.services.yield_benchmark import get_benchmark, position_of

router = APIRouter(prefix="/api/v1", tags=["agronomy"])


@router.get("/yield-benchmark", response_model=YieldBenchmarkOut)
def yield_benchmark(
    crop_key: str = Query(...),
    state: str | None = Query(None),
    season: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> YieldBenchmarkOut:
    result = get_benchmark(db, crop_key, state or current_user.state, season)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No yield benchmark for crop {crop_key!r}.",
        )
    return YieldBenchmarkOut(**result.__dict__)


@router.get("/yield-position", response_model=YieldPositionOut)
def yield_position(
    crop_key: str = Query(...),
    observed_yield: Decimal = Query(..., gt=0),
    state: str | None = Query(None),
    season: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> YieldPositionOut:
    result = position_of(
        db, crop_key, observed_yield, state or current_user.state, season
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No yield benchmark for crop {crop_key!r}.",
        )
    return YieldPositionOut(
        benchmark=YieldBenchmarkOut(**result.benchmark.__dict__),
        observed=result.observed,
        band=result.band,
    )


@router.get("/soil-nutrients", response_model=SoilNutrientsOut)
def soil_nutrients(
    state: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SoilNutrientsOut:
    result = get_soil_nutrients(db, state or current_user.state)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No soil baseline for that state.",
        )
    return SoilNutrientsOut(**result.__dict__)


@router.get("/fertilizer-advice", response_model=FertilizerAdviceOut)
def fertilizer_advice(
    crop_key: str = Query(...),
    n: Decimal | None = Query(None, ge=0),
    p: Decimal | None = Query(None, ge=0),
    k: Decimal | None = Query(None, ge=0),
    ph: Decimal | None = Query(None, gt=0, le=14),
    state: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FertilizerAdviceOut:
    # All three of N/P/K must be supplied together — mixing a measured N with
    # a state-average P and K would produce a gap report that is part
    # measurement and part estimate, with no way to tell which is which.
    supplied = [value for value in (n, p, k) if value is not None]
    if supplied and len(supplied) != 3:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Supply all of n, p and k together, or none of them.",
        )

    if supplied:
        reading_n, reading_p, reading_k = n, p, k
        reading_ph = ph
        soil_source = "caller-supplied reading"
    else:
        baseline = get_soil_nutrients(db, state or current_user.state)
        if baseline is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "No soil reading supplied and no state baseline available "
                    "for that state."
                ),
            )
        reading_n, reading_p, reading_k = baseline.n, baseline.p, baseline.k
        reading_ph = ph if ph is not None else baseline.ph
        soil_source = f"state average ({baseline.source})"

    result = advise(
        db,
        crop_key,
        n=reading_n,
        p=reading_p,
        k=reading_k,
        ph=reading_ph,
        soil_source=soil_source,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No nutrient target for crop {crop_key!r}.",
        )

    return FertilizerAdviceOut(
        crop_key=result.crop_key,
        display_name=result.display_name,
        gaps=[gap.__dict__ for gap in result.gaps],  # type: ignore[list-item]
        soil_source=result.soil_source,
        caveat=result.caveat,
    )
