# ML Serving Integration

_Last updated 2026-09-26. How the models trained in `ml/` reach the app: the
Python sidecar, the Node routes, the database, the frontend screens,
verification and known limits. This describes the system as it is now; §12
records what changed when._

Related documents:

- `ml/README.md` explains the models.
- `ml/MODEL_RESULTS.md` records each model's measured result and ship/hold decision.
- `backend/README-ops.md` covers running the backend.
- `STATE_OF_THE_SYSTEM.md` is the pre-Phase 4 baseline.

---

## 1. Summary

**22 models cleared their bars. 21 are served, and 1 (wheat kernels, 28) is
built but held** until a lighting check is done. They reach 14 app crops
through one Python sidecar that the Node API proxies to.

Before this work the app could reach one model, crop recommendation, through a
Python process started per request
(`backend/src/services/cropRecommendation.js`). That bridge was broken on the
dev machine: it looked for the virtualenv at `ml/.venv`, but the venv lives at
the repo root. The goal was for every shipped model to reach a farmer through
the existing Expo → Node/Express → MySQL app, without breaking the rules the ML
phase set.

### Decisions

| Date | Question | Decision |
|---|---|---|
| 2026-09-24 | How Node calls Python | A **FastAPI sidecar** on `127.0.0.1:8001`, proxied by Node. The spawn bridge was retired. |
| 2026-09-24 | Scope | Every shipped model. **Pearl millet, wheat and tobacco** were added as app crops so models 13, 14b and 17 are reachable. |
| 2026-09-24 | Uploaded photos | **Stored on disk**, with an audit row per photo. The farmer can delete them. |
| 2026-09-24 | Environment | Local dev/demo only (no Docker). |
| 2026-09-26 | Models 20-27 | **Coffee, tea, cauliflower, onion, potato and tomato** were added as app crops. |
| 2026-09-26 | Model 28 (wheat kernels) | **Build it, keep it hidden.** Photo colour alone scores 0.94 on its test set, so `MODEL_RESULTS.md` §28 asks for a check under different lighting first. |

All new crops are seeded with **no varieties, growth stages or agronomic
rules**. None have been sourced or verified, and inventing them would
contradict the project's verification discipline.

### Rules the integration must not break (from `ml/README.md`)

1. **No probability crosses the API.** Only the labels `unverified`,
   `provisional` or `verified` do.
2. **No model prose or product names.** Products come from `agri_catalog`.
3. **Yield is a percentile band, never a number.** The source data has no yield unit.
4. **Rejected and held models stay unreachable.** This is enforced in code, not
   in docs.

Two further conditions carried forward:

- **Disease Q&A (model 4b) ships only while a visible "see all diseases for
  this crop" path exists** (`MODEL_RESULTS.md` §4b).
- **ML output never writes `recommendations` or alerts.** That table is
  rule-engine output: it is FK'd to `plantings` and its confidence enum does not
  fit model labels.

---

## 2. Architecture

```
Expo app ──JSON / multipart──▶ Node API :8000   /api/v1/ml/*, /api/v1/plantings/recommend-crop,
                                 │               /api/v1/fields/:id/soil-tests
                                 │  auth, ownership, photo storage, ml_inferences rows, caching
                                 └──HTTP (localhost only)──▶ FastAPI sidecar 127.0.0.1:8001  /v1/*
                                                               └─ ml.algorithms.* (lazy-loaded, cached)
```

- **Node** owns identity, ownership checks, database writes and files on disk.
- **The sidecar** is stateless apart from its in-memory model caches. It has no
  database access and no auth, and it binds to localhost only.
- **Stripping raw outputs, mapping errors and enforcing holds** all happen
  inside the sidecar, so even a direct call to it cannot leak a raw yield
  number or a probability, or reach a held model.

### Running it

```bash
cd backend
npm run dev:all              # API (node --watch) + sidecar, prefixed output; Ctrl+C stops both
npm run ml                   # sidecar alone
ML_PRELOAD=1 npm run ml      # sidecar, warming every served model first (for demos)
```

| Setting | Default |
|---|---|
| `ML_SIDECAR_URL` | `http://127.0.0.1:8001` |
| `ML_PYTHON_BIN` | `../.venv/Scripts/python.exe`, or `.venv/bin/python` |
| `ML_SIDECAR_PORT` | `8001` |

The first call to a photo model loads its weights, which takes a few seconds.
Later calls take about a second on CPU.

---

## 3. What each model does in the app

### Model → feature map

| # | Model | Where the farmer sees it |
|---|---|---|
| 1 | Crop recommendation (N/P/K + weather) | Add planting: recommendation badge, when the field has a soil test |
| 2 | Crop from soil type | Add planting, when there's no soil test but the soil type is known. The only model that can recommend sugarcane. |
| 3 | Fertilizer targets | Ledger → "Nutrient check" card |
| 4b | Disease Q&A (crop-scoped) | Ledger → "Look up a problem" |
| 5b | Soil fertility class | Ledger → "Soil fertility" card, for a field with a full 12-value soil-test card |
| 6 | Yield percentile | Ledger → "Yield outlook" card (band only) |
| 7b | Soil type from photo | Add field → "Identify soil from a photo" |
| 11 | Insect detection (YOLOv8n) | Photo check → Insect pest |
| 12, 13 | Rice, pearl millet disease type (conditional) | Photo check → Leaf disease |
| 14b | Wheat heading detection | Photo check → Heading |
| 17 | Tobacco lesion share | Photo check → Leaf spots |
| 18 | Mandi price outlook / 13-week forecast | Home → "Market prices" (Karnataka users) |
| 20, 21, 22, 24, 26 | Coffee, tea, cauliflower, onion, potato leaf condition | Photo check → Leaf disease |
| 23 | Cauliflower curd condition | Photo check → Curd disease |
| 25 | Onion bulb healthy/unhealthy | Photo check → Bulb |
| 27 | Tomato fruit grade | Photo check → Fruit grade |
| 28 | Wheat kernel sunn-pest damage | **Held**: built but not offered (§4) |

All photo checks live on the ledger screen, under "Crop health & advice".
**Not served:**
- Rejected models 4, 5, 10, 14, 15 and 19 (sugarcane leaf condition, model 10, is refused with a 409 and never offered).
- Model 16, which clears its bar but was trained on synthetic data.

### Coverage by crop

Every entry is derived at request time by `/v1/capabilities` from the model
registries and artifacts; nothing is a hard-coded crop list.

| Crop | Photo checks | Nutrient check | Disease lookup | Yield outlook | Market prices |
|---|---|---|---|---|---|
| Rice | leaf (conditional), insects | yes | yes | yes | paddy outlook + milled-rice forecast |
| Ragi | none | yes | no (no corpus coverage) | yes | outlook only |
| Maize | insects | yes | yes | yes | yes |
| Cotton | insects | yes | yes | yes | yes |
| Sugarcane | none (leaf model rejected) | no target | yes | yes | jaggery outlook only |
| Pearl millet | leaf (conditional) | no target | no | yes | bajra forecast |
| Wheat | heading; kernels **held** | no target | yes | yes | yes |
| Tobacco | leaf spots (lesion share) | no target | no | yes | no series |
| Coffee | leaf (healthy / rust / phoma) | yes | no | no | no |
| Tea | leaf (fresh / Helopeltis / red spider) | no target | no | no | no |
| Cauliflower | leaf; curd (6 classes) | yes | no | no | no |
| Onion | leaf; bulb (healthy / unhealthy) | yes | yes | yes | no |
| Potato | leaf (early/late blight link to remedies) | yes | yes | yes | no |
| Tomato | fruit grade (damaged / old / ripe / unripe) | yes | yes | no | no |

**Soil fertility (5b)** is a property of the field's soil, not of a crop. It
is available on any field, for any crop, once the field has a full 12-value
soil-test card.

Crop recommendations for coffee, onion, potato, tomato and cauliflower link to
real app crops through `crops.ml_key`.

---

## 4. Python sidecar (`ml/serving/`)

| File | Role |
|---|---|
| `app.py` | FastAPI app. The lifespan hook sets torch threads to half the cores and runs the optional `ML_PRELOAD`, which warms every served model; a held model is skipped. |
| `sanitize.py` | `public()`: strips `_`-prefixed keys (yield's `_raw_model_output`), refuses `probability`/`score`/`proba`-like keys, and makes values JSON-safe. **Every response passes through it.** |
| `errors.py` | Maps exceptions to HTTP responses with a machine-readable `reason` (table below). |
| `images.py` | `decode_upload()`: JPEG/PNG magic-byte check, 8 MB and 25 MP caps, `verify()`, EXIF transpose, RGB. Each photo is decoded once. |
| `capabilities.py` | Per-crop availability and the model roster. Reads registries and metrics JSON only, never a torch checkpoint, so it is cheap. |
| `holds.py` | The list of held models (below). |
| `routers/tabular.py` | Models 1, 2, 3, 4b, 5b, 6 |
| `routers/images.py` | Models 7b, 11, 12, 13, 14b, 17, 20-27 (through `/v1/leaf`), 28 (held). A semaphore caps concurrent image inferences at 2. |
| `routers/market.py` | Model 18, plus the district-name mapping (§8). |
| `routers/meta.py` | `/health`, `/v1/models`, `/v1/models/{id}/classes`, `/v1/capabilities` |
| `tests/test_app.py` | pytest tests against the real artifacts (§9) |

### Photo checks: one per part, derived from the registry

`capabilities.py` defines `PHOTO_PARTS`:

- `leaf_diagnosis` ("")
- `curd_diagnosis` (" curd")
- `bulb_diagnosis` (" bulb")
- `fruit_grade` (" fruit")

A part is offered for a crop when `"<crop key><suffix>"` is a key in
`ml/leaf_conditions.py` and that model's `passed_bar` is true. Each entry
carries `conditional` (true only for rice and pearl millet, from
`CONDITIONAL_CROPS`) and `model_key`, e.g. `"cauliflower curd"`.

All four parts are served by `POST /v1/leaf`, with `crop` set to the
`model_key`. A new crop or part added to the registry is served without code
changes.

The other photo checks each have their own capability entry:
- `insect_detection`: host crops rice, maize, cotton and wheat (wheat thrips,
  added 2026-09-26);
- `wheat_heading`;
- `tobacco_lesions`;
- `wheat_kernels`.

### Holding a model (`holds.py`)

```python
HELD = {"wheat_kernels": ("awaiting_lighting_check", "...MODEL_RESULTS.md section 28...")}
```

A held model cleared its bar but is unreachable at every layer:

- **Capabilities:** `/v1/capabilities` reports it as unavailable with reason
  `awaiting_lighting_check`, so the app never shows it.
- **Sidecar:** `POST /v1/wheat-kernels` raises `ModelOnHold` and returns **409
  `model_on_hold`** before the photo is decoded.
- **Node:** `requireCapability` refuses it (409 `awaiting_lighting_check`)
  before anything is stored.
- **Roster:** `/v1/models` lists it as `held`.

**To enable model 28:**

1. Run the lighting check.
2. Record the result in `MODEL_RESULTS.md` §28.
3. Delete its entry from `HELD`.

When it is served, the route appends a caveat the model's own caveats lack:
photo colour alone predicted the label almost as well as the model.

### Error contract

| Condition | Status | `reason` |
|---|---|---|
| Model failed its bar (`ModelDidNotShip`) | 409 | `model_did_not_ship` |
| Model is held (`ModelOnHold`) | 409 | `model_on_hold` (plus `hold_reason`) |
| Bad input (`ValueError`, validation) | 422 | `invalid_input` |
| Not a JPEG/PNG, or cannot be decoded | 422 | `invalid_image` |
| Over 8 MB or 25 MP | 413 | `image_too_large` |
| Artifact missing | 503 | `artifact_missing` |
| Anything else | 500 | `inference_failed` (Node turns this into 503) |

### Endpoints

| Endpoint | Model |
|---|---|
| `POST /v1/crop-recommendation`, `POST /v1/crop-recommendation/soil-type`, `GET /v1/crop-recommendation/soil-types` | 1, 2 |
| `POST /v1/fertilizer` (`{crop, soil_sample?}` or `{crop, state}`) | 3 |
| `GET /v1/disease/search?crop&q`, `/v1/disease/list?crop`, `/v1/disease/detail?crop&disease` | 4b |
| `POST /v1/soil-fertility` (the 12 card values, each optional; a missing value returns 200 `{reason: "missing_values", missing}`) | 5b |
| `POST /v1/yield` (`{crop, season, state, year}`) | 6 |
| `POST /v1/soil-type` | 7b |
| `POST /v1/insects` | 11 |
| `POST /v1/leaf` (`crop` = registry key, `symptom_reported`) | 12, 13, 20-27 (10 refused) |
| `POST /v1/wheat-heading` | 14b |
| `POST /v1/tobacco-lesions` | 17 |
| `POST /v1/wheat-kernels` | 28, **held** |
| `GET /v1/price/commodities`, `/v1/price/outlook?commodity&district` | 18 |

### Additive changes to `ml/algorithms/`

No model was retrained or altered for serving.

| Function | Module | Purpose |
|---|---|---|
| `list_diseases(crop)` | `disease_info_retrieval.py` | Backs the "see all diseases" path required by bar 4b. |
| `disease_detail(crop, disease)` | `disease_info_retrieval.py` | Stable facts plus up to 5 distinct documented remedies. Links a leaf diagnosis to Q&A content. |
| `supported_commodities()` | `price_forecast.py` | Commodity roster, with forecast-shipped flags. |
| `typical_inputs(crop)` | `yield_prediction.py` | Training-period (≤2014) median fertilizer/pesticide rates per crop. |
| `yield_crop_names()` | `yield_prediction.py` | The model's own crop spellings. |

`ml/requirements.txt` pins the serving dependencies: `fastapi`, `uvicorn`,
`python-multipart`, `httpx` and `pytest`. It also pins `ultralytics`, which the
insect detector already used but which was never listed.

---

## 5. Node backend

### Files added for serving

| File | Role |
|---|---|
| `src/services/mlClient.js` | `mlGet` / `mlPost` (15 s timeout) and `mlImage` (multipart, 90 s timeout for the first torch load). Maps sidecar failures: 409 stays 409, 413/422 pass through with the sidecar's `reason`, and unreachable/timeout/5xx become **503 `ml_unavailable`**. Node never returns a 500 for an ML failure. |
| `src/services/mlInputs.js` | Pure mappings, unit-tested: app soil key → model-2 soil vocabulary, soil-photo class → app soil key, sowing date → season, soil-test row → `{N, P, K, pH}`, and soil-test row → the 12-value card plus the names of missing values. |
| `src/services/soilTests.js` | `latestSoilTest(fieldId)`: the one definition of a field's current soil test (ordered by `tested_at DESC, seq DESC`). Used by crop recommendation, the nutrient check and soil fertility. |
| `src/routes/ml.js` | Every app-facing ML route (below). Uses `multer` (memory storage, 8 MB, JPEG/PNG only). |
| `migrations/0003`–`0005` | Schema changes (§6). |
| `scripts/start-ml.js`, `scripts/dev-all.js` | `npm run ml` and `npm run dev:all`. |
| `test/ml.test.js` | A fake sidecar over real sockets (200 / 409 / 422 / 5xx / refused / timeout), plus the pure mappings and soil-test parsing. |
| `test/fixtures/insect.jpg` | CC BY 4.0 RF100 test image used by the smoke test. |

### Routes (`/api/v1/ml`, all require a JWT and ownership)

| Route | Purpose |
|---|---|
| `GET /capabilities?planting_id=` | What this planting's crop can be offered. Cached per crop for 10 minutes. |
| `POST /soil-type` (multipart `photo`, optional `field_id`) | Soil type from photo, mapped to the app soil key (Cinder → `null`, meaning choose manually). |
| `POST /plantings/:id/photo-check` | Photo checks. `kind` is one of `leaf`, `curd`, `bulb`, `fruit_grade`, `insects`, `wheat_heading`, `wheat_kernels`, `tobacco_lesions`. The four leaf-pipeline kinds send the capability's `model_key` to `/v1/leaf` and record `leaf_condition_<model_key>`. An unavailable or held kind is refused with 409 before anything is stored. A conditional check without `symptom_reported` is refused with **422 `symptom_required`**. |
| `GET /plantings/:id/fertilizer` | Latest complete soil test, else the state average. Adds `products` from `agri_catalog`. |
| `GET /plantings/:id/yield-outlook` | Position band plus comparison scope and caveats. `unit: null`. |
| `GET /plantings/:id/diseases?q=`, `/diseases/all`, `/diseases/detail?disease=` | Disease lookup. |
| `GET /fields/:id/soil-fertility` | `no_soil_test`, `incomplete_soil_test` (with `missing` column names), or the class with `provenance_verified: false`. |
| `GET /market/commodities`, `GET /market/outlook?commodity=` | Karnataka only (`karnataka_only` otherwise). Outlook cached for 6 hours. |
| `GET /inferences`, `GET /inferences/:id/image`, `DELETE /inferences/:id` | The farmer's own photo history. Delete removes the file. |

### Changed files

| File | Change |
|---|---|
| `routes/plantings.js` | `GET /recommend-crop` goes through the sidecar and picks its model in order: **soil test → model 1**, else **mappable soil type → model 2**, else **model 1 on generic defaults**. The response adds `basis`, `model` and a per-entry `crop_id` (joined via `crops.ml_key`). `unreachable_seeded_crops` is computed from the class list of the model that actually ran. The old response keys are kept. |
| `routes/fields.js` | `parseSoilTest` handles all 12 soil-card columns and rejects negatives and pH > 14. New `POST /api/v1/fields/:id/soil-tests` adds a soil test to an existing field; before this there was no way to do so after field creation. |
| `routes/users.js` | `photo_training_consent` in `GET` / `PATCH /users/me`. |
| `routes/reference.js` | `ml_key` added to `/catalog/crops`. |
| `errors.js` | `HttpError` can carry extra keys (`reason`) beside `detail`. |
| `scripts/seed-reference-data.js` | Writes `ml_key`, still insert-only. |
| `scripts/smoke-e2e.js` | ML section (§9). |
| `app.js` | Mounts `/api/v1/ml`. |
| `package.json` | Adds `multer`, `npm run ml` and `npm run dev:all`. |

### Deleted files

`backend/src/services/cropRecommendation.js` and
`ml/serve_crop_recommendation.py` (the spawn bridge).

---

## 6. Database

| Migration | Change |
|---|---|
| `0003_ml_serving.sql` | **`crops.ml_key`**: the crop's key in the ML layer (`rice`, `pearl millet`, `cauliflower`, ...). It replaces fragile display-name matching ("Ragi (Finger Millet)" never matched the model's "Ragi").<br>**`users.photo_training_consent`** (default 0).<br>**`ml_inferences`**: one row per model call made on a farmer's behalf. It holds user/field/planting, model id, crop key, `image_path`, `image_sha256`, request and response JSON, `outcome` (`ok`/`refused`/`error`) and a soft-delete column. |
| `0004_soil_test_card.sql` | Eight nullable `soil_tests` columns for the rest of a soil-test card: `ec`, `organic_carbon`, `sulphur`, `zinc`, `iron`, `copper`, `manganese` and `boron`. |
| `0005_soil_test_order.sql` | An auto-increment `seq` tie-breaker (see §8). |

**Consent flag.** Photos are stored for the farmer's own history whatever
`photo_training_consent` is set to. **Nothing reads the flag yet; any future
training export must filter on it.**

**Seeded crops (`reference-data.json`).** There are 14:
- the original five: rice, ragi, maize, cotton, sugarcane;
- added 2026-09-24: pearl millet, wheat, tobacco;
- added 2026-09-26: coffee, tea, cauliflower, onion, potato, tomato.

Each has an `ml_key`. The new ones have no varieties, stages or rules.

**Photo storage.** Photos are stored at
`backend/uploads/ml/YYYY/MM/<uuid>.jpg` (gitignored). Every stored photo has an
`ml_inferences` row. Uploads the sidecar could not decode are not kept, and
neither are uploads for refused or held checks.

---

## 7. Frontend (Expo 54, still Expo Go compatible)

### New dependencies

`expo-image-picker` and `expo-image-manipulator`. The `expo-image-picker`
plugin in `app.json` carries the camera and photo-library permission strings.

Both packages had to be installed with `npm install --legacy-peer-deps`,
because of a pre-existing react-dom peer conflict.

### Infrastructure

| File | Role |
|---|---|
| `lib/apiClient.ts` | Adds `apiUpload()` (multipart, does not set Content-Type so React Native can add the boundary) and `apiErrorReason()`. |
| `lib/photo.ts` | `pickPhoto(camera\|library)`: permission, then pick, then resize to ≤1280 px wide and re-encode as JPEG. Re-encoding also **strips EXIF, including GPS**, before upload. |
| `services/ml.ts` | Typed wrappers and mappers for every route, plus `remedyFor()` (Hindi only when a genuine Hindi text exists) and `mlErrorMessage()`. Leaf-pipeline results share one shape, `kind: "leaf"` with a `part` (`LeafPart`, `isLeafPart`). Results are held in component state; nothing new is persisted, so no store migration was needed. |
| `services/fields.ts` | `addSoilTest()`, and the 12-value soil-test input. |
| `components/SoilTestFields.tsx` | Shared soil-test form: 4 basic values plus an expandable "More values from your soil-test card", with units in every label. |
| `components/ui/ConfidencePill.tsx` | Extracted from `AlertCard`; now shared. |
| `components/ui/CaveatText.tsx` | Muted caveat text. |
| `components/ml/ModelNotice.tsx` | "Computer estimate. Not reviewed by an agricultural expert." |
| `components/ml/PhotoSourceButtons.tsx` | Take photo / choose photo. |
| `components/ml/DetectionOverlay.tsx` | Insect boxes drawn over the photo. |
| `components/ml/PlantingAdvice.tsx` | The "Crop health & advice" section: photo-check and disease buttons, plus the soil fertility, nutrient and yield cards. Refetched on focus, so a newly entered soil-test card updates everything. |

### Screens

| Screen | Change |
|---|---|
| `app/modals/add-field.tsx` | "Identify soil from a photo" prefills the soil picker. Uses `SoilTestFields`. **Fix:** stores the soil *key*, not the translated label, so the backend can use model 2 in any app language. |
| `app/modals/add-soil-test.tsx` (new) | Enter a soil-test card for an existing field. It becomes the field's current test. |
| `app/(tabs)/fields.tsx` | Displays the soil key translated. Legacy free-text values are shown as stored. |
| `app/modals/add-planting.tsx` | Matches by crop id / `mlKey`, shows a confidence pill and a basis line. **Fix:** a variety is required only when the crop has varieties; otherwise the new crops could not be planted. |
| `app/ledger/[plantingId].tsx` | Adds "Crop health & advice". Everything shown there is driven by `/ml/capabilities`. |
| `app/planting/[plantingId]/photo-check.tsx` (new) | Details below. |
| `app/planting/[plantingId]/diseases.tsx` (new) | Symptom search plus the **always-visible full disease list**. Remedies are shown in Hindi or English, with a "shown in English" note. |
| `app/market.tsx` (new) | Commodity chips (own crops first), the forecast block, and monthly **"Historical price range"** bars. No sell/hold advice. |
| `app/photo-history.tsx` (new) | List and delete stored photo checks. Thumbnails load through the authenticated image URL. |
| `app/(tabs)/profile.tsx` | Photo-training consent toggle and a link to photo history. |
| `app/(tabs)/home.tsx` | "Market prices" card. |

The photo-check screen:
- **Chips:** one per available check, in the order leaf, curd, bulb, fruit grade, insects, heading, kernels, leaf spots.
- **Conditional checks** (rice, pearl millet) require an "I can see symptoms" confirmation and offer "None of these match".
- **Fruit grades** show a "Fruit grade" heading, with no remedies link.
- **Unclassified results** (onion "unhealthy", curd "purple tinge") say the cause can't be named, again with no remedies link.
- **Insect results** that link to a rule offer "Log a scouting count", which opens the existing scouting modal. The rule engine then decides on alerts.

### i18n

About 190 new keys across these namespaces: `ml`, `photoCheck`, `diseases`,
`nutrients`, `yieldOutlook`, `market`, `photoHistory`, `soilTest` and
`soilFertility`, plus three in `addPlanting`. All 10 locales have full key
parity.

**The 9 non-English locales were written without a native speaker and need
review. Manipuri (`mni`) is the least reliable.** Crop, disease and pest names
coming from the models stay in English.

---

## 8. Findings made during integration

- **The price model uses pre-rename district names** (Belgaum, Mysore,
  Davangere, Shimoga...). The app stores current names (Belagavi, Mysuru,
  Davanagere...). Unmapped, every Karnataka farmer would have silently received
  state-level prices. `routers/market.py` resolves names with the existing
  `normalize_district` plus four unambiguous aliases (Chamrajnagar, Davangere,
  Kalburgi, Karwar). **Bangalore is deliberately left unresolved**, because it
  could be Bengaluru Urban or Rural, so those farmers get the Karnataka series.
- **Yield uses typical inputs, never logged ones.** `interventions.quantity_unit`
  is free text and the source data's fertilizer/pesticide units are
  undocumented, so converting a farmer's inputs would fabricate a unit. The
  source's per-hectare fertilizer rate is also near-identical across crops
  (127.71 for both rice and bajra); it tracks year, not crop.
- **Commodity ↔ crop matching.** The price artifact predates the new crops
  (bajra had `app_crop: null`). The sidecar returns a `crop_key` per commodity
  (bajra → pearl millet).
- **Insect hosts are only rice, maize and cotton.** Wheat is not offered the
  insect check even though "wheat thrips" is a detector class, because its host
  list is empty and unverified.
- **Soil tests saved in the same second were returned in arbitrary order.**
  `tested_at` is second-precision (naive UTC, by project convention), so
  "latest" could return an older, partial test. That is exactly what happens
  when a farmer corrects a card straight away, and the smoke test caught it.
  Migration 0005 adds `seq`, and all consumers go through `latestSoilTest()`.
  The bug had also affected crop recommendation and the nutrient check.
- **Soil fertility (5b) needs all 12 card values, and missing ones are never
  imputed.** The API names them and the app asks for them. Its labels are an
  exact cut of a nutrient index computed from the same values, so the card
  says it is "the rating a soil lab would give these values", not a fertilizer
  recommendation. It also says the training data's source is unverified.
- **An i18n trap.** Existing keys (`tapToAddNext`, `boundaryClosed`) use
  `{{count}}`; a blanket rename briefly broke them and was reverted. New keys
  avoid `count`, because i18next treats it as a plural trigger.

---

## 9. Verification (latest run: 2026-09-26)

| Check | Result |
|---|---|
| Sidecar pytest (`.venv/Scripts/python.exe -m pytest ml/serving/tests -q`) | **39 passed, 1 skipped**. The skip is the wheat-heading image test, because `datasets/wheat_dataset` is no longer on disk. Covers per-crop capabilities, one real dataset image per leaf-pipeline model, the held kernel model (409 `model_on_hold`), soil fertility and the sanitize guard. Roster: 21 shipped, 1 held. |
| Backend unit tests (`npm test`) | **24/24** |
| End-to-end smoke (`npm run smoke`, dev MySQL, sidecar running) | **78/78**. Covers: recommend-crop basis and labels; capabilities; fertilizer; yield band with no raw number; disease search and full list; market district forecast and paddy outlook-only; soil fertility from no test to partial card to full card; insect photo check; `symptom_required`; unavailable kind → 409; tomato fruit grade; held wheat-kernel upload → 409 with no photo stored; photo history / image / delete; another user's planting → 403. No response contained `probability` or `_raw`. |
| Smoke with the sidecar **stopped** | **49/49**. ML routes return **503 `ml_unavailable`**, never 500. |
| Frontend `tsc --noEmit` / jest / `expo export --platform android` | clean / **30/30** / bundles |
| Real API runs with dataset photos | Wheat heading detected. Tobacco lesion share returned. Pearl millet rust. **Sugarcane leaf → 409.** Coffee healthy, tea fresh, cauliflower Alternaria (leaf and curd), onion healthy (leaf and bulb), potato early blight, tomato damaged. Test users were deleted afterwards. |

**Not yet done:** a manual walkthrough on a device in Expo Go.

The live weather checks in the smoke test depend on Open-Meteo and have been
flaky once, which is unrelated to this work.

---

## 10. Known limits (stated, not fixed)

- **Crop recommendation rainfall.** It still uses current weather
  precipitation, while the training data uses a longer-horizon rainfall figure.
  This was carried over unchanged. Recommendations can therefore look odd
  (e.g. muskmelon), and the model is already documented as trained on
  synthetic, highly separable data.
- **Stale price forecasts.** Forecasts start from the dataset's last week
  (2026-09-21). Refreshing means updating the price data and re-running
  `train_price_forecast`, which is also a fresh verdict on the test fold.
- **Photo models were trained on dataset photos.** Potato is PlantVillage lab
  photos. The cauliflower curd photos are very alike (21% of test images lack a
  close training neighbour). Field accuracy will be lower than measured, and
  every leaf result carries a caveat saying so.
- **Onion checks name no cause.** An "unhealthy" result gives no remedies.
- **Soil fertility provenance is unverified.** The user states the data is
  real but did not disclose its source.
- **Nine crops lack agronomic data.** Pearl millet, wheat, tobacco, coffee,
  tea, cauliflower, onion, potato and tomato have no varieties, stages, rules or
  scouting metrics, so the rule engine never alerts for them.
- **Tea has only its leaf check.** It has no fertilizer target, yield history,
  disease corpus entry or price series.
- **Model 28 stays held** until the lighting check is done (§4).
- **Legacy soil types.** Fields saved before 2026-09-24 in a non-English
  language hold a translated soil label that cannot be mapped, so the
  soil-type model is skipped for them.
- **The consent flag is recorded but unused.** No training export exists yet.
- **Translations** need native review (§7).

---

## 11. Adding another model later

1. **Leaf-pipeline photo model:** add it to `ml/leaf_conditions.py` (a new crop,
   or a new part with a `PHOTO_PARTS` suffix). Capabilities, routing and the UI
   pick it up; add its app crop to `reference-data.json` if needed.
2. **Any other model:** add a sidecar route in `ml/serving/routers/` that
   returns `public(result)`. Then add a capability entry in
   `ml/serving/capabilities.py`, derived from the artifact's bar flag and the
   relevant registry, not a hard-coded crop list.
3. **Needs a check first:** add it to `ml/serving/holds.py` rather than
   leaving it out.
4. **Node route:** add it in `backend/src/routes/ml.js`, going through
   `mlClient`. Store photos through `runImageModel` so the audit trail stays
   complete.
5. **Frontend:** add a mapper in `frontend/.../services/ml.ts` and gate the UI
   on capabilities.
6. **Tests:** extend `ml/serving/tests/test_app.py` and the ML section of
   `scripts/smoke-e2e.js`.

---

## 12. Change history

| Date | Change |
|---|---|
| 2026-09-24 | Sidecar, Node routes and frontend built. 12 models served. Pearl millet, wheat and tobacco added as crops. Migration 0003. |
| 2026-09-25 | **Soil fertility 5b** served: `/v1/soil-fertility`, `/fields/:id/soil-fertility`, `/fields/:id/soil-tests`, the full soil-test card form, and migrations 0004-0005 (the same-second soil-test bug, §8). 13 models served. |
| 2026-09-26 | **Models 20-28**: six new crops, per-part photo checks (`PHOTO_PARTS`), the hold mechanism (`holds.py`), and model 28 held pending the lighting check. 21 models served, 1 held. |
