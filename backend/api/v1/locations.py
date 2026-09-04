"""State / district reference for the onboarding location pickers.

Server-owned reference data (like catalog / schemes), moved out of the
frontend bundle. Grouped by state so the frontend can drive its two-step
picker without any client-side reshaping. Behind the normal farmer JWT —
onboarding runs after OTP verify, so a token always exists by then.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.deps import get_current_user
from backend.models.location import Location
from backend.models.user import User
from backend.schemas.locations import LocationsListOut, StateDistrictsOut

router = APIRouter(prefix="/api/v1/locations", tags=["locations"])


@router.get("", response_model=LocationsListOut)
def list_locations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LocationsListOut:
    rows = db.execute(
        select(Location.state, Location.district)
        .where(Location.active.is_(True))
        .order_by(Location.state, Location.district)
    ).all()

    grouped: dict[str, list[str]] = {}
    for state, district in rows:
        grouped.setdefault(state, []).append(district)

    return LocationsListOut(
        items=[
            StateDistrictsOut(state=state, districts=districts)
            for state, districts in grouped.items()
        ]
    )
