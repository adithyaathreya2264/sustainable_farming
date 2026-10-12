# Chiguru Nele — Sustainable Farming App

A mobile app for Indian farmers. Farmers register their fields and plantings, log soil tests, interventions and pest scouting, and get rule-based alerts, matched government schemes, weather, market price outlooks and ML-assisted advice (crop choice, fertilizer, disease and pest checks from photos, yield outlook). The UI ships in 10 languages.

> **Status: local development / demo build.** Login is a permanent mock, several data sources are unverified, and nothing here is production-hardened. Read [Known limitations](#known-limitations) before presenting any number or advice from this system as fact.

> **Disclaimer.** Advice, alerts and model results are unverified computer output, not reviewed by an agronomist, and not a substitute for your local agriculture officer or KVK. Scheme matches, prices and yield outlooks are indicative only. Use at your own risk. Full text: [DISCLAIMER.md](DISCLAIMER.md). Data handling: [PRIVACY.md](PRIVACY.md).

## Table of contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Repository structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Getting started](#getting-started)
- [Configuration](#configuration)
- [Backend](#backend)
- [Frontend](#frontend)
- [Machine learning](#machine-learning)
- [Testing](#testing)
- [Known limitations](#known-limitations)
- [Further documentation](#further-documentation)
- [Author and licence](#author-and-licence)

## Features

- **Phone + OTP login** (mock — see limitations) and a 5-step onboarding flow where the farmer picks a unique 4-digit ID.
- **Fields and plantings**: draw field boundaries on a map, record soil-test cards, add plantings with crop, variety and growth stage.
- **Interventions and scouting logs**: record fertiliser/pesticide/irrigation work and pest counts per field.
- **Rule-engine alerts**: agronomic rules evaluate plantings against weather and scouting data and raise alerts the farmer can acknowledge.
- **Government scheme matching**: schemes are matched to the farmer's profile (matches are marked provisional).
- **Weather**: live forecast for the farmer's state/district via Open-Meteo (no API key).
- **Market outlook**: 13-week-ahead Karnataka mandi price outlook for the commodities whose model passes its accuracy bar.
- **ML advice**: crop recommendation, fertilizer targets, soil fertility, yield outlook (percentile band only), crop-scoped disease Q&A.
- **ML photo checks**: soil type, insect detection, leaf-condition and part classifiers for several crops, wheat heading, tobacco lesion severity. Photos can be reviewed and deleted by the farmer.
- **10 languages**: English, Hindi, Kannada, Tamil, Telugu, Malayalam, Bengali, Gujarati, Punjabi, Manipuri.

## Architecture

```
 ┌────────────────────┐   HTTP + JWT    ┌─────────────────────────┐   mysql2   ┌─────────┐
 │  Expo / React      │ ──────────────► │  Node.js + Express API  │ ─────────► │ MySQL 8 │
 │  Native app        │   :8000         │  /api/v1/*              │            └─────────┘
 │  (Chiguru Nele)    │                 │  auth, data, rules,     │
 └────────────────────┘                 │  schemes, alerts        │   HTTP     ┌───────────────────────┐
                                        │                         │ ─────────► │ FastAPI ML sidecar    │
                                        └─────────────────────────┘  127.0.0.1 │ ml/serving  (:8001)   │
                                                  ▲                    :8001   │ loads trained models  │
                       batch runner (cron / loop) │                            └───────────────────────┘
                       npm run batch -- all ──────┘                            Open-Meteo (weather) ◄── API
```

- The **API** owns authentication, ownership checks, photo storage and the `ml_inferences` audit table.
- The **ML sidecar** has no database access and binds to localhost only. The Node API is its only caller.
- If the sidecar is down, ML routes return `503 {"reason": "ml_unavailable"}` and the rest of the app keeps working.
- **Recommendations and scheme matches are produced by batch jobs**, not per request. Until a batch runs, no new ones appear.
- The app is **online-only**. There is no offline write queue; a failed create shows an error toast.

## Tech stack

| Layer | Technology |
|---|---|
| Mobile app | Expo SDK 54, React Native 0.81, React 19, TypeScript 5.9, expo-router 6, NativeWind 4 (Tailwind 3), Reanimated 4, i18next |
| API | Node.js ≥ 20 (ESM), Express 5, mysql2, jsonwebtoken, multer, dotenv |
| Database | MySQL 8, plain-SQL migrations tracked in `schema_migrations` |
| ML serving | Python 3.13, FastAPI, uvicorn |
| ML training | scikit-learn, XGBoost, PyTorch (CPU) / torchvision, ultralytics (YOLOv8), pandas, numpy |
| External | Open-Meteo (weather), MapTiler (field-boundary map imagery) |

## Repository structure

```
sustainable_farming/
├── backend/                  Node/Express API
│   ├── src/                  app.js, server.js, config, auth, db, routes/, services/
│   ├── migrations/           0001–0005 plain SQL migrations
│   ├── scripts/              seed, batch runner, ML launcher, smoke test, seed data
│   ├── test/                 node:test suites
│   ├── plan/                 historical task plans
│   ├── uploads/              stored photo-check images (gitignored)
│   └── README-ops.md         operations guide (batch jobs, migrations, sidecar, seeding)
├── frontend/
│   └── sustainable-farming/  Expo app (app/, components/, services/, store/, locales/, hooks/, lib/)
├── ml/                       training, inference algorithms, FastAPI sidecar
│   ├── training/             offline training scripts
│   ├── algorithms/           inference functions
│   ├── serving/              FastAPI sidecar
│   ├── features/ prep/       shared preprocessing, dormant cleaners
│   ├── artifacts/            trained models (gitignored)
│   └── README.md             model roster, rules, commands
├── datasets/                 raw third-party data (gitignored, ~140 MB)
├── docs/                     working drafts, e.g. agronomic rules (gitignored)
├── STATE_OF_THE_SYSTEM.md    system baseline and "do not treat as production-ready" list
├── DATASETS_STATUS.md        data-integrity findings
└── FRONTEND_BACKEND_GAP_ANALYSIS.md
```

## Prerequisites

- **Node.js ≥ 20** and npm
- **MySQL 8**
- **Python 3.13** (only for the ML sidecar and training)
- **Expo Go** on a phone (same Wi-Fi as your PC), or an Android/iOS emulator
- Windows is the primary development platform; the commands below use Windows venv paths (`.venv/Scripts/`). On Linux/macOS use `.venv/bin/`.

## Getting started

### 1. Database

Create a database named `sustainable-farming` and an application user (the example config uses `sf_app`) with full rights on it.

### 2. Backend

```bash
cd backend
npm install
cp .env.example .env      # then fill in DATABASE_URL, JWT_SECRET, INTERNAL_API_KEY
npm run migrate           # creates the schema
npm run seed              # idempotent reference data: crops, rules, schemes, locations
```

Generate secrets with `node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"`.

### 3. ML environment (optional but needed for ML features)

From the repo root:

```bash
python -m venv .venv --system-site-packages
./.venv/Scripts/python.exe -m pip install -r ml/requirements.txt
./.venv/Scripts/python.exe -m pip install torchvision --index-url https://download.pytorch.org/whl/cpu
```

Trained model artifacts (`ml/artifacts/`) and raw datasets (`datasets/`) are **not in git**.

**Models** are hosted on the Hugging Face Hub. Download them instead of retraining:

```bash
./.venv/Scripts/python.exe -m pip install huggingface_hub
# if the repo is private: huggingface-cli login
export HF_REPO_ID="<hf-username>/<models-repo>"     # PowerShell: $env:HF_REPO_ID="..."
./.venv/Scripts/python.exe -m ml.hf_artifacts fetch
```

The maintainer publishes with `python -m ml.hf_artifacts upload` (private repo by default). Large regenerable folders (`image_cache`, `yolo_data`, `yolo_runs`) are not uploaded.

**Datasets** are only needed for retraining. Get them from their original sources, listed in [datasets/README.md](datasets/README.md). Training commands are in [ml/README.md](ml/README.md). Until models are present, the corresponding ML routes report the model as unavailable.

### 4. Run the API (and sidecar)

```bash
cd backend
npm run dev:all           # API on :8000 + ML sidecar on :8001, Ctrl+C stops both
# or, without ML:
npm run dev
```

Optionally, in a second terminal, run the batch jobs on a loop so alerts and scheme matches appear:

```bash
cd backend
npm run batch -- all --loop --interval 900
```

### 5. Run the app

```bash
cd frontend/sustainable-farming
npm install
# create .env — see Configuration below
npx expo start -c
```

Scan the QR code with Expo Go. **Dev login:** any phone number with OTP `123456`.

## Configuration

### Backend — `backend/.env` (see `backend/.env.example`)

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | yes | — | MySQL connection string (`mysql+pymysql://` and `mysql://` prefixes both accepted) |
| `JWT_SECRET` | yes | — | Signs farmer JWTs |
| `INTERNAL_API_KEY` | yes | — | Shared secret for `/api/v1/internal/*` (sent as `X-Internal-Key`) |
| `MOCK_OTP` | no | `123456` | OTP accepted for any phone number |
| `MYSQL_ROOT_PASSWORD` | no | — | Only needed transiently to provision the database |
| `CORS_ALLOW_ORIGINS` | no | `*` | Comma-separated origins; tighten outside dev |
| `JWT_ALGORITHM` | no | `HS256` | |
| `JWT_EXPIRY_MINUTES` | no | `10080` | 7 days |
| `PORT` | no | `8000` | API port |
| `ML_SIDECAR_URL` | no | `http://127.0.0.1:8001` | Where the API finds the sidecar |
| `ML_SIDECAR_PORT` | no | `8001` | Sidecar port |
| `ML_PYTHON_BIN` | no | repo `.venv` interpreter | Python used to start the sidecar |
| `ML_PRELOAD` | no | off | `1` warms every model at sidecar start |

`.env` is gitignored. Never commit real secrets.

### Frontend — `frontend/sustainable-farming/.env`

| Variable | Purpose |
|---|---|
| `EXPO_PUBLIC_API_BASE_URL` | Backend base URL. Physical phone: `http://<PC-LAN-IP>:8000`. Android emulator: `http://10.0.2.2:8000`. iOS simulator: `http://localhost:8000`. Phone on mobile data: a tunnel such as `npx localtunnel --port 8000`. |
| `EXPO_PUBLIC_MAP_TILER_API_KEY` | MapTiler key for the field-boundary map imagery |

`EXPO_PUBLIC_*` values are inlined at bundle time, so restart with `npx expo start -c` after changing them.

## Backend

### npm scripts (run from `backend/`)

| Script | Does |
|---|---|
| `npm start` | Start the API on `0.0.0.0:8000` |
| `npm run dev` | Same, restarting on file changes |
| `npm run ml` | Start the ML sidecar alone |
| `npm run dev:all` | API + sidecar together |
| `npm run migrate` | Apply SQL migrations |
| `npm run seed` | Seed reference data (insert-only, idempotent) |
| `npm run batch -- <recommendations\|scheme-matching\|all> [--loop --interval <s>]` | Run the rule engine / scheme matcher |
| `npm run smoke` | End-to-end smoke test against the dev DB |
| `npm test` | Unit tests (no DB or network) |

### API overview

All routes are under `/api/v1` and need a farmer JWT unless noted. `GET /health` is unauthenticated.

| Prefix | Purpose |
|---|---|
| `/auth` | `POST /request-otp`, `POST /verify-otp` (no JWT) |
| `/users` | `GET/PATCH /me` (profile; 409 on duplicate `unique_id`) |
| `/fields` | CRUD, plus `POST /:id/soil-tests` |
| `/plantings` | CRUD, plus `GET /recommend-crop` |
| `/interventions` | CRUD |
| `/scouting-observations` | list, create, delete |
| `/catalog`, `/locations`, `/soil-lookup` | Reference data: crops, agri inputs, states/districts, soil type by location |
| `/alerts` | `GET /`, `PATCH /:kind/:alertId` |
| `/weather` | Weather for the profile's state/district |
| `/ml` | Capabilities, soil-type and planting photo checks, fertilizer, yield outlook, disease Q&A, soil fertility, market outlook, inference history |
| `/internal` | `POST /run-recommendations`, `POST /run-scheme-matching` — `X-Internal-Key` header instead of JWT |

### Batch jobs and migrations

The rule engine and scheme matcher run as idempotent batch jobs. Use a loop for demos and one-shot runs under Windows Task Scheduler or cron for anything longer-lived. Migrations are numbered SQL files in `backend/migrations/`; a database created by the old Alembic tooling is stamped rather than recreated. Details: [backend/README-ops.md](backend/README-ops.md).

## Frontend

Located in [frontend/sustainable-farming/](frontend/sustainable-farming/). Highlights:

- **Routing**: file-based via expo-router — `(auth)` login/OTP, `(onboarding)` steps 1–5, `(tabs)` home / fields / log / schemes / profile, plus alert, scheme, ledger, market, photo-history and planting (diseases, photo check) screens and modals for adding fields, plantings, soil tests and scouting.
- **State**: a hand-rolled store (`store/appStore.ts`) persisted to AsyncStorage as a versioned envelope with a migration chain. Services in `services/` call the API through `lib/apiClient.ts`.
- **i18n**: `locales/*.json` for 10 languages. Manipuri (`mni`) translations are machine-generated and unverified.
- **Scripts**: `npm start`, `npm run android`, `npm run ios`, `npm run web`, `npm test`.

More: [frontend/sustainable-farming/README.md](frontend/sustainable-farming/README.md).

## Machine learning

The `ml/` package trains models offline, loads them in a FastAPI sidecar, and exposes them to the app only through the Node API.

**Roster (see [ml/MODEL_RESULTS.md](ml/MODEL_RESULTS.md) for metrics):**

- **Shipped:** 22 models cleared their pre-registered accuracy bars. 21 are served; wheat-kernel damage (model 28) is held in `ml/serving/holds.py` pending a lighting check.
- **Rejected:** 6 trained models failed their bars (unscoped disease Q&A, original soil fertility, sugarcane leaf, wheat canopy segmentation, soybean yield, vegetable classifier) and are never served.
- **Trained but never served:** sugarcane yield, because its data is synthetic.
- **Not trained:** models with no usable data, listed in [ml/PARKED_MODELS.md](ml/PARKED_MODELS.md).

**Four rules enforced in code:**

1. No probabilities cross the API — only `unverified`, `provisional` or `verified` labels. No model can promote itself to `verified`.
2. No model emits prose or product names; products come from the `agri_catalog` table.
3. Yield is a percentile band, never a number.
4. A model that failed its bar cannot be served (`ModelDidNotShip` → HTTP 409).

Training commands, timings and sidecar endpoints are in [ml/README.md](ml/README.md); the serving design is in [ml/ML_SERVING_INTEGRATION.md](ml/ML_SERVING_INTEGRATION.md).

## Testing

| Suite | Command |
|---|---|
| Backend unit tests (no DB/network) | `cd backend && npm test` |
| Backend end-to-end smoke (needs MySQL; `SMOKE_BASE_URL` targets a running server) | `cd backend && npm run smoke` |
| Frontend (jest-expo) | `cd frontend/sustainable-farming && npm test` |
| ML sidecar | `./.venv/Scripts/python.exe -m pytest ml/serving/tests -q` |

## Known limitations

This project is honest about what is not verified. Do not remove these caveats when presenting results.

- **Agronomic rules are drafts.** The rule matrix has had no KVK/ICAR expert sign-off; advice is prefixed `[Unverified guidance]`. Pest rules only fire when the farmer logs scouting counts.
- **Scheme matches are provisional**, because the farmer profile cannot fully check eligibility. Some subsidy figures are stored as ranges.
- **Land-unit conversions:** only standard units and the Karnataka Guntha are verified. Bigha, Katha, Biswa, Kanal and Marla are provisional.
- **Dataset integrity** (details in [DATASETS_STATUS.md](DATASETS_STATUS.md)):
  - The crop-yield column has no unit that applies across crops, so only within-crop percentiles are shown.
  - The fertilizer dataset is synthetically expanded.
  - The soil image split leaks (~19% of training images are near-duplicates of test images).
  - The sugarcane leaf photo model memorised capture sessions and was rejected.
  - Vegetable labels conflict at source.
  - The soil-fertility data's provenance is unverified.
  - Dataset licences have not been verified.
- **Every shipped model is provisional.** Several were trained on lab or PlantVillage-style photos and may not generalise to field conditions. Some models cover crops the app only recently added, with no varieties, stages or rules yet.
- **Mocks and placeholders:** login accepts a fixed OTP for any number (no SMS provider); the nearby-vendors list is hard-coded; the soil lookup uses placeholder in-memory data; Bengaluru resolves to the Karnataka-wide price series.
- **Photo consent:** `users.photo_training_consent` is recorded but nothing reads it yet. Do not export photos for training without filtering on it.
- **Local only:** no Docker, no HTTPS, CORS defaults to `*`, API listens on all interfaces. Not production-hardened.
- **Docs drift:** the backend was rewritten from FastAPI to Node/Express with the same endpoints and schema. Parts of `STATE_OF_THE_SYSTEM.md` and `FRONTEND_BACKEND_GAP_ANALYSIS.md` still describe the FastAPI/offline-sync design and are historical. Verify against the code.

## Further documentation

| Document | Contents |
|---|---|
| [documentation/ARCHITECTURE.md](documentation/ARCHITECTURE.md) | System architecture, data flow, login / photo-check / alert sequence diagrams, app screen map |
| [documentation/DATABASE.md](documentation/DATABASE.md) | ER diagram, every table and column, migration history |
| [documentation/MODEL_CARDS.md](documentation/MODEL_CARDS.md) | One card per shipped model: data, metrics, limits, out-of-scope uses |
| [PRIVACY.md](PRIVACY.md) | What is collected, photo consent, retention and deletion, security gaps (draft) |
| [DISCLAIMER.md](DISCLAIMER.md) | Advice is unverified and not a substitute for an agronomist |
| [STATE_OF_THE_SYSTEM.md](STATE_OF_THE_SYSTEM.md) | Baseline snapshot and the not-production-ready list |
| [DATASETS_STATUS.md](DATASETS_STATUS.md) | Data-integrity findings that constrain how numbers are shown |
| [FRONTEND_BACKEND_GAP_ANALYSIS.md](FRONTEND_BACKEND_GAP_ANALYSIS.md) | Frontend/backend integration audit (§10 is current) |
| [backend/README-ops.md](backend/README-ops.md) | Running the API, batch jobs, migrations, seeding |
| [frontend/sustainable-farming/README.md](frontend/sustainable-farming/README.md) | Mobile app guide |
| [ml/README.md](ml/README.md) | ML roster, rules, training and serving |
| [ml/MODEL_BARS.md](ml/MODEL_BARS.md), [ml/MODEL_RESULTS.md](ml/MODEL_RESULTS.md) | Pre-registered accuracy bars and measured results |
| [ml/PARKED_MODELS.md](ml/PARKED_MODELS.md), [ml/UNBLOCKING_PARKED_MODELS.md](ml/UNBLOCKING_PARKED_MODELS.md) | Models not trained, and what would unblock them |
| [ml/ML_SERVING_INTEGRATION.md](ml/ML_SERVING_INTEGRATION.md) | Sidecar design and integration notes |

## Author and licence

Built by Adithya Athreya as a major project.

No licence has been chosen for this repository yet, so all rights are reserved by default. Third-party datasets keep their own licences (for example the insect test image used by the smoke test is CC BY 4.0 from Roboflow), and their provenance is not fully verified.
