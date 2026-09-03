"""Shared FastAPI dependencies. `get_current_user` is Slice 2's deferred
"used later" auth dependency, now mandatory for the sync endpoints (Slice 3)
and any future protected endpoint.
"""

from __future__ import annotations

import hmac

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.jwt import decode_access_token
from backend.models.user import User

_bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(credentials.credentials)
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        raise unauthorized

    user_id = payload.get("user_id")
    if not user_id:
        raise unauthorized

    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise unauthorized

    return user


def require_internal_key(x_internal_key: str | None = Header(None)) -> None:
    """Guards /api/v1/internal/* — cron-triggered batch endpoints, not a
    farmer's JWT (a farmer's device has no business calling these, and a
    stolen farmer JWT shouldn't be able to either). Missing and wrong keys
    both read as the same 403 — optional header + explicit None-check rather
    than `Header(...)`, so a missing key doesn't fall through to FastAPI's
    generic 422 validation error instead.
    """
    if not x_internal_key or not hmac.compare_digest(
        x_internal_key, settings.internal_api_key
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid internal key."
        )
