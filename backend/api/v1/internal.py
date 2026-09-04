"""Batch endpoints (Phase 4). Secured by a shared internal key
(core/deps.py:require_internal_key), not farmer JWT.

The logic lives in `services/recommendation_run.py` / `services/scheme_run.py`
so it's callable both here (HTTP) and from `backend/scripts/run_batch.py`
(the scheduler entry point — see backend/README-ops.md). These routes stay for
manual triggering / health checks / an external HTTP cron.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.deps import require_internal_key
from backend.services.recommendation_run import run_recommendations
from backend.services.scheme_run import run_scheme_matching

router = APIRouter(
    prefix="/api/v1/internal",
    tags=["internal"],
    dependencies=[Depends(require_internal_key)],
)


@router.post("/run-recommendations")
def run_recommendations_endpoint(db: Session = Depends(get_db)) -> dict[str, int]:
    return run_recommendations(db)


@router.post("/run-scheme-matching")
def run_scheme_matching_endpoint(db: Session = Depends(get_db)) -> dict[str, int]:
    return run_scheme_matching(db)
