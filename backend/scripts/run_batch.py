"""Batch runner for the Phase 4 recommendation / scheme-matching jobs.

This is the scheduler entry point. It calls the same service functions the
`/api/v1/internal/*` routes do, but needs no HTTP layer and no internal key.

Usage (from repo root, venv active):

    python -m backend.scripts.run_batch recommendations
    python -m backend.scripts.run_batch scheme-matching
    python -m backend.scripts.run_batch all

    # Long-running "just works in a demo" mode — re-runs every N seconds:
    python -m backend.scripts.run_batch all --loop --interval 900

Wire the one-shot form to Windows Task Scheduler / cron for production, or
run the `--loop` form as a sidecar process. See backend/README-ops.md.
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from datetime import datetime, timezone

from backend.core.database import SessionLocal
from backend.services.recommendation_run import run_recommendations
from backend.services.scheme_run import run_scheme_matching

_JOBS = {
    "recommendations": run_recommendations,
    "scheme-matching": run_scheme_matching,
}


def _run_once(target: str) -> None:
    names = list(_JOBS) if target == "all" else [target]
    for name in names:
        db = SessionLocal()
        try:
            result = _JOBS[name](db)
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
            print(f"[{stamp}] {name}: {result}", flush=True)
        finally:
            db.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run_batch", description=__doc__)
    parser.add_argument("target", choices=[*_JOBS, "all"])
    parser.add_argument(
        "--loop", action="store_true", help="re-run forever on an interval"
    )
    parser.add_argument(
        "--interval", type=int, default=900, help="seconds between runs in --loop mode"
    )
    args = parser.parse_args(argv)

    if not args.loop:
        _run_once(args.target)
        return 0

    print(f"run_batch loop: {args.target} every {args.interval}s (Ctrl-C to stop)", flush=True)
    while True:
        try:
            _run_once(args.target)
        except Exception:  # noqa: BLE001 — a loop must survive a bad run
            traceback.print_exc()
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
