"""Farmer field-scouting observation (Phase 4 follow-up).

A count a farmer records in the field — dead hearts %, pheromone-trap moths,
whorl-damage %, etc. Feeds `services/rule_engine.py`'s pest/ETL rules, which
key off a `condition_field` string; `metric_key` here holds that exact string.

Farmer-owned, planting-scoped, synced — same shape as `Intervention`
(ownership resolves through `planting_id -> field_id -> user_id`, no direct
`user_id` column). `metric_key` is a plain string, not a DB enum, so the set
of trackable metrics can grow with the rule matrix without a schema change;
the frontend constrains what a farmer can actually log.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, SyncMixin, TimestampMixin


class ScoutingObservation(Base, TimestampMixin, SyncMixin):
    __tablename__ = "scouting_observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    planting_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plantings.id"), nullable=False, index=True
    )
    # Matches AgronomicRule.condition_field exactly (e.g. "dead_hearts_percent").
    metric_key: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_value: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    observed_at: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
