"""User-profile read/update (`/api/v1/users/me`).

Closes the gap FRONTEND_BACKEND_GAP_ANALYSIS.md §1 flagged: the frontend
collected the whole farmer profile in onboarding but had no endpoint to
persist it, so `users.onboarding_complete` was never set and
`run-scheme-matching` (which filters on it) matched nobody.

Behind the normal farmer `get_current_user` JWT auth. Identity comes from the
token — the path is always the caller's own row, never an arbitrary id.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.deps import get_current_user
from backend.models.base import utcnow
from backend.models.user import User
from backend.schemas.users import UserProfileOut, UserProfileUpdateIn

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/me", response_model=UserProfileOut)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserProfileOut)
def update_me(
    body: UserProfileUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    # exclude_unset: a PATCH that only sends `default_unit` must not blank out
    # every other column with its Pydantic default.
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(current_user, field, value)
    current_user.updated_at = utcnow()
    db.add(current_user)
    db.commit()
    return current_user
