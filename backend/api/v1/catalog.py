"""Server-owned reference-data read endpoints (crops/varieties, agri inputs).

Outside the sync protocol on purpose — `Crop`/`CropVariety`/`AgriCatalog` are
server-owned reference tables (see their own docstrings), not synced via
WatermelonDB's pull/push. Farmers select from these, they don't edit them,
so a plain authenticated read path is all that's needed.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.core.database import get_db
from backend.core.deps import get_current_user
from backend.models.agri_catalog import AgriCatalog
from backend.models.crop import Crop
from backend.models.user import User
from backend.schemas.catalog import AgriCatalogListOut, CropsListOut

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])


@router.get("/crops", response_model=CropsListOut)
def list_crops(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CropsListOut:
    # joinedload avoids an N+1 (one query per crop for its varieties) — small
    # dataset today, still worth not skipping.
    crops = db.scalars(
        select(Crop).options(joinedload(Crop.varieties)).where(Crop.active.is_(True))
    ).unique().all()
    return CropsListOut(items=list(crops))


@router.get("/agri-inputs", response_model=AgriCatalogListOut)
def list_agri_inputs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgriCatalogListOut:
    items = db.scalars(select(AgriCatalog).where(AgriCatalog.active.is_(True))).all()
    return AgriCatalogListOut(items=list(items))
