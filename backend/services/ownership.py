"""Ownership resolution shared between api/v1/sync.py and api/v1/alerts.py.

Resolves whose `user_id` a row ultimately belongs to, walking the
field_id/planting_id chain where there's no direct `user_id` column.
Extracted out of sync.py (Slice 3) when alerts.py (Phase 4 Part 2) needed the
exact same logic — keep this the one place it lives.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.field import Field
from backend.models.planting import Planting


def field_owner(db: Session, field_id: str) -> str | None:
    return db.scalar(select(Field.user_id).where(Field.id == field_id))


def planting_owner(db: Session, planting_id: str) -> str | None:
    field_id = db.scalar(select(Planting.field_id).where(Planting.id == planting_id))
    if field_id is None:
        return None
    return field_owner(db, field_id)
