# Backend operations

## Running the API

From the repo root, venv active:

```
PYTHONPATH=. backend/venv/Scripts/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

## Batch jobs (recommendations + scheme matching)

The rule engine and the scheme matcher run as **batch jobs**, not on every
request. Until a job runs, a farmer sees no *new* recommendation or scheme
match. Run them with:

```
PYTHONPATH=. backend/venv/Scripts/python -m backend.scripts.run_batch recommendations
PYTHONPATH=. backend/venv/Scripts/python -m backend.scripts.run_batch scheme-matching
PYTHONPATH=. backend/venv/Scripts/python -m backend.scripts.run_batch all
```

Both are **idempotent** — safe to run as often as you like; they only create
rows that don't already exist.

### Demo / dev: self-running loop

```
PYTHONPATH=. backend/venv/Scripts/python -m backend.scripts.run_batch all --loop --interval 900
```

Runs every 15 minutes until Ctrl-C. Start it in a second terminal alongside
`uvicorn` and recommendations/scheme matches just appear. A bad run is logged
and the loop continues.

### Production: OS scheduler

Prefer the one-shot form on a scheduler over a long-lived `--loop` process.

**Windows Task Scheduler** — one task, trigger "every 30 minutes":

```
Program:   e:\major-project\sustainable_farming\backend\venv\Scripts\python.exe
Arguments: -m backend.scripts.run_batch all
Start in:  e:\major-project\sustainable_farming
```
(set the `PYTHONPATH=.` env via the task's environment, or a one-line `.bat`
wrapper that `cd`s to the repo root and `set PYTHONPATH=.`)

**cron** (Linux):

```
*/30 * * * * cd /srv/sustainable_farming && PYTHONPATH=. venv/bin/python -m backend.scripts.run_batch all >> /var/log/sf-batch.log 2>&1
```

The `/api/v1/internal/run-recommendations` and `/run-scheme-matching` HTTP
routes still exist (behind the `X-Internal-Key` header) for an external HTTP
cron or manual triggering — they call the same service functions.

### Counter-lock note

`run_batch recommendations` fetches every planting's weather snapshot from
Open-Meteo *before* it opens the sync-counter write transaction, so a farmer's
concurrent sync push never blocks on weather-API latency. Keep that ordering if
you edit `backend/services/recommendation_run.py`.

## Migrations

```
PYTHONPATH=. backend/venv/Scripts/python -m alembic -c backend/alembic.ini upgrade head
```

## Seeding reference data (idempotent)

```
PYTHONPATH=. backend/venv/Scripts/python -m backend.scripts.seed_reference_data
```

## Smoke test (end-to-end, against the dev DB)

```
PYTHONPATH=. backend/venv/Scripts/python backend/scripts/smoke_e2e.py
```
