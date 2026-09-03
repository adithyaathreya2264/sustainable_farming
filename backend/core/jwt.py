"""JWT issuance/verification for the phone+OTP auth flow.

`decode_access_token` raises on an expired or invalid signature so callers
(the future `get_current_user` dependency that protects other endpoints) can
catch it cleanly rather than getting a silently-wrong payload back.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from backend.core.config import settings


def create_access_token(user_id: str, phone_number: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "phone_number": phone_number,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expiry_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Raises jwt.ExpiredSignatureError / jwt.InvalidTokenError on failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
