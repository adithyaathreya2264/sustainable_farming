# Architecture and design diagrams

Diagrams are written in [Mermaid](https://mermaid.js.org/), which GitHub, VS Code (with a Mermaid extension) and most Markdown viewers render directly. They describe the code as it is, including known gaps. Sources: `backend/src/routes/`, `backend/src/services/`, `backend/scripts/run-batch.js`, `frontend/sustainable-farming/app/`.

Contents: [1. System architecture](#1-system-architecture) · [2. Data flow](#2-data-flow) · [3. Login and onboarding](#3-sequence-login-and-onboarding) · [4. Photo check](#4-sequence-photo-check) · [5. Alert generation](#5-sequence-alert-generation) · [6. App screen map](#6-app-screen-map)

---

## 1. System architecture

```mermaid
flowchart LR
    subgraph Client["Phone"]
        APP["Chiguru Nele app<br/>Expo / React Native"]
    end

    subgraph Server["Developer machine or server"]
        API["Node.js + Express API<br/>port 8000, /api/v1"]
        BATCH["Batch runner<br/>scripts/run-batch.js"]
        UP[("uploads/ml/<br/>photo files")]
        subgraph ML["ML sidecar - FastAPI, 127.0.0.1:8001"]
            SIDE["ml/serving<br/>loads trained models"]
            ART[("ml/artifacts/<br/>model files")]
        end
        DB[("MySQL 8<br/>sustainable-farming")]
    end

    METEO["Open-Meteo<br/>weather API"]
    TILES["MapTiler<br/>map tiles"]

    APP -- "HTTPS or HTTP, JWT" --> API
    APP -- "map tile requests" --> TILES
    API -- "mysql2 pool" --> DB
    API -- "HTTP, localhost only" --> SIDE
    API -- "write / read / delete" --> UP
    SIDE --> ART
    API -- "weather by lat/long" --> METEO
    BATCH -- "same service code" --> DB
    BATCH -- "weather by lat/long" --> METEO
```

Key points
- The **API** owns authentication, ownership checks, photo storage and the `ml_inferences` audit table.
- The **sidecar** has no database access and listens on localhost only. The API is its only caller. If it is down, ML routes return `503 ml_unavailable` and everything else keeps working.
- **Recommendations and scheme matches** are created by the batch runner (or by `POST /api/v1/internal/*` with `X-Internal-Key`), not per request.
- The app is online-only; there is no offline write queue.

---

## 2. Data flow

```mermaid
flowchart TD
    F["Farmer"] -->|"phone, OTP"| A1["Auth: users row + JWT"]
    F -->|"profile, language, state, district"| A2["users"]
    F -->|"field name, area, boundary, soil type"| A3["fields"]
    F -->|"soil test card"| A4["soil_tests"]
    F -->|"crop, sowing date"| A5["plantings"]
    F -->|"costs, activities"| A6["interventions"]
    F -->|"pest and disease counts"| A7["scouting_observations"]
    F -->|"leaf, soil, insect photos"| P1["API: validate + ownership"]

    P1 -->|"image + fields"| S["ML sidecar"]
    S -->|"label, ranked list, caveats"| P1
    P1 -->|"file"| U[("uploads/ml")]
    P1 -->|"model, request, response, path, sha256"| M["ml_inferences"]
    P1 -->|"result for display"| F

    A3 --> B["Batch job"]
    A5 --> B
    A7 --> B
    W["Open-Meteo weather"] --> B
    R["agronomic_rules + crop_growth_stages"] --> B
    B -->|"rule matches"| REC["recommendations"]
    A2 --> SM["Scheme matcher"]
    SM -->|"matches"| SCH["scheme_matches"]
    REC -->|"GET /alerts"| F
    SCH -->|"GET /alerts"| F
    F -->|"PATCH /alerts: acknowledge, follow, ignore"| REC
```

ML output is stored only in `ml_inferences`. It never writes `recommendations` (rule-engine output only) or alerts.

---

## 3. Sequence: login and onboarding

Login is a **permanent mock**: no OTP is generated or sent, and any phone number works with the fixed `MOCK_OTP` (default `123456`).

```mermaid
sequenceDiagram
    actor F as Farmer
    participant App as Mobile app
    participant API as Express API
    participant DB as MySQL users

    F->>App: Enter 10-digit phone
    App->>API: POST /auth/request-otp
    Note over API: Validates the number only.<br/>No OTP generated, no SMS.
    API-->>App: message OTP sent

    F->>App: Enter OTP 123456
    App->>API: POST /auth/verify-otp
    alt OTP differs from MOCK_OTP
        API-->>App: 401
    else OTP matches
        API->>DB: Find user by phone
        opt No user yet
            API->>DB: INSERT blank user (onboarding_complete = 0)
        end
        API-->>App: access_token (JWT HS256, 7 days)
    end

    App->>API: GET /users/me (Bearer token)
    API->>DB: Load user row
    API-->>App: profile
    alt onboarding not complete
        App->>F: Onboarding steps 1 to 5
        App->>API: PATCH /users/me (unique_id, name, language, unit, area, irrigation, state, district)
        Note over API: 409 if unique_id is already taken
        API-->>App: updated profile
    end
    App->>F: Home tab
```

---

## 4. Sequence: photo check

`POST /api/v1/ml/plantings/:id/photo-check` (the soil-type photo at `POST /ml/soil-type` follows the same pattern without the planting and symptom steps).

```mermaid
sequenceDiagram
    actor F as Farmer
    participant App as Mobile app
    participant API as Express API
    participant ML as ML sidecar
    participant FS as uploads/ml
    participant DB as MySQL

    F->>App: Take or pick a photo
    App->>API: POST photo-check (multipart, field "photo")
    Note over API: multer: memory storage, 8 MB max,<br/>jpeg or png only
    alt too large or wrong type
        API-->>App: 413 image_too_large or 422 invalid_upload
    end

    API->>DB: Check planting belongs to user, crop has ml_key
    alt not owner or crop not modelled
        API-->>App: 403 or 409 crop_not_modelled
    end

    API->>ML: GET /v1/capabilities for the crop (cached 10 min)
    alt capability unavailable or model held
        API-->>App: 409 with reason. Nothing stored.
    end

    opt Conditional model (rice, pearl millet)
        alt symptom_reported is false
            API-->>App: 422 symptom_required. Nothing stored.
        end
    end

    API->>ML: POST /v1/... image + fields (90 s timeout)
    alt sidecar says invalid_image or image_too_large
        ML-->>API: 422 or 413
        Note over API: Photo is discarded, no row written
        API-->>App: error
    else sidecar down, timeout or malformed reply
        API->>FS: Store photo
        API->>DB: INSERT ml_inferences (outcome = error)
        API-->>App: 503 ml_unavailable
    else sidecar refuses (409 or 422)
        API->>FS: Store photo
        API->>DB: INSERT ml_inferences (outcome = refused)
        API-->>App: same status and reason
    else success
        ML-->>API: result (labels, caveats, no probabilities)
        API->>FS: Store photo at YYYY/MM/uuid
        API->>DB: INSERT ml_inferences (outcome = ok, path, sha256, request, response)
        API-->>App: kind, inference_id, result
        App->>F: Result card with confidence label and notice
    end
```

Deletion: `DELETE /ml/inferences/:id` removes the file and clears `image_path`, but keeps the row and its JSON with `deleted_at` set. See [PRIVACY.md](../PRIVACY.md).

---

## 5. Sequence: alert generation

```mermaid
sequenceDiagram
    participant Cron as Batch runner (loop or scheduler)
    participant Run as recommendationRun
    participant DB as MySQL
    participant OM as Open-Meteo
    participant Eng as ruleEngine
    actor F as Farmer
    participant API as Express API

    Cron->>Run: run-batch all
    Run->>DB: Active, non-deleted plantings
    loop each planting (reads happen BEFORE the transaction)
        Run->>DB: Field lat/long
        Run->>OM: Daily weather, past 7 days
        Note over Run,OM: Any error gives an empty snapshot
        Run->>DB: Latest scouting value per metric, last 14 days
    end

    Run->>DB: BEGIN transaction
    loop each planting
        Run->>Eng: evaluatePlanting
        Eng->>DB: Growth stages and active rules for the crop
        Note over Eng: Stage = days since sowing within a stage window.<br/>Skip rules for other stages.
        Eng->>Eng: Condition met? (scouting value first, then weather)
        Eng->>DB: Skip if a pending recommendation for this rule exists
        Eng->>DB: INSERT recommendation (status pending)<br/>text prefixed [Unverified guidance] unless rule is verified
    end
    Run->>DB: COMMIT

    Cron->>DB: Scheme matcher for users with onboarding complete
    Note over DB: PM-KISAN: area above 0.<br/>Krishi Bhagya: rainfed and area at least 0.4047 ha.<br/>Stored as provisional.

    F->>API: GET /alerts
    API->>DB: Recommendations + scheme matches for this user
    API-->>F: Merged list, newest first
    F->>API: PATCH /alerts/recommendation/:id (acknowledged, followed, ignored)
    API->>DB: Update status and responded_at
```

Rules are drafts with no expert sign-off, which is why advice carries the `[Unverified guidance]` prefix. Pest rules fire only when the farmer has logged scouting counts.

---

## 6. App screen map

Navigation gating happens **only** in `app/index.tsx`. No layout checks session or onboarding state, so a deep link into a tab route would bypass it.

```mermaid
flowchart TD
    IDX{"index.tsx<br/>gate"}
    IDX -->|"not signed in"| LOGIN["login"]
    IDX -->|"onboarding incomplete"| S1["onboarding step-1"]
    IDX -->|"ready"| HOME["tabs / home"]

    LOGIN --> OTP["otp"]
    OTP -->|"new user"| S1
    OTP -->|"returning"| HOME
    S1["step-1: unique ID"] --> S2["step-2: language"]
    S2 --> S3["step-3: name"]
    S3 --> S4["step-4: unit and area"]
    S4 --> S5["step-5: irrigation, state, district"]
    S5 --> HOME

    subgraph TABS["Bottom tabs"]
        HOME
        FIELDS["fields"]
        FAB(("+ quick log"))
        SCHEMES["schemes"]
        PROFILE["profile"]
    end

    HOME -->|"alert card"| ALERT["alert/id"]
    HOME -->|"market card"| MARKET["market"]
    HOME -->|"view ledger"| LEDGER["ledger/plantingId"]
    HOME -->|"no fields"| ADDF["modal: add-field"]
    FIELDS --> ADDF
    FIELDS -->|"start planting"| ADDP["modal: add-planting"]
    FIELDS --> LEDGER
    FAB --> QLOG["modal: quick-log"]
    SCHEMES --> SCHEME["scheme/id"]
    PROFILE --> PHIST["photo-history"]
    PROFILE -->|"log out"| LOGIN

    LEDGER --> PCHECK["planting/id/photo-check"]
    LEDGER --> DIS["planting/id/diseases"]
    LEDGER --> SCOUT["modal: log-scouting"]
    LEDGER --> SOIL["modal: add-soil-test"]
    PCHECK -->|"see documented remedies"| DIS
    PCHECK -->|"log a count"| SCOUT
    ALERT -->|"log this action"| QLOG
```

Tabs are Home, Fields, a centre "+" button that opens the quick-log modal (its own `log` tab screen redirects to Home and is effectively unreachable), Schemes and Profile.
