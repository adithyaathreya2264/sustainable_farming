"""Server-internal OTP requests for phone-number verification (Slice 2 auth).

No SyncMixin — this never touches WatermelonDB, same reasoning as `User` in
`models/user.py`: it isn't farmer-editable offline data.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin


class OtpRequest(Base, TimestampMixin):
    __tablename__ = "otp_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # Never store the raw OTP — sha256 hex digest (see core/otp.py).
    otp_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    # Set on successful verify — makes the OTP single-use.
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(), nullable=True
    )
    # Incremented on each failed verify attempt; caps retries (see auth endpoint).
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
