# State of the System — Pre-Phase 4 Checkpoint

_Date: 2026-09-03. Written before starting **Phase 4 (prescriptive engine + scheme matcher)**._
_This is a factual baseline, not a design doc. No code or architecture changed to produce it._

> **§7 added post-checkpoint, same day:** Phase 4 Part 1 (rule engine + scheme
> matcher) is now built and verified. This file's §1–§6 describe the system
> *as it stood right before* that work — read §7 for what changed, don't
> assume §1–§6 are still the current state of those specific areas.
> **Cross-session drift is confirmed, not theoretical** (see §7.4) — verify
> against actual disk state before trusting any single section here as
> current, this doc included.
>
> **§8 added later the same day:** Phase 4 Part 2 (alert delivery) is done —
> §2.3/§2.4's delivery gap and §6 assumption 5 are **resolved**, not just
> tracked. `Recommendation`/`SchemeMatch` rows now reach a farmer via
> `GET/PATCH /api/v1/alerts`, verified end-to-end for real. See §8, don't
> read §2.3/§2.4/§6.5 below as still-open.
>
> **2026-09-21: offline-first dropped, app is online-only.** §2.3 is
> rewritten in place to describe the new state — every other section's
> mentions of `api/v1/sync.py`, `services/sync-manager.ts`, `isSynced`,
> `sync_version`/`created_sync_version`/`sync_counter`, or WatermelonDB
> describe **removed** code kept here only as history of how the system
> got here; none of it exists on disk anymore. Read §2.3 for what replaced
> it (plain CRUD endpoints + direct fetch, no local dirty-row queue).
>
> **2026-09-21, later the same day: login is permanently mock; a unique
> 4-digit `User.unique_id` was added.** Any mention below of Fast2SMS, real
> OTP delivery/expiry/hashing, rate-limiting, `OtpRequest`/`otp_requests`, or
> `dev_auth_bypass` describes **removed** code — `POST /api/v1/auth/verify-otp`
> now only ever checks a fixed `settings.mock_otp` ("123456") for any phone
> number, unconditionally, no flag involved. Separately, onboarding now opens
> with a new step ((onboarding)/step-1.tsx) where the farmer picks a 4-digit
> `unique_id`, globally unique across users (`PATCH /api/v1/users/me` returns
> 409 "This unique number already exists." on a duplicate) — the onboarding
> steps that used to be step-1..4 are now step-2..5.
>
> **2026-09-21, later still: the backend is now Node.js (Express + mysql2),
> not Python.** Behavior is unchanged — same endpoints, JSON, status codes,
> error messages, MySQL schema and port 8000 (verified by replaying a
> 103-step scenario against both backends: identical apart from the wording
> of a malformed-JSON parser error). Anywhere below that mentions FastAPI,
> SQLAlchemy, Alembic, `backend/venv`, or `*.py` backend files describes the
> **old** implementation, kept as history. Current layout: `backend/src/`
> (app, routes, services), `backend/migrations/` (SQL, run by `npm run
> migrate`), `backend/scripts/` (`seed-reference-data.js`, `run-batch.js`,
> `smoke-e2e.js`, `seed_data/locations.json`). See `backend/README-ops.md`.
> `ml/` is still Python and was not touched; it still reads
> `backend/scripts/seed_data/locations.json`.

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

### 2.3 Offline-first dropped — the app is online-only (2026-09-21)
- The app was never truly offline-first (see the historical note below) and the user explicitly dropped the feature outright: no local dirty-row queue, no background sync, no "pending sync" UI anywhere.
- `services/fields.ts` / `plantings.ts` / `interventions.ts` / `scouting.ts` now call the backend directly (`GET/POST` against `api/v1/fields.py`, `plantings.py`, `interventions.py`, `scouting_observations.py`) and update the in-memory `appStore` from the server's response. A failed create/fetch surfaces as a thrown `ApiError` — the four add-* modals catch it and show a "couldn't save, check your connection" toast rather than silently queuing the write.
- `services/sync-manager.ts`, `hooks/useSyncTriggers.ts`, the `isSynced` field on `Field`/`Planting`/`Intervention`/`ScoutingObservation`, `SyncStatusIcon`, the `lastPulledAt` pull cursor, and the backend's `api/v1/sync.py` + `SyncMixin` (`sync_version`/`created_sync_version`/`sync_counter`) are all deleted. `hooks/useRefreshTriggers.ts` replaces the sync hook, refetching catalog/alerts/weather/locations/fields/plantings/interventions/scouting-observations on app foreground and a periodic timer — no connectivity listener (`@react-native-community/netinfo` removed).
- `deleted_at` (soft-delete) survives as `SoftDeleteMixin`, still used by the new CRUD endpoints' DELETE and by `api/v1/alerts.py`'s recommendation/scheme-match filtering.
- Historical note (superseded): despite several `backend/plan/` docs referring to "WatermelonDB state", the frontend never used `@nozbe/watermelondb` — it used a hand-rolled fetch client speaking a WatermelonDB-shaped wire protocol against `api/v1/sync.py`, chosen because WatermelonDB needs native SQLite bindings Expo Go can't run (decision 2026-09-13). That whole protocol is what's removed here.

### 2.4 Recommendation model mismatch — **RESOLVED, see §8**
- Backend `Recommendation` = `rule_code` / `trigger_snapshot` / `severity` / `status` (+ `confidence`, added in §8).
- The frontend's old mock `Recommendation` (`title`/`description`/`confidencePct`/`createdAt`) **no longer exists** — replaced entirely by a unified `Alert` type fed from `GET /api/v1/alerts`. `services/schemes.ts` and `data/mock/schemes.json` are deleted, not just superseded.

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
| ~~Scouting-observation input source~~ **BUILT 2026-09-04** | `services/recommendation_run.py`; §8.3; `FRONTEND_BACKEND_GAP_ANALYSIS.md` §10.4e | Was: 4 (not 6) pest/ETL rules keyed off a farmer scouting count with no source. Now: synced `scouting_observations` table + `app/modals/log-scouting.tsx`; the 4 rules fire, still `[Unverified guidance]`. |
| `AgriCatalog.typical_dosage_per_hectare` unused by the rule engine | `schemas/catalog.py`; `services/rule_engine.py`; §7.4 | Catalog schema's comment anticipated the rule engine reading it; the engine as built only reads `AgronomicRule.threshold_value`. Intent drift between sessions, not a bug — reconcile if/when dosage cross-checks get added. |

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
5. ~~Phase 4 output (`Recommendation`, `SchemeMatch`) currently has no delivery path to the app~~ — **resolved, see §8.** `migrations[3]` (persisting the new `Alert` shape) is done, not just planned.
6. The rule matrix and scheme rules **must remain behind an "unverified" flag** until domain sign-off.

---

## 7. Phase 4 Part 1 — completed post-checkpoint

Built and verified end-to-end against real MySQL, same day as this checkpoint
(see `[[phase4-part1-rule-engine-scheme-matcher]]` for full detail). This
section is the delta on top of §1–§6, not a restatement of them.

### 7.1 What's real now
- `models/crop_growth_stage.py` (`crop_growth_stages`, 19 seeded rows, 5
  crops), `models/agronomic_rule.py` (`agronomic_rules`, 10 seeded rows —
  all `confidence=low` except `COTTON_PBW_ETL`=`medium`), migration
  `74017a935c9e`.
- `services/rule_engine.py` (`evaluate_planting`) + `services/growth_stage.py`
  — verified against a real test planting: correct stage resolved from
  `sowing_date`, `Recommendation` row created with `[Unverified guidance] `
  prefix (every seeded rule is non-`verified`), correct `sync_version`,
  idempotent on re-run (checked via an actual second call, not just review).
- `services/scheme_matcher.py` + `scheme_matches.match_confidence` (new
  column, migration `74017a935c9e`) — verified against a real test user:
  **both** PM-KISAN and Krishi Bhagya matched with `match_confidence:
  "provisional"`, confirming §6 assumption that neither scheme's eligibility
  can be fully checked against `User` today (not just Krishi Bhagya, as the
  original brief implied).
- `core/weather.py` — real Open-Meteo integration (no API key needed),
  live-tested against a Karnataka coordinate. Wired correctly, but **no rule
  in the current seed batch actually consumes weather data** (see 7.2).
- `POST /api/v1/internal/run-recommendations`, `/run-scheme-matching` —
  `INTERNAL_API_KEY` header auth (`core/deps.py:require_internal_key`,
  constant-time compare), not farmer JWT. Verified: missing/wrong key both
  403, correct key runs and is idempotent.

### 7.2 New concrete limitation: no scouting-observation input source
This is the load-bearing gap in Task 4.1, more specific than §2.3/§2.4's
"no delivery path": **6 of the 10 seeded `agronomic_rules` (the pest/ETL
ones — stem borer, PBW, shoot borer, fall armyworm) key off a farmer
field-scouting count** (`dead_hearts_percent`,
`pheromone_trap_moths_per_night_3day_avg`, `deadheart_percent`,
`percent_plants_with_whorl_damage`) — **a number only a human counts in a
field. Nothing in this app, frontend or backend, collects or stores that
observation anywhere.**

`evaluate_planting(planting, weather_snapshot, scouting_observations, db)`
takes `scouting_observations` as a real parameter, correctly typed and
threaded through condition-matching — but `api/v1/internal.py` currently
calls it with `{}` every time, because there is no source to populate it
from. **Practical effect: those 6 rules can never fire in this system as it
stands today, no matter how the trigger endpoint is run.** Only the 4
pure stage-gate irrigation rules (plus the 2 reinterpreted Ragi rules) can
ever produce a `Recommendation` right now.

This is not a bug in the engine — the mechanism is correct and tested — it's
a missing upstream feature (a scouting-observation input, presumably a
farmer-facing "log a field observation" form, itself a nontrivial addition:
UI, a table, sync support, an idempotency story). Building that is real
follow-up work, explicitly out of scope for Task 4.1 per the agreed
scope boundary (§7.3), not an oversight to silently work around.

Weather is real and tested but similarly unused by current rules — it's
wired for whenever a weather-gated rule is added, not dead code, but also
not doing anything for a farmer today.

### 7.3 Scope boundary held
Confirmed with the user before building: both tasks stop at "data exists
correctly in the DB, gated by confidence markers." No changes to
`api/v1/sync.py`'s `TABLES` registry, no frontend delivery — §2.3/§2.4's
gaps are **unchanged and now more consequential**, since real
`Recommendation`/`SchemeMatch` rows can actually exist in the DB post-Phase-4
(previously theoretical, now literal — every internal-endpoint run that
matches anything creates real rows a farmer still can't see).

**Superseded by §8, later the same day:** the delivery gap this paragraph
describes is now closed — via a fetch/PATCH endpoint, deliberately not the
`api/v1/sync.py` `TABLES` registry (see §2.3's updated note).

### 7.4 Cross-session drift is confirmed, not theoretical
Two independent, concrete instances now, not a hypothetical risk:
1. This very checkpoint doc, plus real frontend sync/persistence
   infrastructure (`store/appStore.ts` migrations, `services/sync-manager.ts`,
   `api/v1/catalog.py`, a `Crop.varieties` relationship) appeared on disk
   between sessions, built by someone/something else, with no advance
   notice in this conversation.
2. A reconciliation pass against that work (prompted by the user, this
   session) found it **imports cleanly and is mostly intent-consistent**
   with Slice 1/3.4 — but surfaced one real intent drift:
   `schemas/catalog.py`'s `AgriCatalogOut` comment claims
   `typical_dosage_per_hectare` is "shaped now so the rule engine can start
   reading it" — but `services/rule_engine.py` (built this session) never
   reads `AgriCatalog` at all, only `AgronomicRule.threshold_value`. Not a
   bug (nothing breaks), just an expectation set by one session that the
   other didn't fulfill, because neither knew about the other's specifics in
   advance.

**Practical implication for whoever/whatever works on this next:** treat
every section of this doc — including this one — as "true when written,"
not "true now." Re-verify against actual disk state (`git status`, a fresh
read of the specific file in question) before building on top of a claim
here, the same way this session did before trusting §1's description of its
own prior work.

---

## 8. Phase 4 Part 2 — alert delivery, completed later the same day

Closes the exact gap §2.3/§2.4/§6.5/§7.3 described: `Recommendation`/
`SchemeMatch` rows existed in the DB (§7) with no way for a farmer to see or
respond to them. See `[[phase4-part2-alert-delivery]]` for full detail —
summary here.

### 8.1 What's real now
- `GET /api/v1/alerts` — both record kinds in one response, ownership-scoped
  (recommendation via the field→planting chain, `services/ownership.py`,
  extracted out of `api/v1/sync.py` rather than duplicated; scheme_match via
  `user_id` directly). `PATCH /api/v1/alerts/{kind}/{id}` — per-kind status
  validation (recommendation: acknowledged/followed/ignored; scheme_match:
  viewed/dismissed/claimed), farmer JWT auth, not the internal key.
- `Recommendation` gained a real `confidence` column (migration
  `43d7a9a13999`) — no more inferring confidence from the
  `"[Unverified guidance] "` text prefix.
- **Not the sync protocol** — a deliberate choice, not an oversight. See
  §2.3's updated note.
- Frontend: `services/alerts.ts` rewritten (`fetchAndCacheAlerts`,
  `respondToAlert`), wired into the same `useSyncTriggers.ts` triggers as
  sync/catalog. **No new screen** — Home's alert list and the Schemes tab +
  detail screen were adapted in place rather than building a third surface;
  both work off the same unified `Alert` type now.
- `store/appStore.ts`: `SCHEMA_VERSION` 2 → 3, `migrations[3]` resets
  `alerts` (old mock shape → new `Alert` shape), tested.
- All 10 locales updated, full key-parity checked (not just en.json).

### 8.2 Bug found during E2E testing, not code review
`rec.status = body.status` (bare string) then reading `.status.value` 500'd
— `core/database.py`'s session is `expire_on_commit=False`, so a raw string
assignment never becomes an enum instance post-commit. Fixed: explicit
`RecommendationStatus(...)`/`SchemeMatchStatus(...)` construction on assign.
**Same pattern exists in `api/v1/sync.py`'s push handlers**
(`row.status = payload["status"]`) — not fixed there, because nothing
currently reads `.status.value` back within that same request, so it's a
latent footgun, not an active bug. Worth remembering if `sync.py`'s push
response ever needs to echo back a written row's enum fields.

### 8.3 What's still genuinely open

> **Update 2026-09-04 — much of this section is now closed.** See
> `FRONTEND_BACKEND_GAP_ANALYSIS.md` §10.4d/e. Corrections below.

- ~~The 6 scouting-dependent `agronomic_rules` still can't fire~~ — it was **4**
  (`RICE_STEM_BORER_SCOUT`, `COTTON_PBW_ETL`, `SUGARCANE_EARLY_SHOOT_BORER`,
  `MAIZE_FAW_ETL`), and they **can fire now**: a farmer logs a field-scouting
  count (`app/modals/log-scouting.tsx` → synced `scouting_observations` table →
  `services/recommendation_run.py` feeds it to the rule engine). Still gated
  behind `[Unverified guidance]` pending agronomist sign-off.
- The recommendation/scheme-matching **batch jobs now have a runner** —
  `backend/scripts/run_batch.py` (`--loop` for demos, one-shot for
  cron/Task Scheduler). See `backend/README-ops.md`.
- True bidirectional sync for `recommendations`/`scheme_matches` (offline
  farmer edits) is still unbuilt — deliberately. **They ARE in `api/v1/sync.py`'s
  `TABLES` registry** (this section previously said otherwise — that was wrong),
  but `push_allowed=False` since 2026-09-04: pull serves them, push ignores
  them, delivery is `GET/PATCH /api/v1/alerts`.
- Krishi Bhagya's subsidy-% is still an unverified range (§4's deferred
  table) — now visible to a farmer for the first time via the real
  `detail` field, unchanged in content, just newly reachable.
- The alert-screen **"nearby vendors" list is a known, accepted mock** — 2
  hardcoded shops in `data/mock/demoSeed.json`, no backend. Kept intentionally
  (§5); replace behind a real `GET /api/v1/vendors` when a dealer dataset exists.
