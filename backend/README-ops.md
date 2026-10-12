# Backend operations

The backend is Node.js ≥ 20 (Express 5 + mysql2). All commands run from
`backend/` after a one-time `npm install`. Configuration comes from
`backend/.env` (see `.env.example`). For the system overview see the
[root README](../README.md).

## First-time setup

1. Create a MySQL 8 database `sustainable-farming` and an app user (the example
   config uses `sf_app`) with full rights on it.
2. `cp .env.example .env` and fill in `DATABASE_URL`, `JWT_SECRET` and
   `INTERNAL_API_KEY` (generate secrets with
   `node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"`).
3. `npm install`, then `npm run migrate`, then `npm run seed`.
4. `npm run dev` (API only) or `npm run dev:all` (API + ML sidecar).

Login is a permanent mock: `verify-otp` accepts `MOCK_OTP` (default `123456`)
for any phone number and still issues a real JWT.

### Environment variables

| Variable | Required | Default |
|---|---|---|
| `DATABASE_URL` | yes | — |
| `JWT_SECRET` | yes | — |
| `INTERNAL_API_KEY` | yes (guards `/api/v1/internal/*` via `X-Internal-Key`) | — |
| `MOCK_OTP` | no | `123456` |
| `CORS_ALLOW_ORIGINS` | no | `*` (tighten outside dev) |
| `JWT_ALGORITHM` / `JWT_EXPIRY_MINUTES` | no | `HS256` / `10080` |
| `PORT` | no | `8000` |
| `MYSQL_ROOT_PASSWORD` | no — only to provision the DB, then remove | — |
| `ML_SIDECAR_URL`, `ML_SIDECAR_PORT`, `ML_PYTHON_BIN`, `ML_PRELOAD` | no | see "ML sidecar" below |

### npm scripts

`start`, `dev`, `ml`, `dev:all`, `migrate`, `seed`, `batch`, `smoke`, `test`
— each is described in the section for its job below.

## Running the API

```
npm start          # listens on 0.0.0.0:8000
npm run dev        # same, restarting on file changes
```

## Batch jobs (recommendations + scheme matching)

The rule engine and the scheme matcher run as **batch jobs**, not on every
request. Until a job runs, a farmer sees no *new* recommendation or scheme
match. Run them with:

```
npm run batch -- recommendations
npm run batch -- scheme-matching
npm run batch -- all
```

Both are **idempotent** — safe to run as often as you like; they only create
rows that don't already exist.

### Demo / dev: self-running loop

```
npm run batch -- all --loop --interval 900
```

Runs every 15 minutes until Ctrl-C. Start it in a second terminal alongside
`npm start` and recommendations/scheme matches just appear. A bad run is
logged and the loop continues.

### Production: OS scheduler

Prefer the one-shot form on a scheduler over a long-lived `--loop` process.

**Windows Task Scheduler** — one task, trigger "every 30 minutes":

```
Program:   C:\Program Files\nodejs\node.exe
Arguments: scripts/run-batch.js all
Start in:  e:\major-project\sustainable_farming\backend
```

**cron** (Linux):

```
*/30 * * * * cd /srv/sustainable_farming/backend && node scripts/run-batch.js all >> /var/log/sf-batch.log 2>&1
```

The `/api/v1/internal/run-recommendations` and `/run-scheme-matching` HTTP
routes still exist (behind the `X-Internal-Key` header) for an external HTTP
cron or manual triggering — they call the same service functions.

### Ordering note

`run-recommendations` fetches every planting's weather snapshot from
Open-Meteo *before* it opens its write transaction, so the transaction only
spans fast DB work, never weather-API latency. Keep that ordering if you edit
`backend/src/services/recommendationRun.js`.

## Migrations

```
npm run migrate
```

Migrations are plain SQL files in `backend/migrations/`, tracked in the
`schema_migrations` table.

- **Empty database:** every migration runs, creating the full schema.
- **Existing database built by the old Alembic tooling** (at revision
  `e1f2a3b4c5d6`): the baseline (`0001_baseline`) is *stamped* as applied
  without running any DDL, so nothing is recreated or altered. Later
  migrations then apply normally. The old `alembic_version` table is left
  alone.
- Any other state (tables present, revision unknown or older) is refused with
  a clear message rather than guessed at.

Schema changes from here on are new numbered `.sql` files in `migrations/`.
Current files: `0001_baseline`, `0002_soil_tests`, `0003_ml_serving`,
`0004_soil_test_card`, `0005_soil_test_order`.

## ML sidecar (model serving)

The shipped models run in a separate Python process, `ml/serving/` (FastAPI on
`127.0.0.1:8001`), which this API proxies to. It uses the repo-root `.venv`
(see `ml/README.md`).

```
npm run dev:all    # API (node --watch) + sidecar, prefixed output; Ctrl+C stops both
npm run ml         # sidecar alone; ML_PRELOAD=1 npm run ml warms every model first
```

Settings: `ML_SIDECAR_URL` (default `http://127.0.0.1:8001`), `ML_PYTHON_BIN`
(default `../.venv/Scripts/python.exe` or `.venv/bin/python`), `ML_SIDECAR_PORT`.

If the sidecar is down, every ML route returns **503 `{reason: "ml_unavailable"}`**
and everything else keeps working. The first call to a photo model loads its
weights (a few seconds); later calls are about a second.

**Photos.** Uploads for photo checks are stored under `backend/uploads/ml/YYYY/MM/`
(gitignored), one `ml_inferences` row each. Farmers can list and delete their
own from the app; deleting removes the file. `users.photo_training_consent`
(off by default) records whether a farmer allows their photos to be used for
retraining. Nothing reads it yet; any future training export must filter on it.

## Seeding reference data (idempotent)

```
npm run seed
```

Insert-only, keyed on natural keys (crop name, rule code, scheme name,
state+district, ...): re-running never modifies existing rows. Source data is
`scripts/reference-data.json` and `scripts/seed_data/locations.json`.
(`ml/prep` also reads `locations.json` from that path — keep it there.)

## Tests

```
npm test           # pure-logic unit tests (no DB / network)
npm run smoke      # end-to-end against the dev MySQL (starts the app in-process)
SMOKE_BASE_URL=http://localhost:8000 npm run smoke   # against a running server
```
