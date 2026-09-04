"""WatermelonDB sync endpoints (Slice 3): GET /api/v1/sync (pull),
POST /api/v1/sync (push). See backend/plan/slice3.txt and the Slice 3 plan
notes in models/base.py (SyncMixin) for the design this implements.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.deps import get_current_user
from backend.core.sync_counter import bump_sync_counter
from backend.models.base import SyncCounter, utcnow
from backend.models.field import Field
from backend.models.intervention import Intervention
from backend.models.planting import Planting
from backend.models.recommendation import Recommendation
from backend.models.scheme import SchemeMatch
from backend.models.scouting_observation import ScoutingObservation
from backend.models.user import User
from backend.schemas.sync import PullResponse, PushChangesBody, TableChanges
from backend.services.ownership import field_owner as _field_owner
from backend.services.ownership import planting_owner as _planting_owner

router = APIRouter(prefix="/api/v1/sync", tags=["sync"])

# --- Coercion helpers -------------------------------------------------------
# Payload values may arrive as ISO strings or epoch-millisecond numbers
# (WatermelonDB typically stores date/datetime columns as ms-since-epoch) —
# the exact shape depends on the frontend's eventual WatermelonDB schema,
# which doesn't exist yet, so both are accepted defensively.


def _parse_date(value: Any) -> date:
    if isinstance(value, (int, float)):
        return datetime.utcfromtimestamp(value / 1000).date()
    return date.fromisoformat(value)


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.utcfromtimestamp(value / 1000)
    # Naive-UTC convention (see models/base.py) — strip any offset if present.
    dt = datetime.fromisoformat(value)
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


# --- Per-table sync config ---------------------------------------------------
# `owner_of_row`: given an existing row, whose user_id does it ultimately
# belong to (resolving through field_id/planting_id where there's no direct
# user_id column).
# `owner_of_new`: given a create payload (not yet inserted), resolve the same
# thing, to check the parent the client is trying to attach to actually
# belongs to them.
# `apply_writable`: copy client-writable fields from payload onto a model
# instance (never id/user_id/sync_version/created_sync_version/timestamps —
# those are always server-assigned).


def _apply_field(row: Field, payload: dict[str, Any]) -> None:
    row.name = payload["name"]
    row.area_size_hectares = payload["area_size_hectares"]
    row.lat = payload["lat"]
    row.long = payload["long"]
    row.boundary = payload["boundary"]
    row.soil_type = payload.get("soil_type")


def _apply_planting(row: Planting, payload: dict[str, Any]) -> None:
    row.field_id = payload["field_id"]
    row.crop_id = payload["crop_id"]
    row.variety_id = payload.get("variety_id")
    row.sowing_date = _parse_date(payload["sowing_date"])
    row.status = payload["status"]


def _apply_intervention(row: Intervention, payload: dict[str, Any]) -> None:
    row.planting_id = payload["planting_id"]
    row.type = payload["type"]
    row.product_id = payload.get("product_id")
    row.quantity_metric = payload.get("quantity_metric")
    row.quantity_unit = payload.get("quantity_unit")
    row.cost_in_inr = payload["cost_in_inr"]
    row.intervention_date = _parse_date(payload["intervention_date"])
    row.notes = payload.get("notes")


def _apply_scouting_observation(row: ScoutingObservation, payload: dict[str, Any]) -> None:
    row.planting_id = payload["planting_id"]
    row.metric_key = payload["metric_key"]
    row.metric_value = payload["metric_value"]
    row.observed_at = _parse_date(payload["observed_at"])
    row.notes = payload.get("notes")


def _push_not_allowed(row: Any, payload: dict[str, Any]) -> None:
    # recommendations / scheme_matches are server-generated (rule engine,
    # scheme matcher) and delivered to the app via GET/PATCH /api/v1/alerts —
    # never pushed. They stay in TABLES for the *pull* side; the push side is
    # gated off by `push_allowed=False`, so this is unreachable.
    raise AssertionError("server-generated record type; never pushed via /sync")


class _TableConfig:
    def __init__(
        self,
        model: type,
        apply_writable: Callable[[Any, dict[str, Any]], None],
        owner_of_row: Callable[[Session, Any], str | None],
        owner_of_new: Callable[[Session, dict[str, Any]], str | None],
        set_owner: Callable[[Any, str], None] | None = None,
        query_scope: Callable[[Any, str], Any] | None = None,
        push_allowed: bool = True,
    ):
        self.model = model
        self.apply_writable = apply_writable
        self.owner_of_row = owner_of_row
        self.owner_of_new = owner_of_new
        self.set_owner = set_owner
        self.query_scope = query_scope
        # False for server-generated record types (recommendations,
        # scheme_matches): they're delivered via GET/PATCH /api/v1/alerts, the
        # push side ignores them. Pull still serves them.
        self.push_allowed = push_allowed


# Pull needs a base query scoped to the user; push needs owner resolution.
# Order below is FK-safe for push: parents before children.
TABLES: dict[str, _TableConfig] = {
    "fields": _TableConfig(
        model=Field,
        apply_writable=_apply_field,
        owner_of_row=lambda db, row: row.user_id,
        owner_of_new=lambda db, payload: None,  # no parent to check; server sets owner
        set_owner=lambda row, uid: setattr(row, "user_id", uid),
        query_scope=lambda q, uid: q.where(Field.user_id == uid),
    ),
    "plantings": _TableConfig(
        model=Planting,
        apply_writable=_apply_planting,
        owner_of_row=lambda db, row: _field_owner(db, row.field_id),
        owner_of_new=lambda db, payload: _field_owner(db, payload["field_id"]),
        query_scope=lambda q, uid: q.join(Field, Planting.field_id == Field.id).where(
            Field.user_id == uid
        ),
    ),
    "interventions": _TableConfig(
        model=Intervention,
        apply_writable=_apply_intervention,
        owner_of_row=lambda db, row: _planting_owner(db, row.planting_id),
        owner_of_new=lambda db, payload: _planting_owner(db, payload["planting_id"]),
        query_scope=lambda q, uid: q.join(
            Planting, Intervention.planting_id == Planting.id
        )
        .join(Field, Planting.field_id == Field.id)
        .where(Field.user_id == uid),
    ),
    "scouting_observations": _TableConfig(
        model=ScoutingObservation,
        apply_writable=_apply_scouting_observation,
        owner_of_row=lambda db, row: _planting_owner(db, row.planting_id),
        owner_of_new=lambda db, payload: _planting_owner(db, payload["planting_id"]),
        query_scope=lambda q, uid: q.join(
            Planting, ScoutingObservation.planting_id == Planting.id
        )
        .join(Field, Planting.field_id == Field.id)
        .where(Field.user_id == uid),
    ),
    "recommendations": _TableConfig(
        model=Recommendation,
        apply_writable=_push_not_allowed,
        owner_of_row=lambda db, row: _planting_owner(db, row.planting_id),
        owner_of_new=lambda db, payload: _planting_owner(db, payload["planting_id"]),
        query_scope=lambda q, uid: q.join(
            Planting, Recommendation.planting_id == Planting.id
        )
        .join(Field, Planting.field_id == Field.id)
        .where(Field.user_id == uid),
        push_allowed=False,
    ),
    "scheme_matches": _TableConfig(
        model=SchemeMatch,
        apply_writable=_push_not_allowed,
        owner_of_row=lambda db, row: row.user_id,
        owner_of_new=lambda db, payload: None,
        set_owner=lambda row, uid: setattr(row, "user_id", uid),
        query_scope=lambda q, uid: q.where(SchemeMatch.user_id == uid),
        push_allowed=False,
    ),
}


# --- Pull --------------------------------------------------------------------


@router.get("", response_model=PullResponse)
def pull_changes(
    last_pulled_at: int | None = Query(None),
    # Accepted per WatermelonDB's pull contract but unused until the frontend
    # WatermelonDB schema (and its migrations) exist — see slice3.txt Step 1.
    schema_version: int = Query(...),
    migration: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PullResponse:
    cursor = last_pulled_at or 0
    changes: dict[str, TableChanges] = {}

    for table_name, cfg in TABLES.items():
        base_query = select(cfg.model).where(cfg.model.sync_version > cursor)
        query = cfg.query_scope(base_query, current_user.id)
        rows = db.scalars(query).all()

        table_changes = TableChanges()
        for row in rows:
            if row.deleted_at is not None:
                table_changes.deleted.append(row.id)
            elif row.created_sync_version > cursor:
                table_changes.created.append(_row_to_dict(row))
            else:
                table_changes.updated.append(_row_to_dict(row))
        changes[table_name] = table_changes

    timestamp = db.scalar(select(SyncCounter.current_value).where(SyncCounter.id == 1))
    return PullResponse(changes=changes, timestamp=timestamp or 0)


def _row_to_dict(row: Any) -> dict[str, Any]:
    """SQLAlchemy model -> plain dict for the pull response. Excludes nothing
    special — WatermelonDB's raw record shape includes everything, and the
    client only reads the columns its own schema knows about."""
    return {
        c.key: getattr(row, c.key)
        for c in row.__table__.columns
        if c.key != "deleted_at"
    }


# --- Push --------------------------------------------------------------------


@router.post("", status_code=status.HTTP_200_OK)
def push_changes(
    body: PushChangesBody,
    last_pulled_at: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    changes = body.root
    # Locked rows from pass 1, reused in pass 2 (same session identity map —
    # this dict just avoids a second lookup, the lock itself is held by the
    # session/transaction either way).
    locked: dict[tuple[str, str], Any] = {}

    # A child and its parent can be created in the same push (a farmer adds a
    # field and a planting offline, then syncs) — the parent isn't in the DB
    # yet during pass-1 validation, so track created ids per table as we walk
    # the FK-safe order and treat a parent that's being created in this same
    # push as owned by the caller (fields get `set_owner=current_user`;
    # plantings created here hang off a field validated in this same push).
    _PARENT_FK: dict[str, tuple[str, str]] = {
        "plantings": ("fields", "field_id"),
        "interventions": ("plantings", "planting_id"),
        "scouting_observations": ("plantings", "planting_id"),
    }
    created_this_push: dict[str, set[str]] = {t: set() for t in TABLES}

    # Pass 1: validate everything before writing anything (whole push is one
    # transaction — either all writes succeed or none do).
    for table_name in TABLES:  # fixed, FK-safe order — ignore payload's order
        table_changes = changes.get(table_name)
        if table_changes is None:
            continue
        cfg = TABLES[table_name]
        if not cfg.push_allowed:
            continue  # server-generated; delivered via /api/v1/alerts, not synced

        for payload in table_changes.created:
            new_id = payload.get("id")
            if new_id and db.get(cfg.model, new_id) is not None:
                # A duplicate id would otherwise hit MySQL's PK constraint at
                # commit time and surface as a raw 500 — reject cleanly here
                # instead (also makes a client's accidental create-retry safe).
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"{table_name} {new_id} already exists.",
                )
            if new_id:
                created_this_push[table_name].add(new_id)
            if cfg.set_owner is not None:
                continue  # server sets owner directly — nothing to check
            parent = _PARENT_FK.get(table_name)
            if parent is not None:
                parent_table, fk = parent
                if payload.get(fk) in created_this_push[parent_table]:
                    continue  # parent is being created in this same push, by us
            owner = cfg.owner_of_new(db, payload)
            if owner is None:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    f"{table_name}: referenced parent row not found.",
                )
            if owner != current_user.id:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your data.")

        ids_to_lock = [p["id"] for p in table_changes.updated] + table_changes.deleted
        for row_id in ids_to_lock:
            row = db.execute(
                select(cfg.model).where(cfg.model.id == row_id).with_for_update()
            ).scalar_one_or_none()
            if row is None:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    f"{table_name} {row_id} not found.",
                )
            if cfg.owner_of_row(db, row) != current_user.id:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your data.")
            if row.sync_version > last_pulled_at:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"{table_name} {row_id} changed remotely — pull and retry.",
                )
            locked[(table_name, row_id)] = row

    # Pass 2: everything validated clean — assign one version for this whole
    # push and apply every write.
    new_version = bump_sync_counter(db)

    for table_name, cfg in TABLES.items():
        table_changes = changes.get(table_name)
        if table_changes is None:
            continue
        if not cfg.push_allowed:
            continue

        for payload in table_changes.created:
            row = cfg.model(id=payload.get("id") or str(uuid.uuid4()))
            cfg.apply_writable(row, payload)
            if cfg.set_owner is not None:
                cfg.set_owner(row, current_user.id)
            row.sync_version = new_version
            row.created_sync_version = new_version
            db.add(row)

        for payload in table_changes.updated:
            row = locked[(table_name, payload["id"])]
            cfg.apply_writable(row, payload)
            row.sync_version = new_version

        for row_id in table_changes.deleted:
            row = locked[(table_name, row_id)]
            row.deleted_at = utcnow()
            row.sync_version = new_version

    db.commit()
    return {"status": "ok"}
