"""The shared sync-version counter (Slice 3).

`sync_version`/`created_sync_version` (see `models/base.py`) are never given a
DB-level default — this is the one place they're assigned, explicitly, in
Python.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.base import SyncCounter

_COUNTER_ROW_ID = 1


def bump_sync_counter(db: Session) -> int:
    """Atomically increment the global sync counter and return the new value.

    Locks the singleton row with SELECT ... FOR UPDATE — caller must be inside
    a transaction that also applies the writes using this version, so the lock
    is held until that transaction commits (or rolls back on conflict).

    Call this ONCE per push request, not once per row — every row touched by
    a given push shares the same new sync_version.
    """
    row = db.execute(
        select(SyncCounter).where(SyncCounter.id == _COUNTER_ROW_ID).with_for_update()
    ).scalar_one()
    row.current_value += 1
    db.flush()
    return row.current_value
