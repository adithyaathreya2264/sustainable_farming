"""Request/response shapes for the WatermelonDB sync endpoints (Slice 3).

`TableChanges`/`PushChangesBody` are kept as raw dicts rather than strict
per-field models — the payload shape is generic across 5 different tables and
each table's own SQLAlchemy model is the real source of truth for its fields.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, RootModel


class TableChanges(BaseModel):
    created: list[dict[str, Any]] = []
    updated: list[dict[str, Any]] = []
    deleted: list[str] = []


class PullResponse(BaseModel):
    changes: dict[str, TableChanges]
    timestamp: int


class PushChangesBody(RootModel[dict[str, TableChanges]]):
    """`{ "fields": {created, updated, deleted}, "plantings": {...}, ... }`"""
