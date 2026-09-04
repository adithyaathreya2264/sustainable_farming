"""Batch government-scheme matching run (Phase 4).

Extracted out of `api/v1/internal.py` so it's callable from the HTTP route and
from `backend/scripts/run_batch.py`. `match_schemes` is DB-only (no outbound
calls), so the counter lock is short regardless — the counter bump still goes
after the user query, matching `recommendation_run`.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.sync_counter import bump_sync_counter
from backend.models.user import User
from backend.services.scheme_matcher import match_schemes


def run_scheme_matching(db: Session) -> dict[str, int]:
    users = db.scalars(
        select(User).where(User.onboarding_complete.is_(True))
    ).all()

    sync_version = bump_sync_counter(db)

    created = 0
    for user in users:
        created += len(match_schemes(user, db, sync_version))

    db.commit()
    return {"users_evaluated": len(users), "matches_created": created}
