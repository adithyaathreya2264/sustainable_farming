"""User identity. Not sync'd via SyncMixin — identity is not farmer-editable
offline data in the WatermelonDB sense.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # uuid4 as str
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    language_pref: Mapped[str] = mapped_column(String(8), nullable=False)
    default_unit: Mapped[str] = mapped_column(String(16), nullable=False)
    total_area_hectares: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    irrigation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(80), nullable=False)
    district: Mapped[str] = mapped_column(String(80), nullable=False)
    # Frontend onboarding gate. As of Slice 1 this is NOT checked server-side
    # anywhere — no auth middleware or sync-eligibility logic depends on it yet.
    # If that changes (e.g. block sync until onboarding done), note it here.
    onboarding_complete: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
