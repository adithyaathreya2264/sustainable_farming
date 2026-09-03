"""Government schemes (server-owned reference) and per-user matches (sync'd)."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, String, Text
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, SyncMixin, TimestampMixin, utcnow


class SchemeMatchStatus(str, enum.Enum):
    matched = "matched"
    viewed = "viewed"
    dismissed = "dismissed"
    claimed = "claimed"


class MatchConfidence(str, enum.Enum):
    """How much of a scheme's eligibility criteria this match actually
    checked, not just how solid the scheme's own published data is (Task 4.2)
    — e.g. PM-KISAN's figures are fully verified, but a match is still
    "provisional" if we can't check its exclusion criteria against `User`.
    """

    verified = "verified"
    provisional = "provisional"


class GovtScheme(Base, TimestampMixin):
    """Reference table. Server-owned, read-only to clients — not sync'd."""

    __tablename__ = "govt_schemes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scheme_name: Mapped[str] = mapped_column(String(200), nullable=False)
    authority: Mapped[str] = mapped_column(String(160), nullable=False)
    eligibility_criteria: Mapped[dict] = mapped_column(JSON, nullable=False)
    benefit_description: Mapped[str] = mapped_column(Text, nullable=False)
    application_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class SchemeMatch(Base, TimestampMixin, SyncMixin):
    """A scheme surfaced to a user. Sync'd (farmer can act on it)."""

    __tablename__ = "scheme_matches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    scheme_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("govt_schemes.id"), nullable=False, index=True
    )
    matched_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, default=utcnow
    )
    status: Mapped[SchemeMatchStatus] = mapped_column(
        SQLEnum(SchemeMatchStatus), nullable=False, default=SchemeMatchStatus.matched
    )
    match_confidence: Mapped[MatchConfidence] = mapped_column(
        SQLEnum(MatchConfidence), nullable=False
    )
