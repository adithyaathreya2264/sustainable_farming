# Datasets Integration — State of Play

_Date: 2026-09-04, backend/MySQL integration built. **2026-09-21: that
integration reverted** — MySQL is app-data-only now; see §0._

This is a factual status document, not a design doc. Companion to
`STATE_OF_THE_SYSTEM.md` — that file describes the app baseline; this one
covers only the dataset work.

---

## 0. 2026-09-21 revert — read this first

The backend/MySQL half of this work (models, Alembic migration, seeder,
services, and the 8 `/api/v1/yield-benchmark` / `/soil-nutrients` /
`/fertilizer-advice` / `/market/*` / `/advisory/*` endpoints) has been
**removed**. Nothing in the frontend ever called any of it (confirmed at
removal time), so nothing else was affected.

**Current state:** the datasets stay exactly where they always were — plain
CSVs under `datasets/` (gitignored, ~139 MB, see `datasets/README.md`).
`ml/prep/*.py` still exists and still works as a dev-time cleaning step
(`python -m ml.prep.run_all` -> cleaned JSON under
`backend/scripts/seed_data/`), kept as dormant groundwork for later — but
its output is no longer read by anything; the app currently has zero
runtime dependency on `datasets/`. MySQL holds only real app data (users,
fields, plantings, interventions, alerts, ...).

**What's deleted:** `backend/models/{state_baseline,yield_benchmark,
crop_nutrient_target,market_price,crop_disease}.py`; the
`5e695dbcd25d_add_dataset_reference_tables` migration is reversed by
`c4a1e7b6f2d3_drop_dataset_reference_tables` (drops all 7 tables);
`backend/scripts/seed_datasets.py`; `backend/services/{yield_benchmark,
fertilizer_advice,market_prices,disease_advisory}.py` and
`soil_lookup.get_soil_nutrients()` (its `get_soil_type()` placeholder
lookup, a separate pre-existing feature, is untouched);
`backend/schemas/{agronomy,market,advisory}.py`;
`backend/api/v1/{agronomy,market,advisory}.py`; the 8 generated
`backend/scripts/seed_data/*.json` artifacts (everything except
`locations.json`, which is unrelated hand-curated data).

**Why:** consuming these datasets is being redone later via ML training
against the raw CSVs directly, not via a MySQL reference-table layer. When
that work starts, sections 1 and 4 below (the pipeline shape and the
data-integrity findings) are still the relevant starting point — they
describe the CSVs themselves, which haven't changed.

---

## 1. The dataset-cleaning step (still present, dev-time only)

```
datasets/*                    raw, third-party, gitignored (~139 MB)
   |
   |  python -m ml.prep.run_all          stdlib only, deterministic
   v
backend/scripts/seed_data/*.json         cleaned, reviewable — NOT read by the app
```

The cleaners use only `csv`, `json`, `statistics` and `hashlib` — no pandas,
no new dependency. Re-running is safe and byte-deterministic. This step is
no longer wired to anything downstream (no seeder, no MySQL, no API) — it's
kept only because it's correct, reusable groundwork for whatever consumes
the datasets next (per the plan, that's a future ML-training path, not a
reference-table API).

| File | Role |
|---|---|
| `ml/prep/common.py` | Crop / state / district / season reconciliation. The reference for all four vocabularies. |
| `ml/prep/clean_state_soil.py` | state soil baselines (30 states) |
| `ml/prep/clean_state_climate.py` | state climate normals (30 states) |
| `ml/prep/clean_fertilizer_targets.py` | crop nutrient targets (97 crops) |
| `ml/prep/clean_crop_yield.py` | crop yield benchmarks (2,131 bands) + meta |
| `ml/prep/clean_market_prices.py` | market price listings (2,224) + meta |
| `ml/prep/clean_crop_diseases.py` | crop diseases (88) + symptom/remedy rows (2,140) |
| `ml/prep/run_all.py` | Runs all six in order |

**2026-09-22 update: this is no longer true.** `ml/training/`,
`ml/algorithms/` and `ml/artifacts/` now exist and six models are trained. See
`ml/MODEL_BARS.md` (acceptance thresholds, written before training),
`ml/MODEL_RESULTS.md` (measured outcomes) and `ml/PARKED_MODELS.md` (what was
not trained and why). The cleaners in `ml/prep/` are unchanged and still
dormant, but `ml/prep/common.py` is now load-bearing again: it supplies the
crop vocabulary every model's output is mapped through.

Two findings from that work belong in this document and are recorded below:
§2.3b (68 questions span multiple crop/disease pairs) and §2.7 (the soil image
directories contain heavy duplication across the train/test boundary).

---

## 2. Data-integrity findings that still matter

These were established by checking, not assumed, and describe the raw CSVs
themselves — still true regardless of how the data eventually gets consumed.

### 2.1 The yield column has no usable unit

`crop_yield.csv`'s `yield` column is **not** production divided by area
(recomputing disagrees in 13,663 of 19,689 rows, 69%), and its scale is
crop-dependent (median 8,466 for Coconut, 53 for Sugarcane, 2.2 for Rice).
Within one crop the values are consistent, so the data supports a
**relative** comparison (percentile within a crop's own distribution), never
an absolute figure with a unit attached. **Do not "improve" this by adding a
unit.**

### 2.2 Fertilizer.csv is synthetically expanded

97 crops times ~19 near-duplicate rows; N/P/K identical within a crop, only
pH jittered. Collapses to one row per crop by median pH — and the N/P/K
constancy should be asserted, not assumed, when this is next consumed (doing
so previously caught two real crop-alias bugs: Coriander leaves vs seeds,
Mustard seeds vs Rapeseed).

### 2.3 The disease CSV is a Q&A corpus, not a reference table

2,231 rows over only 88 distinct (crop, disease) pairs — about 25 phrasings
per disease, each with its own remedy/severity/season/plant-part/state.
`cause` and `disease_type` are the only fields constant within a pair.
Flattening to one row per disease would mean picking one arbitrary remedy
out of ~25 and discarding the rest.

### 2.3b 68 questions belong to more than one crop/disease pair

_Added 2026-09-22, during ML training._

68 distinct `question_en` strings — 137 rows, **6.1% of the corpus** — are
recorded against more than one (crop, disease) pair. Examples:

- identical bacterial-ooze text under both `Tomato / Bacterial Wilt` and
  `sugarcane / Grassy Shoot Disease`
- identical boll-and-fibre text under both `cotton / Pink Bollworm Blight` and
  `sugarcane / Leaf Scald`

This was **verified not to be a bug in the reading code**: the raw CSV really
does carry these assignments, and a direct row-by-row check confirmed zero
mispairing in the long-form transformation used to build the retrieval index.

**These are not treated as mislabellings with a knowable correct answer.** Some
are genuine shared symptomatology — bacterial wilt does present alike across
crops — and there is no basis in this data for declaring either label wrong. So
the rows are kept, not deleted, and the retrieval layer surfaces all matching
pairs together flagged as a shared symptom rather than silently resolving to
one.

Consequence: this is a hard ceiling on exact-pair retrieval accuracy. Anything
built on this corpus should expect it and report it rather than tuning against
it.

### 2.4 The market data is a single stale day

Every row carries arrival date 2019-03-04. No trend, average or
direction-of-travel claim can be drawn from one day of data.

### 2.5 Provenance of the whole folder is undocumented

Upstream sources are unrecorded and licences unverified — anything built on
this data needs to carry an unverified/low-confidence caveat, matching the
pattern `services/rule_engine.py` established elsewhere in this codebase.

### 2.6 Known data gaps

- No Sugarcane nutrient target — Fertilizer.csv has no Sugarcane row.
- Disease corpus covers 4 of 5 seeded crops (rice, maize, cotton, sugarcane) — no ragi.
- Only en/hi/mr text exists in the disease corpus; the app has 10 locales.
- Two market districts (Karnataka/Bangalore, UP/Kanpur) couldn't be resolved to a canonical district without guessing — see `ml/prep/common.py`'s `_DISTRICT_ALIASES` comment.

### 2.7 The soil image split leaks, badly

_Added 2026-09-22, during ML training._

`datasets/soil datasets/soil datasets(1)/` ships a pre-made Soil Train / Soil
Test split. **That split does not hold.**

- **56 of 295 training images (19%) are near-duplicates of test images.**
- The training directory duplicates itself heavily too: the 239 images
  remaining after the above removal are only **183 distinct photographs**.

Measured with an 8x8 average hash, so this catches resized and recompressed
copies of the same photo, not merely byte-identical files.

Anything trained on this directory must deduplicate across the split first, and
must group duplicates when carving a validation fold, or the reported accuracy
is partly a memory test. Concretely: taking the shipped split at face value
gave a validation accuracy of exactly 1.0000 and inflated test accuracy by
about 4 points for the classical model.

---

## 3. Reading order for whoever picks up the training work next

1. `datasets/README.md` — what each dataset is and what limits it
2. `ml/prep/common.py` — the vocabulary reconciliation everything depends on
3. This file, §2 — the integrity findings above, before trusting any raw number
