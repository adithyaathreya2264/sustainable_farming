# Frontend ↔ Backend Gap Analysis

_Date: 2026-09-03. Audit of `frontend/sustainable-farming/` (Expo SDK 54) against
`backend/` (FastAPI + SQLAlchemy 2.0 + MySQL 8)._

> **Update (post-implementation): see §10 for what was found, fixed, verified, and
> what remains. §1–§9 are the ORIGINAL audit snapshot and are now largely
> superseded** — §1's "one load-bearing gap" (profile round-trip) and "no CORS"
> are both fixed; §3.1/§3.4/§4/§5/§7/§8/§9 are pre-implementation to-do lists
> that §10.2 / §10.4a–e completed. Read §10 for current state; treat §1–§9 as
> history.

---

## 1. Overall integration status

**Mostly integrated, one load-bearing gap.**

Auth, background sync (fields/plantings/interventions), reference-data catalog,
soil lookup, and the Phase 4 alert feed are all wired frontend→API→DB→UI and
verified in prior slices. The frontend `lib/apiClient.ts` speaks the real
backend wire protocol, the JWT is the real identity everywhere, and the DB is
migrated to head (`43d7a9a13999`) with reference data seeded (2 schemes,
5 crops, 10 varieties, 10 agri inputs, 10 rules, 19 growth stages).

**The gap:** the **user profile / onboarding round-trip does not exist.** The
frontend collects name, language, land-unit, area, irrigation type, state and
district across `(onboarding)/step-1..4` and `(tabs)/profile.tsx`, but there is
**no backend endpoint to read or write a user profile.** `services/onboarding.ts`
and `services/profile.ts` only mutate the local store. Consequences:

- `users.onboarding_complete` is **never set true server-side** →
  `POST /api/v1/internal/run-scheme-matching` filters
  `User.onboarding_complete.is_(True)` and therefore **matches zero users**,
  so the Schemes tab can never populate for anyone.
- `users.state` / `district` / `total_area_hectares` / `irrigation_type` stay at
  the empty/zero defaults written by `verify-otp` → `services/scheme_matcher.py`
  predicates (which read `user.total_area_hectares`, `user.irrigation_type`)
  can't evaluate a real farmer.
- Frontend `user.id` stays the mock `"u1"` forever (`verifyOtp` stores only the
  JWT, never fetches a profile). Harmless today (backend derives owner from the
  JWT and ignores client `user_id`), but it means the app shows no real name and
  the returning-user vs new-user routing in `otp.tsx` always sends users through
  onboarding.

Secondary: **no CORS middleware** (fine for Expo Go native; breaks an
`expo start --web` build or any browser client).

---

## 2. Frontend ↔ Backend API mapping

| Frontend call (`services/…`) | Method + path | Backend handler | Status |
|---|---|---|---|
| `auth.requestOtp` | `POST /api/v1/auth/request-otp` | `api/v1/auth.py:request_otp` | ✅ wired |
| `auth.verifyOtp` | `POST /api/v1/auth/verify-otp` | `api/v1/auth.py:verify_otp` | ✅ wired (but never fetches profile after) |
| `sync-manager.pull` | `GET /api/v1/sync` | `api/v1/sync.py:pull_changes` | ✅ wired (fields/plantings/interventions only) |
| `sync-manager.push` | `POST /api/v1/sync` | `api/v1/sync.py:push_changes` | ✅ wired (create-only; no update/delete payloads) |
| `catalog.fetchAndCacheCatalog` | `GET /api/v1/catalog/crops`, `/agri-inputs` | `api/v1/catalog.py` | ✅ wired |
| `soilLookup.lookupSoilType` | `GET /api/v1/soil-lookup` | `api/v1/soil.py:soil_lookup` | ✅ wired |
| `alerts.fetchAndCacheAlerts` | `GET /api/v1/alerts` | `api/v1/alerts.py:list_alerts` | ✅ wired |
| `alerts.respondToAlert` | `PATCH /api/v1/alerts/{kind}/{id}` | `api/v1/alerts.py:update_alert_status` | ✅ wired |
| `weather.fetchAndCacheWeather` | `GET /api/v1/weather` | `api/v1/weather.py:current_weather` | ✅ wired (geocodes profile state/district → Open-Meteo) |
| `users.fetchProfile` / `updateProfile` | `GET`/`PATCH /api/v1/users/me` | `api/v1/users.py` | ✅ wired |
| `locations.fetchAndCacheLocations` | `GET /api/v1/locations` | `api/v1/locations.py` | ✅ wired (MySQL `locations`, 738 rows; bundled JSON is offline fallback only) |
| `onboarding.completeOnboarding` | `PATCH /api/v1/users/me` | `api/v1/users.py:update_me` | ✅ wired (§10.2 — was ❌ at audit time) |
| `profile.updateLanguage` / `updateUnitPreference` | `PATCH /api/v1/users/me` | `api/v1/users.py:update_me` | ✅ wired (§10.2 — was ❌ at audit time) |
| `scouting.addScoutingObservation` → sync push | `POST /api/v1/sync` (`scouting_observations`) | `api/v1/sync.py` `_apply_scouting_observation` | ✅ wired (§10.4e) |
| `run_batch.py` (scheduler entry) | `POST /api/v1/internal/run-recommendations` | `services/recommendation_run.py` | ✅ triggered by `backend/scripts/run_batch.py` (§10.4d) |
| `run_batch.py` (scheduler entry) | `POST /api/v1/internal/run-scheme-matching` | `services/scheme_run.py` | ✅ triggered by `backend/scripts/run_batch.py` (§10.4d) |

Backend health: `GET /health` — no frontend consumer (fine).

---

## 3. Mismatches and required fixes

### 3.1 Missing endpoints (fix: build them)

- **`GET /api/v1/users/me`** — return the authenticated user's profile so the
  frontend can hydrate real `id` + `onboarding_complete` after OTP verify.
- **`PATCH /api/v1/users/me`** — partial update of name / language_pref /
  default_unit / total_area_hectares / irrigation_type / state / district /
  onboarding_complete. Backs `completeOnboarding` and the profile-screen pickers.

### 3.2 Request/response field mapping (already correct)

`lib/syncMapping.ts` verified against `models/field.py` / `planting.py` /
`intervention.py` — pure camelCase↔snake_case, no shape drift. `boundary` is
`{lat,long}[]` on both sides. `services/alerts.ts` `BackendAlert` matches
`schemas/alerts.py:AlertOut` exactly. `services/catalog.ts` matches
`schemas/catalog.py`. No type mismatches found.

New profile endpoint must follow the same convention:
`total_area_hectares` ↔ `totalAreaHectares`, etc.

### 3.3 Auth

- JWT is HS256, 7-day expiry, `user_id` claim. `get_current_user` resolves the
  row from the claim. `apiClient` attaches `Authorization: Bearer` from
  `getState().authToken`. Correct.
- `verify-otp` auto-creates the `User` with empty onboarding fields — correct,
  but nothing ever fills them in (see §1).

### 3.4 CORS

`backend/main.py` mounts no `CORSMiddleware`. Add one, origins from config
(`CORS_ALLOW_ORIGINS`, default `["*"]` for dev).

### 3.5 Config

- Backend `.env` present and valid; DB reachable; `INTERNAL_API_KEY`,
  `JWT_SECRET`, `FAST2SMS_API_KEY` all set.
- Frontend `.env` has `EXPO_PUBLIC_API_BASE_URL` (a localtunnel URL). `apiClient`
  falls back to `http://10.0.2.2:8000` (Android emulator loopback). OK.

### 3.6 Mock / hardcoded data still in play

| Item | File | Verdict |
|---|---|---|
| `data/mock/user.json` seed (`id:"u1"`) | `store/appStore.ts` | Acceptable as an initial placeholder; **should be overwritten by `GET /users/me`** after login. |
| `data/mock/locations.json` (states/districts) | `services/locations.ts` | No backend location endpoint exists or is planned. Leave as-is (static reference). |
| `data/mock/demoSeed.json` (vendors, demo rows) | `store/appStore.ts` | Demo-only, guarded by `dataOrigin` — never synced. Leave. |
| `getNearbyVendors()` → `getState().vendors` | `services/alerts.ts` | No backend vendor feature. Out of scope. |
| `services/ledger.ts` financials | — | Computed client-side from interventions; no backend equivalent needed. |

### 3.7 Frontend features without backend support

- **Scouting observations**: none _at audit time_. **Built 2026-09-04 (§10.4e)**
  — 4 (not 6) of 10 rules were blocked; they fire now.
- **Vendor directory**: mock-only, out of scope.
- **Language/unit preference persistence**: fixed by the new `PATCH /users/me`.

### 3.8 Backend features without frontend integration

- `POST /api/v1/internal/*` — by design (external cron; `require_internal_key`).
  No frontend change needed, but the app can't _demonstrate_ recommendations or
  scheme matches until these run at least once. Documented.
- `sync.py` handles `recommendations` / `scheme_matches` pull/push; the frontend
  sync client deliberately ignores them (alerts use the separate fetch/PATCH
  path). Consistent with `STATE_OF_THE_SYSTEM.md` §2.3.

---

## 4. Frontend work remaining

1. `services/users.ts` (new) — `fetchProfile()`, `updateProfile(patch)` with
   camel↔snake mapping.
2. `services/auth.ts` — after `verifyOtp` stores the token, call `fetchProfile()`
   and merge real `id` + `onboardingComplete` (+ any server-side profile) into
   the store; derive `isNewUser` from the fetched `onboarding_complete`.
3. `services/onboarding.ts` — `completeOnboarding` PATCHes the backend
   (`onboarding_complete: true` + all fields), then writes local state. Keep the
   local write so the flow still completes offline.
4. `services/profile.ts` — `updateLanguage` / `updateUnitPreference` fire a
   best-effort `PATCH /users/me`.

## 5. Backend work remaining

1. `schemas/users.py` (new) — `UserProfileOut`, `UserProfileUpdateIn` (all
   optional).
2. `api/v1/users.py` (new) — `GET` + `PATCH /api/v1/users/me`, `get_current_user`
   auth.
3. `main.py` — include the router; add `CORSMiddleware`.
4. `core/config.py` — `cors_allow_origins: list[str] = ["*"]`.

## 6. Data-model mismatches

None in the synced entities. The only field-set mismatch is that the frontend
`User` type carries `onboardingComplete` and the backend column is
`onboarding_complete` with no endpoint exposing it — resolved by §5.

`User.default_unit` is `String(16)`; frontend `LandUnit` includes
`"drip_sprinkler"`-length values only for irrigation, units max out at
`"hectare"`/`"sqyard"` — fits. `irrigation_type` `String(32)` vs longest value
`"drip_sprinkler"` (13) — fits.

## 7. Authentication / configuration issues

- None blocking. CORS absence (§3.4) is the only config fix.
- `verify-otp` `isNewUser` is currently derived from the local seed, not the
  server — fixed in §4.2.

## 8. Prioritized implementation plan

1. **P0** Backend `GET`/`PATCH /api/v1/users/me` + schemas + router wiring.
2. **P0** Frontend `services/users.ts` + `auth.ts` profile hydration.
3. **P1** Frontend `onboarding.ts` / `profile.ts` → backend PATCH.
4. **P2** CORS middleware + config.
5. **P2** Verify: OTP → profile → onboarding PATCH → `run-scheme-matching` →
   `GET /alerts` shows a scheme → PATCH status.

## 9. Final integration checklist

- [ ] `GET /api/v1/users/me` returns the JWT user's profile
- [ ] `PATCH /api/v1/users/me` updates a subset of fields + `onboarding_complete`
- [ ] Router wired in `main.py`; CORS mounted
- [ ] `verifyOtp` hydrates real `user.id` + `onboardingComplete`
- [ ] `completeOnboarding` persists to backend
- [ ] Profile pickers persist to backend
- [ ] `run-scheme-matching` produces a `SchemeMatch` for an onboarded user
- [ ] `GET /api/v1/alerts` returns that match; `PATCH` transitions its status
- [ ] `npx jest` green; `npx tsc --noEmit` clean
- [ ] Backend smoke test of the full chain green

---

## 10. Implementation results

### 10.1 What was found

- **Integration was ~85% complete.** Auth, sync, catalog, soil lookup and the
  alert feed were all correctly wired frontend→API→DB→UI by prior slices, with
  clean camel↔snake mapping and JWT-based identity throughout.
- **One load-bearing gap:** no user-profile endpoint. Onboarding and the profile
  screen only mutated local state; `users.onboarding_complete` was never set, so
  `run-scheme-matching` (which filters on it) could never match anyone, and the
  frontend `user.id` stayed the mock `"u1"` forever.
- **One latent sync bug found during E2E testing** (not visible on read): a push
  containing a newly-created field *and* a planting on that field in the same
  request 422'd — pass-1 validation resolved the planting's parent field before
  pass-2 inserted it. This is exactly what `sync-manager.push()` sends after a
  farmer adds a field then a planting offline, so it would have permanently
  wedged that farmer's sync.
- No CORS middleware (fine for Expo Go native, breaks a browser client).
- No backend test infrastructure at all.

### 10.2 What was fixed

**Backend**
- `schemas/users.py` (new) — `UserProfileOut`, `UserProfileUpdateIn` (all fields
  optional).
- `api/v1/users.py` (new) — `GET /api/v1/users/me`, `PATCH /api/v1/users/me`
  (partial update via `model_dump(exclude_unset=True)`), JWT auth, always
  operates on the caller's own row.
- `main.py` — mounted the users router; added `CORSMiddleware` (origins from
  config, `allow_credentials=False` since auth is a Bearer header).
- `core/config.py` — `cors_allow_origins` setting (comma-separated, default `*`)
  + `cors_origins_list` helper.
- `.env.example` — documented `CORS_ALLOW_ORIGINS`.
- `api/v1/sync.py` `push_changes` — pass-1 validation now tracks ids created
  earlier in the same push (FK-safe walk order) and treats a parent being
  created in the same request as owned by the caller. Co-created field+planting
  (and planting+intervention) pushes now succeed.
- `scripts/smoke_e2e.py` (new) — 25-check end-to-end script over the real DB
  (uses FastAPI `TestClient`, already a dependency; no pytest added). Self-cleans.

**Frontend**
- `services/users.ts` (new) — `fetchProfile()` (merges server `id` +
  `onboardingComplete` + saved fields into the store, keeping locally-set values
  the fresh server row doesn't have yet) and `updateProfile(patch)` (writes
  local state first, then best-effort `PATCH`).
- `services/auth.ts` — `verifyOtp` now calls `fetchProfile()` after storing the
  token and derives `isNewUser` from the server's `onboarding_complete`, so
  returning users skip onboarding and `user.id` becomes real.
- `services/onboarding.ts` — `completeOnboarding` PATCHes the full profile +
  `onboarding_complete: true` to the backend (after the local write, so the
  flow still completes offline).
- `services/profile.ts` — `updateLanguage` / `updateUnitPreference` route
  through `updateProfile` (local + best-effort backend PATCH).

Architecture preserved: no new dependencies, same service-layer/apiClient
pattern, same local-first-then-sync behavior as the rest of the app.

### 10.3 What remains

**Resolved 2026-09-04** (see §10.4d/e): the scheduler gap (`run_batch.py`), the
scouting-observation input (4 rules now fire), the `_apply_recommendation`
`confidence` latent 500 (push path gated off), and `data/mock/locations.json`
(→ MySQL `locations`, §10.4c).

Still open:

- `recommendations` / `scheme_matches` are not bidirectionally synced (fetch +
  status-PATCH via `/api/v1/alerts` only) — **by design**, farmers never create
  them. Not a gap.
- The 4 pest/ETL rules can now fire but are `confidence != verified` — output
  carries `[Unverified guidance]`; needs KVK/ICAR agronomist sign-off before it
  reads as advice.
- **Vendor directory** (`getNearbyVendors` / the alert-screen vendor list) — a
  **known, accepted mock**: 2 hardcoded shops in `demoSeed.json`, no backend.
  Kept intentionally (user decision 2026-09-04); replace behind a real
  `GET /api/v1/vendors` when a dealer dataset exists.
- Krishi Bhagya subsidy-% is still an unverified range (`STATE_OF_THE_SYSTEM.md`
  §4).
- Fast2SMS OTP delivery still unverified in production (`STATE_OF_THE_SYSTEM.md`
  §4) — smoke test monkeypatches the send.

### 10.4 Tests performed

| Test | Result |
|---|---|
| `backend/scripts/smoke_e2e.py` — now **39 checks** (OTP → profile → weather → locations → soil → catalog+growth_stages → co-created field+planting+**scouting obs** push → pull ownership → **recommendations-in-push ignored** → scheme matching → **run-recommendations fires the scouting rule + idempotent** → alert feed has both kinds → status PATCH → 422 → unauth 401) | **39/39 pass** |
| Verified `run-scheme-matching` returns `matches_created: 2` for the onboarded smoke user (was 0 before — `onboarding_complete` now set) | ✅ |
| Verified `run-recommendations` created a recommendation for the pushed planting and it appears in `GET /api/v1/alerts` | ✅ |
| Frontend `npx tsc --noEmit` | **clean** |
| Frontend `npx jest` (18 tests: appStore migration incl. v4→v5, sync guard, scouting service + mapping + `metricForPlanting`) | **18/18 pass** |
| Backend `from backend.main import app` import | ✅ |
| DB state check (migrations at `43d7a9a13999`, reference data seeded) | ✅ |

### 10.4a Mock auth (added after project-guide sign-off)

Phone+OTP was reverted to a mock per the project guide's decision on the app's
auth story. `DEV_AUTH_BYPASS=true` (`backend/core/config.py`, `.env`):

- `POST /api/v1/auth/request-otp` — no-op, always 200 (no Fast2SMS call, no rate
  limit, no `OtpRequest` row).
- `POST /api/v1/auth/verify-otp` — accepts `DEV_AUTH_OTP` (`123456`) for **any**
  phone number, find-or-creates the `User`, and issues a **real JWT** — so sync,
  profile, catalog, alerts all keep working unchanged.
- Phone validation is relaxed to any 10 digits in bypass mode (a tester types a
  random number, not a real Indian mobile).

Set `DEV_AUTH_BYPASS=false` to restore the real OTP + Fast2SMS flow (code path
untouched). Frontend needed no change — it still calls the same endpoints.

### 10.4b Live weather widget (added 2026-09-04)

The dashboard `WeatherWidget` was a static mock ("Mysuru, Karnataka · 27°C").
Now wired end-to-end to the farmer's onboarding state/district:

- **`GET /api/v1/weather`** ([backend/api/v1/weather.py](backend/api/v1/weather.py))
  — JWT auth; resolves `current_user.state` / `district` (or `?state=&district=`
  overrides), geocodes `"<district>, <state>, India"` via Open-Meteo's free
  geocoding API (no key), then pulls the `current` block + a 4-day daily
  forecast from the same Open-Meteo forecast service `core/weather.py` already
  used for the rule engine. Always 200 — `available: false` when no location is
  set / geocoding fails / provider unreachable. 10-minute in-process cache.
- [backend/services/weather_report.py](backend/services/weather_report.py) (new)
  — geocode + fetch + WMO-code→`{group, label}` mapping, graceful degradation.
- [backend/schemas/weather.py](backend/schemas/weather.py) (new).
- Frontend [services/weather.ts](frontend/sustainable-farming/services/weather.ts)
  (new) `fetchAndCacheWeather()` — cached into `appStore.weather`
  (`SCHEMA_VERSION` 3→4, `migrations[4]`), refreshed from the same
  `useSyncTriggers` trigger set as sync/catalog/alerts, plus a mount-time fetch
  in the widget.
- [components/WeatherWidget.tsx](frontend/sustainable-farming/components/WeatherWidget.tsx)
  rewritten to render the real snapshot (condition emoji + label, temp,
  humidity, wind, tomorrow's forecast) with loading / no-location / unavailable
  states. 7 new i18n keys added to all 10 locales (`home.weatherLoading`,
  `weatherSetLocation`, `weatherUnavailable`, `weatherTomorrow`, `humidity`,
  `wind`, `rain`).

Verified live: `Karnataka/Mysuru` → `30.7°C, Overcast, humidity 56%`, 4-day
forecast; `Punjab/Amritsar` override → `32.4°C, Clear sky`. In smoke_e2e.py
(checks 30/30).

Weather condition **labels** are English from the backend (matches the old
widget's bar); full per-locale condition text is a future pass — the frontend
already receives a stable `condition_group` key it could map to i18n.

### 10.4c Locations moved to MySQL + dead mock files removed (2026-09-04)

Cleanup pass toward "all reference data in MySQL 8":

- **Deleted** `frontend/.../data/mock/crops.json` and `agriCatalog.json` — dead
  files, not imported anywhere (superseded by `GET /api/v1/catalog/*`).
- **State/district lists → MySQL.** New `locations` table (`models/location.py`,
  migration `a1b2c3d4e5f6`, 738 rows / 36 states), seeded by
  `seed_reference_data.py` from `backend/scripts/seed_data/locations.json`.
  New **`GET /api/v1/locations`** ([backend/api/v1/locations.py](backend/api/v1/locations.py))
  returns them grouped by state.
- Frontend [services/locations.ts](frontend/sustainable-farming/services/locations.ts)
  now fetches from the backend (cached in-module, refreshed from the
  `useSyncTriggers` set). `data/mock/locations.json` moved to
  `data/locationsFallback.json` and is now **only** a bundled offline fallback
  for first-run onboarding with no connectivity — the server is the source of
  truth.

Remaining frontend seed files: `data/mock/user.json` (empty placeholder,
overwritten by `GET /users/me`) and `data/mock/demoSeed.json` (the "Load sample
data" button only, never synced). Both intentional.

### 10.4d Batch scheduler + counter-lock fix + sync-push cleanup (2026-09-04)

Closes the "no scheduler" gap — `/api/v1/internal/*` were only ever hit by the
smoke test, so the app never surfaced a *new* recommendation/scheme match on
its own.

- **`backend/scripts/run_batch.py`** (new) — `python -m backend.scripts.run_batch
  {recommendations|scheme-matching|all} [--loop --interval N]`. Zero new
  dependencies (stdlib `argparse`/`time`). See `backend/README-ops.md` for
  Task Scheduler / cron wiring.
- Endpoint bodies extracted to **`backend/services/recommendation_run.py`** /
  **`scheme_run.py`**; `api/v1/internal.py` routes now delegate to them (same
  response shapes, still `X-Internal-Key` gated).
- **Counter-lock fix** — `recommendation_run.py` fetches every planting's
  Open-Meteo weather snapshot *before* `bump_sync_counter` opens the
  `SELECT ... FOR UPDATE` on the `sync_counter` row. Previously the lock was
  held across N weather HTTP calls, blocking any concurrent farmer sync push
  for the whole batch.
- **Sync-push cleanup** — `_TableConfig` gained `push_allowed`; `recommendations`
  and `scheme_matches` are now `push_allowed=False` (pull still serves them).
  `_apply_recommendation`/`_apply_scheme_match` are replaced by a
  `_push_not_allowed` tripwire — kills the latent `confidence`-column 500 (a
  recommendations block in a push body is now silently ignored). Removed
  `"recommendations"` from `_PARENT_FK`.

### 10.4e Field scouting observations (2026-09-04)

Closes the "N of 10 rules can't fire" gap (it's **4 of 10**, not 6 — the other
6 are stage-only and already fired). New farmer-owned, planting-scoped, synced
table, same pattern as `interventions`.

- **Backend** — `models/scouting_observation.py` (`ScoutingObservation`,
  `SyncMixin`); migration `2dbb7f768aad`; `api/v1/sync.py` `TABLES` entry
  (`push_allowed=True`, `_PARENT_FK` for co-create); `services/recommendation_run.py`
  builds `{metric_key: value}` from the latest non-deleted observation per
  planting within a **14-day recency window** and passes it to
  `evaluate_planting` (rule engine unchanged — `_condition_met` already
  consumed that shape). Growth-stage windows added to `GET /api/v1/catalog/crops`
  (`Crop.growth_stages` relationship + `CropOut.growth_stages`) so the client
  can work out a planting's current stage.
- **Frontend** — `types/models.ts` `ScoutingObservation` + `Crop.growthStages`;
  `services/scouting.ts` (`addScoutingObservation`); `lib/syncMapping.ts`
  converters; `lib/scoutingMetrics.ts` (4 metrics + `metricForPlanting`);
  `store/appStore.ts` (`SCHEMA_VERSION` 4→5, `migrations[5]`, PERSISTED_KEYS,
  resetDemo/markLiveSession/pruneOrphanedCatalogRefs); `services/sync-manager.ts`
  wires `scouting_observations` into pull/collectDirty/push; new modal
  `app/modals/log-scouting.tsx` launched from the planting ledger only when a
  metric is due; 12 i18n keys × 10 locales.
- **Verified end-to-end** (`smoke_e2e.py`, 39/39): push a scouting observation
  (`dead_hearts_percent=8`) for a Rice planting sown 30 days ago → `run_batch
  recommendations` → a `RICE_STEM_BORER_SCOUT` recommendation appears in
  `GET /api/v1/alerts` (it did not before) → 2nd run is idempotent.

The 4 pest rules are still `confidence != verified` — output still carries the
`[Unverified guidance]` prefix and needs KVK/ICAR sign-off before it's advice.

### 10.5 Blockers

None. The full chain **Frontend service → apiClient → FastAPI → SQLAlchemy →
MySQL → response → store → screen** is verified working end-to-end for auth,
profile/onboarding, fields/plantings/interventions sync, catalog, soil lookup,
and the alert feed.

Not verified in a live Expo Go client (no device in this environment) — the
frontend paths are exercised via `tsc` + unit tests + a backend E2E that speaks
the exact wire shapes `services/*.ts` produce. A device pass is the one
remaining manual QA step.

### 10.6 Checklist (final)

- [x] `GET /api/v1/users/me` returns the JWT user's profile
- [x] `PATCH /api/v1/users/me` updates a subset of fields + `onboarding_complete`
- [x] Router wired in `main.py`; CORS mounted
- [x] `verifyOtp` hydrates real `user.id` + `onboardingComplete`
- [x] `completeOnboarding` persists to backend
- [x] Profile pickers persist to backend
- [x] `run-scheme-matching` produces a `SchemeMatch` for an onboarded user
- [x] `GET /api/v1/alerts` returns that match; `PATCH` transitions its status
- [x] Co-created field+planting sync push no longer 422s
- [x] Batch scheduler (`run_batch.py`) + counter-lock fix + sync-push cleanup
- [x] Scouting observations: push → rule fires → recommendation in `/alerts`
- [x] `GET /api/v1/catalog/crops` returns growth-stage windows
- [x] `npx jest` green (18/18); `npx tsc --noEmit` clean
- [x] Backend E2E smoke test green (39/39)
- [x] `alembic` down/up reversibility cycle for `2dbb7f768aad`
- [ ] Live Expo Go device pass (manual, needs hardware) — incl. the new
      "Log Field Scouting" flow from the planting ledger
