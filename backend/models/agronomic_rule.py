"""Agronomic rule matrix (Task 4.1) — resolves Task 2.5's draft into schema.

Server-owned reference, not synced. `condition_field`/`operator`/
`threshold_value` are the nullable trio: null on all three means the rule
fires on reaching `stage_name` alone (irrigation-critical-stage rules);
populated means a scouting/weather observation is also checked (pest ETL
rules). `stage_name` itself is NOT nullable here — every rule in this v1
batch specifies one (see the Task 4.1 plan notes on why the original
"nullable stage_name" design didn't match the real draft data).

`confidence`/`source` make the rule matrix's "draft, not ready-to-ship"
status structural: `rule_engine.py` prefixes recommendation_text with an
"[Unverified guidance]" marker for anything not `confidence == verified` —
which, in this seed batch, is everything.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Enum as SQLEnum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin
from backend.models.crop_growth_stage import DataConfidence
from backend.models.recommendation import RecommendationSeverity


class AgronomicRule(Base, TimestampMixin):
    __tablename__ = "agronomic_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    rule_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    crop_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("crops.id"), nullable=False, index=True
    )
    stage_name: Mapped[str] = mapped_column(String(80), nullable=False)
    condition_field: Mapped[str | None] = mapped_column(String(64), nullable=True)
    operator: Mapped[str | None] = mapped_column(String(8), nullable=True)
    threshold_value: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    severity: Mapped[RecommendationSeverity] = mapped_column(
        SQLEnum(RecommendationSeverity), nullable=False
    )
    recommendation_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[DataConfidence] = mapped_column(
        SQLEnum(DataConfidence), nullable=False
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
