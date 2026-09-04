"""Declarative base, timestamp/sync mixins, and the sync counter table.

Design notes carried over from ``backend/plan/slice1.txt``:

* ``created_at`` / ``updated_at`` are **display-only**. They are never used for
  sync conflict resolution.
* ``sync_version`` (see :class:`SyncMixin`) has **no default of any kind** — not
  an ORM ``default``, not ``server_default``, not MySQL ``AUTO_INCREMENT``, and
  emphatically not SQLAlchemy's ``Sequence`` construct.

  Why not ``Sequence``: ``Sequence`` compiles to native ``CREATE SEQUENCE``,
  which plain MySQL (including 8.x) does not have. On MySQL it is silently a
  no-op — the model looks correct and passes a casual review, but no counter is
  ever created and the column has no usable default at insert time.

  Instead, ``sync_version`` is assigned explicitly in Python inside the sync
  endpoint's transaction (Slice 3) by incrementing :class:`SyncCounter` under a
  ``SELECT ... FOR UPDATE`` row lock. Do not add a default here.

* All datetime columns are **naive, UTC-by-convention** — not
  ``DateTime(timezone=True)``. MySQL's ``DATETIME`` has no timezone concept at
  all, and PyMySQL silently drops tzinfo in both directions: a tz-aware value
  written to the DB comes back naive on the next read. Keeping the Python side
  aware just sets up a naive-vs-aware ``TypeError`` the first time you compare
  a freshly-created value against one that round-tripped through the DB (hit
  this for real in Slice 2's OTP-expiry check). Everyone in this codebase
  agrees every datetime, column or Python object, is UTC; ``utcnow()`` is the
  one place that's true and the only thing that should ever be called to get
  "now".
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    """Current UTC time, naive (see module docstring on why not tz-aware)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    """Display-only audit timestamps. Not used for conflict resolution."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )


class SyncMixin:
    """Columns for entities that WatermelonDB syncs as farmer-editable data.

    ``sync_version`` is intentionally left with NO default — it is assigned
    explicitly in the sync transaction (see module docstring). ``deleted_at``
    is a soft-delete tombstone propagated to clients.

    ``created_sync_version`` is set exactly once, at creation, to the same
    counter value as ``sync_version`` at that moment — then never touched
    again. It exists purely to answer "was this row created since the
    client's last pull?" on the pull endpoint (Slice 3): comparing
    ``created_at`` against ``last_pulled_at`` doesn't work because
    ``last_pulled_at`` is a version-counter cursor, not a wall-clock
    timestamp (WatermelonDB's own docs assume the latter; we deliberately
    don't use wall-clock time as the sync cursor — see Slice 1). Also no
    default here, for the same reason as ``sync_version``: it's assigned in
    Python inside the push transaction, never by the ORM or MySQL.
    """

    sync_version: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    created_sync_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)


class SyncCounter(Base):
    """Single-row table holding the global monotonic sync version counter.

    The push endpoint (Slice 3) locks and increments the row with id == 1,
    once per push request. The row is seeded (id=1, current_value=0) by the
    Alembic migration that adds ``created_sync_version`` — see alembic/versions.
    """

    __tablename__ = "sync_counter"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    current_value: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
