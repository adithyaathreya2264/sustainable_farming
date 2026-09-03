"""Farmer-facing alert feed (Phase 4 Part 2) — resolves the delivery gap
STATE_OF_THE_SYSTEM.md §2.3/§2.4 flagged: Recommendation/SchemeMatch rows
existed in the DB (Phase 4 Part 1) with no way for a farmer to see them.

Deliberately NOT the WatermelonDB-shaped sync protocol (api/v1/sync.py) —
farmers view and respond to alerts, they never create them, so a plain
fetch + narrow status-only PATCH fits better than full bidirectional sync.
Behind the normal farmer `get_current_user` auth — no internal-key here.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.deps import get_current_user
from backend.models.base import utcnow
from backend.models.crop_growth_stage import DataConfidence
from backend.models.field import Field
from backend.models.planting import Planting
from backend.models.recommendation import Recommendation, RecommendationStatus
from backend.models.scheme import (
    GovtScheme,
    MatchConfidence,
    SchemeMatch,
    SchemeMatchStatus,
)
from backend.models.user import User
from backend.schemas.alerts import AlertOut, AlertsListOut, AlertStatusIn
from backend.services.ownership import planting_owner

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])

# Two different confidence *scales* unified into one label — see the Phase 4
# Part 2 plan's "Additional gaps found" for the reasoning. Recommendation's
# low/medium both collapse to "unverified": the point of the label is
# "vetted or not", not a 3-way distinction a farmer doesn't need.
_RECOMMENDATION_LABEL = {
    DataConfidence.low: "unverified",
    DataConfidence.medium: "unverified",
    DataConfidence.verified: "verified",
}
_SCHEME_LABEL = {
    MatchConfidence.provisional: "provisional",
    MatchConfidence.verified: "verified",
}

_ALLOWED_STATUS: dict[str, set[str]] = {
    "recommendation": {"acknowledged", "followed", "ignored"},
    "scheme_match": {"viewed", "dismissed", "claimed"},
}


def _flatten_eligibility(criteria: dict[str, Any]) -> list[str]:
    """GovtScheme.eligibility_criteria's JSON shape varies per scheme (see
    docs/govt-schemes-sourcing.md) — flattened here so the frontend doesn't
    need per-scheme parsing logic."""
    lines: list[str] = []
    for key, value in criteria.items():
        label = key.replace("_", " ").capitalize()
        if isinstance(value, list):
            lines.extend(f"{label}: {item}" for item in value)
        else:
            lines.append(f"{label}: {value}")
    return lines


def _recommendation_to_alert(rec: Recommendation) -> AlertOut:
    return AlertOut(
        id=rec.id,
        kind="recommendation",
        severity=rec.severity.value,
        status=rec.status.value,
        headline=rec.recommendation_text,
        detail=None,
        confidence_label=_RECOMMENDATION_LABEL[rec.confidence],
        generated_at=rec.generated_at,
        planting_id=rec.planting_id,
    )


def _scheme_match_to_alert(match: SchemeMatch, scheme: GovtScheme) -> AlertOut:
    return AlertOut(
        id=match.id,
        kind="scheme_match",
        severity=None,
        status=match.status.value,
        headline=scheme.scheme_name,
        detail=scheme.benefit_description,
        confidence_label=_SCHEME_LABEL[match.match_confidence],
        application_url=scheme.application_url,
        authority=scheme.authority,
        eligibility_summary=_flatten_eligibility(scheme.eligibility_criteria),
        generated_at=match.matched_at,
    )


@router.get("", response_model=AlertsListOut)
def list_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AlertsListOut:
    recommendations = db.scalars(
        select(Recommendation)
        .join(Planting, Recommendation.planting_id == Planting.id)
        .join(Field, Planting.field_id == Field.id)
        .where(Field.user_id == current_user.id, Recommendation.deleted_at.is_(None))
    ).all()

    scheme_matches = db.scalars(
        select(SchemeMatch).where(
            SchemeMatch.user_id == current_user.id, SchemeMatch.deleted_at.is_(None)
        )
    ).all()
    scheme_ids = {m.scheme_id for m in scheme_matches}
    schemes_by_id = {
        s.id: s
        for s in db.scalars(select(GovtScheme).where(GovtScheme.id.in_(scheme_ids))).all()
    }

    items = [_recommendation_to_alert(r) for r in recommendations] + [
        _scheme_match_to_alert(m, schemes_by_id[m.scheme_id])
        for m in scheme_matches
        if m.scheme_id in schemes_by_id
    ]
    items.sort(key=lambda a: a.generated_at, reverse=True)

    return AlertsListOut(items=items)


@router.patch("/{kind}/{alert_id}", response_model=AlertOut)
def update_alert_status(
    kind: str,
    alert_id: str,
    body: AlertStatusIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AlertOut:
    allowed = _ALLOWED_STATUS.get(kind)
    if allowed is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown alert kind.")
    if body.status not in allowed:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Invalid status {body.status!r} for kind {kind!r}. Allowed: {sorted(allowed)}.",
        )

    if kind == "recommendation":
        rec = db.get(Recommendation, alert_id)
        if rec is None or rec.deleted_at is not None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Recommendation not found.")
        if planting_owner(db, rec.planting_id) != current_user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your data.")
        # Explicit enum construction, not a bare string assignment: the
        # session is expire_on_commit=False (core/database.py), so the
        # in-Python attribute never gets refreshed from the DB as an Enum
        # after commit — a raw string here would make rec.status.value
        # blow up in _recommendation_to_alert below.
        rec.status = RecommendationStatus(body.status)
        rec.responded_at = utcnow()
        db.commit()
        return _recommendation_to_alert(rec)

    match = db.get(SchemeMatch, alert_id)
    if match is None or match.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scheme match not found.")
    if match.user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your data.")
    match.status = SchemeMatchStatus(body.status)
    db.commit()
    scheme = db.get(GovtScheme, match.scheme_id)
    return _scheme_match_to_alert(match, scheme)
