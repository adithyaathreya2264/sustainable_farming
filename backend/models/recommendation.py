"""Rule-engine recommendation attached to a planting.

Schema follows the redesign in ``backend/plan/slice1.txt``, which differs from
the frontend mock ``Recommendation`` (title / description / confidencePct). The
frontend service layer will need a small adapter when it swaps to the real API.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, String, Text
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, SyncMixin, TimestampMixin, utcnow
from backend.models.crop_growth_stage import DataConfidence


class RecommendationSeverity(str, enum.Enum):
    info = "info"
    advisory = "advisory"
    critical = "critical"


class RecommendationStatus(str, enum.Enum):
    pending = "pending"
    acknowledged = "acknowledged"
    followed = "followed"
    ignored = "ignored"


class Recommendation(Base, TimestampMixin, SyncMixin):
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    planting_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plantings.id"), nullable=False, index=True
    )
    rule_code: Mapped[str] = mapped_column(String(64), nullable=False)
    # Snapshot of the inputs that fired the rule (weather, stage, history, ...).
    trigger_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    recommendation_text: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[RecommendationSeverity] = mapped_column(
        SQLEnum(RecommendationSeverity), nullable=False
    )
    # Copied from AgronomicRule.confidence at creation (services/rule_engine.py)
    # — lets API consumers (api/v1/alerts.py) map a confidence_label without
    # parsing the "[Unverified guidance] " text prefix on recommendation_text.
    confidence: Mapped[DataConfidence] = mapped_column(
        SQLEnum(DataConfidence), nullable=False
    )
    status: Mapped[RecommendationStatus] = mapped_column(
        SQLEnum(RecommendationStatus),
        nullable=False,
        default=RecommendationStatus.pending,
    )
    farmer_feedback_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, default=utcnow
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(), nullable=True
    )
