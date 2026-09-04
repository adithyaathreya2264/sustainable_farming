"""Batch recommendation run (Phase 4).

Extracted out of `api/v1/internal.py` so the same logic is callable from the
HTTP route *and* from `backend/scripts/run_batch.py` (the scheduler entry
point).

Lock ordering note: `bump_sync_counter` takes a `SELECT ... FOR UPDATE` on the
single `sync_counter` row and holds it until the transaction commits. A
concurrent farmer sync push also bumps that counter. So every outbound
Open-Meteo call is done *before* the bump — the write transaction only spans
fast, DB-only work (`evaluate_planting`), not network latency.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.sync_counter import bump_sync_counter
from backend.core.weather import get_weather_snapshot
from backend.models.base import utcnow
from backend.models.field import Field
from backend.models.planting import Planting, PlantingStatus
from backend.models.scouting_observation import ScoutingObservation
from backend.services.rule_engine import evaluate_planting

# A scouting count older than this is treated as stale and not fed to the rule
# engine (otherwise an old dead-heart reading would keep re-firing a rule).
_SCOUTING_RECENCY_DAYS = 14


def _scouting_for_planting(db: Session, planting_id: str) -> dict[str, float]:
    """Latest non-deleted value per `metric_key` for this planting, within the
    recency window — shaped exactly as `rule_engine._condition_met` expects
    (``{condition_field: value}``)."""
    cutoff = utcnow().date() - timedelta(days=_SCOUTING_RECENCY_DAYS)
    rows = db.scalars(
        select(ScoutingObservation)
        .where(
            ScoutingObservation.planting_id == planting_id,
            ScoutingObservation.deleted_at.is_(None),
            ScoutingObservation.observed_at >= cutoff,
        )
        .order_by(ScoutingObservation.observed_at.desc())
    ).all()

    latest: dict[str, float] = {}
    for row in rows:  # newest-first — first value seen per key wins
        latest.setdefault(row.metric_key, float(row.metric_value))
    return latest


def run_recommendations(db: Session) -> dict[str, int]:
    active_plantings = db.scalars(
        select(Planting).where(
            Planting.status == PlantingStatus.active,
            Planting.deleted_at.is_(None),
        )
    ).all()

    # Gather every outbound/read input BEFORE opening the counter lock.
    inputs: list[tuple[Planting, dict, dict[str, float]]] = []
    for planting in active_plantings:
        field = db.get(Field, planting.field_id)
        weather_snapshot = get_weather_snapshot(float(field.lat), float(field.long))
        scouting = _scouting_for_planting(db, planting.id)
        inputs.append((planting, weather_snapshot, scouting))

    sync_version = bump_sync_counter(db)

    created = 0
    for planting, weather_snapshot, scouting in inputs:
        new_recs = evaluate_planting(
            planting, weather_snapshot, scouting, db, sync_version
        )
        created += len(new_recs)

    db.commit()
    return {
        "plantings_evaluated": len(active_plantings),
        "recommendations_created": created,
    }
