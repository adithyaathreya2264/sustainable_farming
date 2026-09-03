# State of the System — Pre-Phase 4 Checkpoint

_Date: 2026-09-03. Written before starting **Phase 4 (prescriptive engine + scheme matcher)**._
_This is a factual baseline, not a design doc. No code or architecture changed to produce it._

---

## 1. What is real / implemented and verified

### Backend (`backend/`, FastAPI + SQLAlchemy 2.0 + MySQL 8.0)

| Area | Status | Verification |
|---|---|---|
| **Schema / models** (Slice 1) | 11 models, all 8 core tables + reference tables created via Alembic | DDL reviewed; `alembic upgrade head` applied against real MySQL |
| **Alembic migrations** | Set up before any business logic; baseline `d540032edfd8` contains full DDL; later migrations `7cf4ac7f1803`, `89c8abd11684` | Autogenerate diffs reviewed each time |
| **Phone + OTP auth + JWT** (Slice 2) | `POST /api/v1/auth/request-otp`, `/verify-otp`; `User` auto-created on first verify | End-to-end against real MySQL: rate-limit 429, wrong-OTP 401, correct-OTP 200 + valid JWT |
| **Sync endpoint** (Slice 3) | `GET/POST /api/v1/sync`, WatermelonDB-shaped protocol; `sync_version` counter cursor; `created_sync_version` split; push conflict detection (409 on stale); owner resolution from JWT with `SELECT ... FOR UPDATE` | End-to-end against real MySQL with 2 users / real JWTs: created/updated split, 409 stale push (no partial write), 403 cross-user, 422 missing parent, delete→tombstone, 409 on duplicate client id |
| **Soil-type lookup** (Task 3.1) | `GET /api/v1/soil-lookup`; always 200 with `confidence: taluk\|district\|none`; logic isolated in `services/soil_lookup.py` | Tested: all 3 fallback tiers + 401 without auth |
| **Reference-data catalog** (Tasks 3.4/3.5) | `crops` + `crop_varieties` + `agri_catalog` + `govt_schemes` models & endpoints (`api/v1/catalog.py`); seeded idempotently by `scripts/seed_reference_data.py`; `Planting.crop_id`/`variety_id` and `Intervention.product_id` now real FKs | Seed script re-run-safe; FKs enforced |
| Routers wired in `main.py` | `auth`, `sync`, `soil`, `catalog`, `/health` | — |

### Frontend (`frontend/sustainable-farming/`, Expo SDK 54, Expo Go workflow)

| Area | Status |
|---|---|
| **Auth flow** | `services/auth.ts` calls the real backend OTP endpoints; login/otp screens unchanged |
| **Sync engine** | `services/sync-manager.ts` — hand-rolled fetch client speaking the real backend wire protocol (pull-then-push, retry-once, concurrency guard). Scope: **`fields` / `plantings` / `interventions` only** |
| **Soil lookup** | `services/soilLookup.ts` wired into `add-field.tsx` — best-effort pre-fill, never blocks save |
| **Reference catalog** | `services/catalog.ts` fetches server catalog; `appStore` caches `crops` / `agriInputs`; screens show an empty state until first fetch |
| **Unit conversions** | `utils/unitConversion.ts` — standardized land units exact; Guntha verified for Karnataka |
| **i18n** | 10 locales, key-parity checked as standard practice |

---

## 2. Known gaps and limitations

### 2.1 The mock IDs (catalog data)
- `data/mock/crops.json` uses synthetic ids (`c1`, `c1v1`, …) and `data/mock/demoSeed.json` / mock interventions use `p1`, `p5`, `p7` product ids.
- The **backend seeds catalog rows with generated UUIDs** (`uuid` in `seed_reference_data.py`). The mock ids **do not and will never match** real backend catalog ids.
- Any planting/intervention created from demo seed data references catalog ids that are meaningless server-side. `appStore` already documents that screens must show "connect once to download crop data" rather than fall back to fake ids — but `demoSeed.json` still contains them, and `loadDemoData()` injects them wholesale.
- **Phase 4 impact:** the prescriptive engine keys rules off `crop_id`. Demo/mock plantings cannot be matched. Real-catalog `crop_id`s must be flowing before rule output means anything.

### 2.2 The `user.id` red herring
- Frontend `user.id` is seeded to `"u1"` from `data/mock/user.json` and **is never refreshed from the backend**. `verifyOtp()` stores only the JWT; it does not fetch a profile, and there is no endpoint that returns the user's real id.
- `services/fields.ts` stamps `field.userId = getState().user.id` (`"u1"`), and `lib/syncMapping.ts` forwards it as `user_id`.
- **The backend ignores it entirely.** In `api/v1/sync.py`, `fields` and `scheme_matches` have `set_owner` — the server overwrites `user_id` from `current_user.id` (the JWT subject) and skips owner-validation on create. So the wrong client value is harmless *today* for `fields`.
- It is a red herring because it **looks** like identity plumbing but carries no weight. Do not build Phase 4 logic that trusts `user.id` client-side, compares it to backend ids, or assumes `field.userId` is a real foreign key value. The only real user identity is the JWT.

### 2.3 The WatermelonDB gap
- Despite "Task 2.4" instructions and several `backend/plan/` docs referring to "WatermelonDB state", **the frontend does not use `@nozbe/watermelondb`.** It uses a hand-rolled fetch client + a reactive in-memory `appStore` persisted to `AsyncStorage`.
- Reason: WatermelonDB needs native SQLite bindings that Expo Go cannot run; the user explicitly chose to keep the Expo Go workflow (decision 2026-09-13).
- The wire protocol matches the backend, but the frontend has **no local relational DB, no observable queries, no real migration system, and no per-record change tracking** beyond a boolean `isSynced` flag.
- Sync scope is partial: `recommendations` and `scheme_matches` are **not pulled or applied** by `sync-manager.ts` (documented data-model mismatch with the mock shapes). **Phase 4 produces exactly those two record types** — delivering their output to the app is unbuilt work, not a wiring detail.

### 2.4 Recommendation model mismatch
- Backend `Recommendation` = `rule_code` / `trigger_snapshot` / `severity` / `status`.
- Frontend mock `Recommendation` = `title` / `description` / `confidencePct` / `createdAt`.
- No adapter exists. `services/alerts.ts` and `services/schemes.ts` are still pure mock readers off `appStore` / `data/mock/*.json`.

---

## 3. Migration risks

### 3.1 appStore migration risk — **RESOLVED 2026-09-03**
Fixed before Phase 4. `store/appStore.ts` now:
- Persists a **versioned envelope** `{ schemaVersion, data }` under `agrosense.appState.v1`, writing **only `PERSISTED_KEYS`** (whitelist) — not the whole state blob. `hydrate()` runs a `migrations[n]` chain from the stored version up to `SCHEMA_VERSION` (currently `2`); a blob from a **newer** version, or corrupt JSON, starts clean instead of merging garbage. `migratePersisted()` is pure and unit-tested.
- `migrations[2]` intentionally **discards any v1 blob** (no v1 install has real synced data; a v1 blob can't tell demo rows from real). Cost: existing Expo Go sessions need **one re-login** after this update. From v2 on, migrations preserve data.
- Tracks **`dataOrigin: "empty" | "demo" | "live"`**. `loadDemoData()` → `"demo"`; `markLiveSession()` (called on successful OTP verify) wipes demo rows and flips to `"live"`. `sync-manager.synchronize()` **no-ops while `"demo"`** — mock rows can never be pushed.
- `pruneOrphanedCatalogRefs()` + `catalogDatasetTag` (`CATALOG_DATASET_TAG = "seed-uuid-v1"` in `services/catalog.ts`) reconcile unsynced local rows when backend catalog IDs change — runtime hook now, callable from a future `migrations[n]`.
- Tests: `store/__tests__/appStore.migration.test.ts`, `services/__tests__/syncGuard.test.ts` (11 cases, `npm test` via `jest-expo`).

**Phase 4 note:** adding `recommendations` / `scheme_matches` to persisted state = add them to `PERSISTED_KEYS` behind a new `migrations[3]`.

### 3.2 Other migration risks
- **Catalog id cutover:** switching mock catalog → real catalog invalidates every persisted `crop_id` / `variety_id` / `product_id`. Needs a deliberate reset or remap, not a silent swap.
- **`user.id` becoming real:** if a profile fetch is added, existing persisted `field.userId = "u1"` values become visibly wrong (still ignored by backend, but confusing in the UI and in any future client-side filter).
- **Datetime convention:** all datetimes are **naive-UTC-by-convention** (MySQL `DATETIME` drops tzinfo). Phase 4 rule evaluation does date math (growth-stage windows, scouting intervals) — it must use `models/base.py:utcnow()` and never construct tz-aware datetimes, or the Slice 2 comparison crash recurs in harder-to-unwind code.
- **`sync_version` is a counter, not a timestamp.** `lastPulledAt` in `appStore` is an opaque cursor. Any Phase 4 code tempted to treat it as time is wrong.

---

## 4. Intentionally deferred (with references)

| Item | Reference | Note |
|---|---|---|
| Fast2SMS success-response shape | `core/sms.py` best guess `{"return": true}`; `[[backend-slice2]]` | Account not verified for OTP route (Fast2SMS dashboard step). Failure path is confirmed real. Deferred indefinitely by user. |
| Agronomic rule matrix verification | `docs/agronomic-rules-draft.csv` + `.md`; `[[task-2.5-agronomic-rules]]` | 10 rows, every row LOW/MEDIUM confidence except `COTTON_PBW_ETL` and `MAIZE_FAW_ETL`. **Needs Karnataka KVK / ICAR package-of-practices sign-off before any row drives real `trigger_snapshot` logic.** |
| Irrigation-rule shape | `[[task-2.5-agronomic-rules]]` | Real irrigation guidance is growth-stage-based, not a threshold+operator. Needs a stage-duration table derived from `sowing_date`. **Decide this before building the rule engine, not after.** |
| Real soil DB | `services/soil_lookup.py` `# TODO(real-soil-db)` | Placeholder in-memory data; swap that one file when a real soil-survey table exists. |
| Taluk-level soil precision | `[[task-3.1-soil-lookup]]` | Backend supports `taluk`; onboarding never collects it, so only state+district are sent. |
| Non-standardized land units | `docs/unit-conversions.md`; `[[task-2.6-unit-conversions]]` | Bigha/Katha/Biswa/Kanal/Marla shipped provisional, sourced from real-estate aggregators, **not** state revenue records. None is Karnataka. |
| Krishi Bhagya Yojana exact subsidy % | `docs/govt-schemes-sourcing.md`; `[[task-3.4-3.5-reference-data]]` | Stored as an 80–90% range with "confirm at application_url" caveat, not a bare number. |
| Manipuri (`mni`) translations | `[[task-3.1-soil-lookup]]` | No longer missing, but still AI-generated and unverified; needs a native speaker / MT-verification pass. |
| Recommendations / scheme_matches sync | `services/sync-manager.ts` docstring | Not pulled or applied by the frontend sync client. Data-model mismatch (§2.4). Separate follow-up. |
| `recommendations` / `scheme_matches` push from client | `api/v1/sync.py` `TABLES` | Backend has owner resolution for them, but the frontend never sends them. |

---

## 5. Do NOT treat as production-ready

- **The agronomic rule content** (`docs/agronomic-rules-draft.csv`) — it is an explicitly unverified draft. Phase 4 can build the *engine* against it, but no rule output should reach a farmer as advice until agronomist sign-off.
- **Government scheme eligibility logic** — `services/schemes.ts` is a hardcoded mock (`if scheme.id === "s3"`). The "you qualify for ₹X" framing is trust-critical and currently fictional.
- **Any demo-seeded data** — mock ids, mock user, mock vendors. It exists to make screens look alive, not to be synced or reasoned over.
- **The frontend local store** — in-memory + `AsyncStorage`; now versioned/migrated with a persist whitelist (§3.1), but still no conflict UI and sync failures are swallowed silently.
- **Fast2SMS delivery** — unverified account; OTPs may not actually send in production.
- **Soil suggestions** — placeholder data; correct-looking output for a location may be from a hardcoded fallback row.
- **Non-Karnataka land-unit conversions** — unverified factors.

---

## 6. Assumptions carried into Phase 4

1. The **JWT is the only real user identity**. Ignore client-supplied `user_id` / `user.id`.
2. **Real catalog `crop_id`s** (UUIDs from `seed_reference_data.py`) are the join key for rules — not mock ids.
3. All datetimes are **naive UTC**, produced only via `utcnow()`.
4. `sync_version` / `lastPulledAt` are **opaque counters**, never timestamps.
5. Phase 4 output (`Recommendation`, `SchemeMatch`) currently has **no delivery path to the app** — building that path is in-scope work, and requires resolving §2.4 (§3.1 is now resolved; persist new keys behind `migrations[3]`).
6. The rule matrix and scheme rules **must remain behind an "unverified" flag** until domain sign-off.
