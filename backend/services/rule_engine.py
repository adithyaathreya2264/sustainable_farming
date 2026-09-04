"""Rule-based prescriptive engine (Task 4.1).

`evaluate_planting` is deliberately narrow about what it trusts: every rule
in the current seed batch is `confidence != "verified"` (see
models/agronomic_rule.py, docs/agronomic-rules-draft.md), so every generated
Recommendation gets an explicit "[Unverified guidance]" prefix — the single
most important line in this file, per the Task 4.1 brief: it makes "don't
ship as advice" a property of the data, not just a warning in a doc.
"""

from __future__ import annotations

import operator as op_module
import uuid
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.agronomic_rule import AgronomicRule
from backend.models.base import utcnow
from backend.models.crop_growth_stage import DataConfidence
from backend.models.planting import Planting
from backend.models.recommendation import Recommendation, RecommendationStatus
from backend.services.growth_stage import current_growth_stage

_UNVERIFIED_PREFIX = "[Unverified guidance] "

_OPERATORS: dict[str, Callable[[Any, Any], bool]] = {
    ">=": op_module.ge,
    "<=": op_module.le,
    ">": op_module.gt,
    "<": op_module.lt,
    "==": op_module.eq,
    "!=": op_module.ne,
}


def _condition_met(
    rule: AgronomicRule, weather_snapshot: dict, scouting_observations: dict
) -> tuple[bool, Any]:
    """Returns (met, observed_value). A stage-only rule (no condition_field)
    is always met once its stage gate has already passed — this function is
    only reached after that check.
    """
    if rule.condition_field is None:
        return True, None

    # Scouting observations checked first — every seeded pest rule keys off
    # a farmer field-scouting count, not weather; this order just means a
    # future weather-gated rule works without code changes here.
    if rule.condition_field in scouting_observations:
        value = scouting_observations[rule.condition_field]
    elif rule.condition_field in weather_snapshot:
        value = weather_snapshot[rule.condition_field]
    else:
        return False, None

    comparator = _OPERATORS.get(rule.operator)
    if comparator is None:
        return False, None

    return bool(comparator(float(value), float(rule.threshold_value))), value


def evaluate_planting(
    planting: Planting,
    weather_snapshot: dict,
    scouting_observations: dict,
    db: Session,
    sync_version: int,
) -> list[Recommendation]:
    """`sync_version` is obtained by the caller (one `bump_sync_counter` per
    batch run — see api/v1/internal.py — not one per planting/row), so every
    Recommendation created across a whole trigger-endpoint run shares it,
    matching the push endpoint's granularity (Slice 3)."""
    stage = current_growth_stage(planting, db)

    rules = db.scalars(
        select(AgronomicRule).where(
            AgronomicRule.crop_id == planting.crop_id,
            AgronomicRule.active.is_(True),
        )
    ).all()

    new_recommendations: list[Recommendation] = []

    for rule in rules:
        if stage is None or rule.stage_name != stage:
            continue

        met, observed_value = _condition_met(rule, weather_snapshot, scouting_observations)
        if not met:
            continue

        # Idempotency: don't spam duplicates on repeated trigger-endpoint runs.
        already_pending = db.scalar(
            select(Recommendation.id).where(
                Recommendation.planting_id == planting.id,
                Recommendation.rule_code == rule.rule_code,
                Recommendation.status == RecommendationStatus.pending,
                Recommendation.deleted_at.is_(None),
            )
        )
        if already_pending:
            continue

        text = rule.recommendation_text
        if rule.confidence != DataConfidence.verified:
            text = _UNVERIFIED_PREFIX + text

        trigger_snapshot = {
            "stage": stage,
            "condition_field": rule.condition_field,
            "observed_value": observed_value,
            "threshold_value": (
                float(rule.threshold_value) if rule.threshold_value is not None else None
            ),
        }

        new_recommendations.append(
            Recommendation(
                id=str(uuid.uuid4()),
                planting_id=planting.id,
                rule_code=rule.rule_code,
                trigger_snapshot=trigger_snapshot,
                recommendation_text=text,
                severity=rule.severity,
                confidence=rule.confidence,
                status=RecommendationStatus.pending,
                generated_at=utcnow(),
                sync_version=sync_version,
                created_sync_version=sync_version,
            )
        )

    for rec in new_recommendations:
        db.add(rec)

    return new_recommendations
