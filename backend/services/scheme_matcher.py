"""Government scheme matcher (Task 4.2).

Matches only what `User` can actually represent today. Neither PM-KISAN's
exclusion criteria (income tax, government employment, pension, licensed
professional) nor Krishi Bhagya's SC/ST tier exist as `User` fields — every
match's `match_confidence` reflects that, not just each scheme's own
data quality. In practice this means most v1 matches land on "provisional"
regardless of scheme, which is the honest state of things, not a bug.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.base import utcnow
from backend.models.scheme import (
    GovtScheme,
    MatchConfidence,
    SchemeMatch,
    SchemeMatchStatus,
)
from backend.models.user import User

_ONE_ACRE_HECTARES = Decimal("0.4047")

# Scheme-specific matchers: (scheme_name, predicate, confidence).
# scheme_name matches GovtScheme.scheme_name exactly, as seeded by
# backend/scripts/seed_reference_data.py.
_MATCHERS: list[tuple[str, callable, MatchConfidence]] = [
    (
        "PM-KISAN (Pradhan Mantri Kisan Samman Nidhi)",
        lambda user: user.total_area_hectares > 0,
        # Fully verified scheme data (see docs/govt-schemes-sourcing.md), but
        # exclusions (income tax, govt employment, pension, licensed
        # professional) can't be checked against User — this farmer's actual
        # eligibility isn't confirmed, only the landholding proxy.
        MatchConfidence.provisional,
    ),
    (
        "Krishi Bhagya Yojana",
        lambda user: (
            user.irrigation_type == "rainfed"
            and user.total_area_hectares >= _ONE_ACRE_HECTARES
        ),
        # SC/ST tier can't be checked; benefit_description's subsidy-%
        # itself is already an unverified range (see
        # docs/govt-schemes-sourcing.md) — doubly provisional.
        MatchConfidence.provisional,
    ),
]


def match_schemes(user: User, db: Session, sync_version: int) -> list[SchemeMatch]:
    """`sync_version` is obtained by the caller (one `bump_sync_counter` per
    batch run — see api/v1/internal.py), matching the push endpoint's
    granularity (Slice 3), not one bump per user/row."""
    new_matches: list[SchemeMatch] = []

    for scheme_name, predicate, confidence in _MATCHERS:
        scheme = db.scalar(select(GovtScheme).where(GovtScheme.scheme_name == scheme_name))
        if scheme is None or not scheme.active:
            continue

        if not predicate(user):
            continue

        # Idempotency: matching is a presence check, not a repeated event.
        existing = db.scalar(
            select(SchemeMatch.id).where(
                SchemeMatch.user_id == user.id,
                SchemeMatch.scheme_id == scheme.id,
                SchemeMatch.deleted_at.is_(None),
            )
        )
        if existing:
            continue

        new_matches.append(
            SchemeMatch(
                id=str(uuid.uuid4()),
                user_id=user.id,
                scheme_id=scheme.id,
                matched_at=utcnow(),
                status=SchemeMatchStatus.matched,
                match_confidence=confidence,
                sync_version=sync_version,
                created_sync_version=sync_version,
            )
        )

    for match in new_matches:
        db.add(match)

    return new_matches
