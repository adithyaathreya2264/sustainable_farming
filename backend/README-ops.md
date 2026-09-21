# Backend operations

The backend is Node.js (Express + mysql2). All commands run from `backend/`
after a one-time `npm install`. Configuration comes from `backend/.env`
(see `.env.example`).

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
