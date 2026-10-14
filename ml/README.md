# `ml/` — models for the sustainable farming app

Models for the Sustainable Farming app (Chiguru Nele): offline training in
`training/`, inference functions in `algorithms/`, and a FastAPI sidecar in
`serving/` that the Node backend calls. See the [root README](../README.md) for
the system overview.

**Roster at a glance** (metrics and verdicts are in `MODEL_RESULTS.md`; every
model is provisional):

- **22 models ship.** They cover crop recommendation (from N/P/K + weather, and
  from soil type), the fertilizer target lookup, crop-scoped disease Q&A, soil
  fertility (5b; its data's provenance is unverified), yield as a percentile
  band, soil type from photo, insect detection (YOLOv8), leaf-condition
  classifiers (rice, pearl millet, and models 20-27 for coffee, tea,
  cauliflower leaf/curd, onion leaf/bulb, potato and tomato fruit), wheat
  heading, wheat kernel damage (28), tobacco lesion severity, and the Karnataka
  mandi price outlook (forecast for 8 of 13 commodities).
- **21 are served** through `serving/` (see "Serving" below). Wheat kernels
  (28) is held in `serving/holds.py` until a lighting check passes.
- **Six were trained, measured and rejected** (models 4, 5, 10, 14, 15, 19 in
  `MODEL_RESULTS.md`): unscoped disease Q&A, the original soil fertility model
  (5b replaces it), leaf condition for sugarcane, wheat canopy segmentation
  (its heading output alone ships as 14b), soybean seed yield, and the
  vegetable variety/size classifier.
- **Sugarcane yield (16)** clears its bar but is never served: its data is
  synthetic.
- **The rest were never trained** because the data to train them does not exist.

Models 20-28 were added 2026-09-26 and are not yet app crops, except wheat.
Pearl millet, wheat and tobacco were added as app crops earlier (seeded without
varieties, stages or rules), so their models are reachable.

Read in this order:

1. **`MODEL_BARS.md`** — what each model had to achieve, written and committed
   before anything was trained.
2. **`MODEL_RESULTS.md`** — what each one actually achieved, and the ship/hold
   decision.
3. **`PARKED_MODELS.md`** — what was not trained and why.
   **`UNBLOCKING_PARKED_MODELS.md`** — what would concretely unblock each
   one, including which parts the app's own data (scouting logs,
   interventions) could eventually supply and which parts need an external
   source no amount of app usage will produce.
4. `../DATASETS_STATUS.md` §2 — the data-integrity findings that constrain how
   any of these numbers may be presented. Read before trusting a raw value.

## Layout

```
ml/
  paths.py          every dataset and artifact path, resolved once
  labels.py         confidence -> categorical label; model label -> app crop vocabulary
  leaf_conditions.py  leaf-photo classes -> stable key, category, Q&A disease link
  evaluation.py     three-way splits, baselines, bar checking
  features/         preprocessing shared by training AND serving (soil_image, cnn)
  prep/             dataset cleaners (pre-existing, stdlib-only, dormant)
  training/         offline training; parked/ holds what is not in the pipeline
  algorithms/       inference functions; parked/ likewise
  serving/          FastAPI sidecar the Node backend calls (see "Serving")
  artifacts/        build outputs, gitignored
```

## Running it

```bash
python -m venv .venv --system-site-packages
./.venv/Scripts/python.exe -m pip install -r ml/requirements.txt
./.venv/Scripts/python.exe -m pip install torchvision --index-url https://download.pytorch.org/whl/cpu

./.venv/Scripts/python.exe -m ml.training.train_crop_recommendation_model
./.venv/Scripts/python.exe -m ml.training.train_crop_soil_type_model
./.venv/Scripts/python.exe -m ml.training.build_fertilizer_lookup
./.venv/Scripts/python.exe -m ml.training.build_disease_qa_index
./.venv/Scripts/python.exe -m ml.training.train_yield_model
./.venv/Scripts/python.exe -m ml.training.train_soil_type_model   # slowest, trains two candidates
./.venv/Scripts/python.exe -m ml.training.train_soil_fertility_model   # fails its bar, by design

# Leaf condition from photo - one model per crop, ~35 min on CPU
./.venv/Scripts/python.exe -m ml.training.train_leaf_condition_model --crop sugarcane
./.venv/Scripts/python.exe -m ml.training.audit_leaf_scene_leakage --crop sugarcane   # evidence check
./.venv/Scripts/python.exe -m ml.training.train_leaf_condition_model --crop rice   # conditional; ~18 min on an idle CPU
./.venv/Scripts/python.exe -m ml.training.train_leaf_condition_model --crop "pearl millet"   # conditional; ~15 min
./.venv/Scripts/python.exe -m ml.training.train_wheat_segmentation   # ~18 min; fails its bar (cover MAE)
./.venv/Scripts/python.exe -m ml.training.apply_wheat_heading_bar   # bar 14b, heading only; no retraining
./.venv/Scripts/python.exe -m ml.training.train_soybean_yield_model   # seconds; fails its bar
./.venv/Scripts/python.exe -m ml.training.train_sugarcane_synthetic_yield_model   # seconds; synthetic data, never served
./.venv/Scripts/python.exe -m ml.training.train_tobacco_lesion_segmentation   # ~20 min
./.venv/Scripts/python.exe -m ml.training.train_price_forecast   # ~3 min; reads 1.6 GB of price CSVs
./.venv/Scripts/python.exe -m ml.training.train_vegetable_classifier   # ~25 min; fails its bar (label conflicts)
./.venv/Scripts/python.exe -m ml.training.train_soil_fertility_v2_model   # ~1 min; model 5b
# Models 20-27 (leaf pipeline) and 28 (wheat kernels), 2026-09-25/26
./.venv/Scripts/python.exe -m ml.training.calibrate_similarity --crop coffee   # threshold rule, before training
./.venv/Scripts/python.exe -m ml.training.train_leaf_condition_model --crop coffee          # ~11 min
./.venv/Scripts/python.exe -m ml.training.train_leaf_condition_model --crop tea             # ~2 h (35k files)
./.venv/Scripts/python.exe -m ml.training.train_leaf_condition_model --crop cauliflower     # ~3 min
./.venv/Scripts/python.exe -m ml.training.train_leaf_condition_model --crop "cauliflower curd"   # ~5 min
./.venv/Scripts/python.exe -m ml.training.train_leaf_condition_model --crop onion           # ~12 min, capped
./.venv/Scripts/python.exe -m ml.training.train_leaf_condition_model --crop "onion bulb"    # ~10 min, capped
./.venv/Scripts/python.exe -m ml.training.train_leaf_condition_model --crop potato          # ~5 min
./.venv/Scripts/python.exe -m ml.training.train_leaf_condition_model --crop "tomato fruit"  # ~27 min
./.venv/Scripts/python.exe -m ml.training.train_wheat_kernel_damage                          # ~25 min
./.venv/Scripts/python.exe -m ml.training.train_insect_detector --resume            # YOLOv8n+s; ~2-3 h CPU from scratch;
                                                                                  # --resume reuses finished runs
```

Raw datasets are gitignored and are not fetched automatically. `ml/paths.py`
raises with the repo-relative filename if one is missing.

## Four rules that hold across every model here

**1. No probability crosses the API boundary.** Confidence is a categorical
label — `unverified`, `provisional`, `verified` — mapped inside `ml/labels.py`.
`backend/plan/phase4-part2.txt` line 33 directs this: a numeric score "implies
false precision". A forest's 0.87 is the fraction of its trees that voted one
way on synthetic data, not an 87% chance of being right.

No model can promote itself to `verified`. That label means a human domain
expert signed the guidance off, and none of this has been reviewed by anyone.

**2. No model emits prose or product names.** Fertilizer advice returns
structured nutrient deficits; product identity and dosage come from
`agri_catalog` at serving time, where they already live and can be localised.
The app ships 10 locales; English strings baked into a model response are
unlocalisable for all of them.

**3. Yield is a percentile, never a number.** The source column has no unit
that applies across crops (`DATASETS_STATUS.md` §2.1). A bare "2.34" on a
screen will be read as tonnes per hectare regardless of any caveat beside it.

**4. Failing a bar is enforced by code, not by documentation.** Training
records `passed_bar` in every artifact and `ml/algorithms/_loader.py` raises
`ModelDidNotShip` rather than returning one that failed. Serving a rejected
model requires deleting that check — a conversation, not an oversight.

## What this phase changed about the inherited code

`ml/training/` and `ml/algorithms/` began as a contributed tree. The reasoning
in its docstrings was largely sound and has been preserved and extended rather
than replaced. The substantive changes:

- **It did not run.** Every script computed its own `BASE_DIR` and joined
  `"datasets/..."` onto it, assuming a tree inside the package that has never
  existed here. The assumption was not even self-consistent — training and
  serving looked for the same weather file at two different paths. Hence
  `paths.py`.
- **A feature function existed twice.** `extract_features` was duplicated
  byte-for-byte between the soil training script and its serving module, with
  nothing keeping them in step. Now imported from `ml/features/`, with a
  `FEATURE_VERSION` the artifact records so a mismatch raises rather than
  silently mispredicting.
- **Nothing was held out honestly.** Scores were reported on the same fold used
  to make tuning decisions. Every model now has a distinct validation fold and
  a test fold read once.
- **The retrieval index had no evaluation at all.** It built, printed a row
  count, and shipped.
- **Models loaded at import.** Importing one module deserialised 214 MB.
- **`soil_to_crop_bridge.py` was dead code** — it imported `ml.algorithms` from
  a directory named `ml(1)`, which is not a valid Python identifier.

Two inherited defects turned out to matter more than they looked:

- The yield model was **19% worse than a median lookup** despite an R-squared of
  0.95. Between-crop scale differences meant squared error was dominated by
  coconut. Fixed with a log target and an absolute-error objective.
- The soil image directories leak: **19% of training images are near-duplicates
  of test images**, plus heavy duplication within training itself.

## Serving: the sidecar in `ml/serving/`

Built 2026-09-24, once the roster was known. A FastAPI app on
`127.0.0.1:8001` wraps `ml/algorithms/*`; the Node backend
(`backend/src/services/mlClient.js`, `backend/src/routes/ml.js`) is its only
caller and owns auth, ownership, photo storage and the `ml_inferences` audit
table. The sidecar has no database access and binds to localhost only.

```bash
cd backend && npm run dev:all      # API on :8000 and sidecar on :8001 together
cd backend && npm run ml           # sidecar alone; ML_PRELOAD=1 warms every model
./.venv/Scripts/python.exe -m pytest ml/serving/tests -q
```

| Sidecar endpoint | Model |
|---|---|
| `POST /v1/crop-recommendation`, `/v1/crop-recommendation/soil-type` | 1, 2 |
| `POST /v1/fertilizer` | 3 |
| `GET /v1/disease/search`, `/list`, `/detail` | 4b (list = the required "see all" path) |
| `POST /v1/soil-fertility` | 5b (needs all 12 soil-card values; names missing ones) |
| `POST /v1/yield` | 6 (band only; input rates always the crop's training-period medians) |
| `POST /v1/soil-type` | 7b |
| `POST /v1/insects` | 11 |
| `POST /v1/leaf` | 12, 13, 20-27 (`crop` is the registry key: `cauliflower curd`, `onion bulb` and `tomato fruit` are parts); 10 (sugarcane) is refused with 409 |
| `POST /v1/wheat-heading` | 14b |
| `POST /v1/tobacco-lesions` | 17 |
| `POST /v1/wheat-kernels` | 28, **held** in `serving/holds.py` (409 `model_on_hold`) until the lighting check in MODEL_RESULTS §28 |
| `GET /v1/price/commodities`, `/v1/price/outlook` | 18 |
| `GET /health`, `/v1/models`, `/v1/capabilities?crop=` | roster and per-crop availability |

How the four rules above are enforced at the boundary:

- **Rules 1 and 3.** Every response passes through `serving/sanitize.py`,
  which strips `_`-prefixed keys (yield's `_raw_model_output`) and refuses to
  emit any `probability`/`score`-like key.
- **Rule 4.** `ModelDidNotShip` maps to 409 `model_did_not_ship`, never to a
  500 and never to a result. `/v1/capabilities` reads the same `passed_bar`
  flags from metrics JSON, so the app never offers a refused model (the
  sugarcane leaf check does not appear at all).
- **Rule 2.** Unchanged: product names are joined from `agri_catalog` in Node.

Serving-time findings, recorded here because they shaped the integration:

- **The price model spells districts as the market data did** (Belgaum,
  Mysore, Davangere); the app stores current names. `serving/routers/market.py`
  resolves them with `normalize_district` plus four unambiguous aliases.
  Bangalore stays unresolved, so Bengaluru farmers get the Karnataka series.
- **Yield input rates.** `interventions.quantity_unit` is free text and the
  source data's fertilizer/pesticide units are undocumented, so logged inputs
  are never converted. The source's per-hectare fertilizer rate is also
  near-identical across crops (127.71 for both rice and bajra), i.e. it tracks
  year, not crop.
- **Insect hosts are rice, maize and cotton only**, so wheat is not offered
  the insect check even though "wheat thrips" is a detector class: its host
  list is empty and unverified.
