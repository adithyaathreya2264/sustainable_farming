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

### 2.8 Leaf photo dataset: sugarcane (supplied 2026-09-23)

_Added 2026-09-23, during ML training._

A crop-specific leaf dataset, which partly unblocks the disease-from-photo
model parked on 2026-09-22 (`ml/PARKED_MODELS.md` §1):

| Crop | Folder | Images | Classes |
|---|---|---|---|
| Sugarcane | `Sugarcane Leaf Image Dataset/Sugarcane Leaf Image Dataset` | 6,748 | 11, incl. Healthy Leaves and Dried Leaves |

**Sugarcane's class folders sit at uneven depths.** The nine disease folders
are under `Diseases/Diseases/`, while `Dried Leaves` and `Healthy Leaves` are
one level shallower. A loader assuming one layout silently misses classes.

**The dataset contains the same photograph filed under two different
labels.** Measured with a flip- and rotation-invariant hash, then confirmed
pixel by pixel (mean difference under 5/255 after best alignment):

**294 duplicate groups, 614 images (9.1% of the dataset)** carry conflicting
labels. The largest overlaps are Pokkah Boeng / smut (95 groups) and Banded
Chlorosis / BrownRust (64). There are also Healthy / Viral Disease pairs. More
broadly, the 6,748 images are only 5,610 distinct photographs.

One photo cannot be of two conditions, and nothing in the data says which
label is right, so every conflicting group is excluded from training and
evaluation. The Healthy ↔ disease pairs are the most consequential: kept, they
would train the model to call a diseased leaf healthy.

**What this implies about the rest of the sugarcane labels.** When 95
identical photos are filed as both Pokkah Boeng and smut, it is likely that one
folder was partly filled from the other. Removing the exact duplicates cannot
detect *non-duplicate* images that were misfiled the same way. The test
labels may carry some of that noise, which would cap measured accuracy on
those classes — a limit of the data, not necessarily of the model.

**A hash alone is not enough here.** Leaf photos are uniform (a green leaf,
centred, similar backgrounds), so even a 256-bit hash matched 23 pairs of
genuinely different photographs. Grouping on the hash alone would have
wrongly discarded 105 good images as "conflicts". Duplicates must be confirmed
at pixel level.

**The dataset is a few hundred capture sessions, not thousands of
independent photos.** Every image carries an EXIF capture time, and each class
was shot in continuous streams, frames seconds apart. Grouping images of one
class taken within 10 seconds of each other, 5,316 distinct photos form **216**
independent sessions (8 to 51 per class).

Frames of one session share leaf, light, background and camera settings. **Any
split of this dataset must be made by capture session.** Splitting by photo
lets a model score by recognising the session instead of the condition. This
was measured, not assumed: split by photo, the model scored 0.98 macro-F1;
split by session, it fell to 0.52 (`ml/MODEL_RESULTS.md` §10). 78% of test
images had their most similar training image within three filenames of them.

---

### 2.9 Rice leaf disease and insect detection datasets (supplied 2026-09-23)

_Added 2026-09-23, during ML training._

**`datasets/rice_leafs_disease`** — 5,932 JPGs, mostly 300x300, four disease
classes (Bacterial blight 1,584, Blast 1,440, Brown spot 1,600, Tungro 1,308).

- **No healthy class.** A model trained on it names one of four diseases for
  any rice leaf, so it can only be used conditionally, after a symptom has
  been reported (`ml/MODEL_BARS.md`, model 12).
- **Heavily pre-augmented.** The flip/rotation hash with pixel verification
  reduces 5,932 images to 1,094 distinct photos. Similarity grouping then
  finds brightened, zoomed and recropped copies on top of that: at a
  similarity of 0.93, comparing every image, the data is **302 independent
  groups**, about 5% of its file count. No near-copy pair crosses a disease
  label.
- **Almost no capture metadata** (about 7% of sampled images carry an EXIF
  time), so a session split is not possible.
- All four classes map to Q&A corpus diseases (Bacterial Leaf Blight, Rice
  Blast, Brown Spot, Rice Tungro).

**`datasets/insects.v2-release.yolov8`** — Roboflow RF100 "insects" v2, YOLOv8
export, **CC BY 4.0**. That is the first dataset in this folder with a recorded
licence. 995 images, 10 classes, shipped split 696 / 199 / 100.

- **224x224 tight crops, a median of one insect each, and no insect-free
  images.** It is an identification set in detection format; it does not
  resemble a field photo.
- **16 photos appear in two shipped splits** (pixel-verified; 11 train/valid,
  4 train/test, 1 valid/test). None of the pairs has conflicting labels.
- **Filenames do not identify source images.** `100_jpg.rf.<hash>` appears under
  five different classes, because merged class folders each had their own
  `100.jpg`.
- No EXIF. Nine of the ten classes are pests of the app's crops; legume
  blister beetle is not. Wheat phloeothrips joined on 2026-09-26, when wheat
  became an app crop.
- Test instances per class run 5 to 17, so per-class metrics are coarse.

---

### 2.10 Pearl millet leaf disease dataset (supplied 2026-09-24)

_Added 2026-09-24, during ML training._

**`datasets/millets_dataset`**: three folders, blast 2,926, rust 2,059 and
Healthy 1,326 (no licence recorded).

- **It is pearl millet (bajra), not finger millet (ragi).** The leaves are broad
  with a midrib, and the classes are pearl millet's two classic leaf diseases.
  Confirmed with the user on 2026-09-24. It does **not** unblock a ragi leaf
  model; ragi still has no leaf dataset.
- **Healthy is a different source from the diseases.**

  | | Blast and rust | Healthy |
  |---|---|---|
  | Image size | 256x256 | 640x640 |
  | Framing | one leaf across a background | close, full-frame leaves |
  | Origin | camera `DSC_####` shots | phone and WhatsApp photos, dated Aug-Sep 2021, from a Roboflow export |

  Healthy's 1,326 files are about 502 photos with Roboflow augmentations. Any
  healthy-vs-disease model trained on this folder could learn the source
  instead of the condition, so Healthy is excluded from training.
- **The disease folders are mostly crops and bursts of the same shots.**
  - Each `DSC_####` number appears as up to four crops (`normal0` to `normal3`).
    4,985 files are 2,002 distinct shots.
  - Consecutive shot numbers are bursts of the same leaf: median similarity
    0.95, against 0.69 for distant shots.
  - Linking consecutive shots gives only **84 independent sessions**, 45 blast
    and 39 rust.
- **No EXIF** in any image, so shot numbers are the only session signal.

### 2.11 Wheat canopy segmentation dataset (supplied 2026-09-24)

_Added 2026-09-24, during ML training._

**`datasets/wheat_dataset`**: GlobalWheat **GWFSS v1.0**, organ segmentation.
The files are 512x512 top-down canopy JPEGs with indexed PNG masks (0
background, 1 head, 2 stem, 3 leaf), plus `classes.json`,
`dataset_summary.json` and per-split metadata CSVs with pixel counts.

- **Partial download: 438 of 1,096 images (40%)**, per its own
  `dataset_summary.json`. The shipped split is 350 train and 88 val.
- **Not a disease dataset.** It supports growth-stage (heading) and canopy-cover
  signals only. Wheat is not a seeded app crop.
- **Clean with respect to near-copies.** No EXIF or site metadata.
  - Val-to-train nearest similarity has median 0.85, with none at >= 0.97.
  - Only 4 train images reach >= 0.93 to a val image.
  - Within train there is a single link at 0.93.
- **Class balance** (train pixels): leaf 58%, background 27%, head 11%, stem
  3.5%. 68 of 350 train images have no head pixels.

### 2.12 Soybean agricultural dataset (supplied 2026-09-24)

_Added 2026-09-24, during ML training._

**`datasets/soybean_dataset/Advanced Soybean Agricultural Dataset.csv`**: 55,450
rows, 15 columns (a `Parameters` code, a replicate `Random`, and 13 plant
traits including seed yield).

- **Only 108 unique rows.** Every row is repeated about 500 times. Any model or
  statistic computed on the raw file counts each plot about 500 times, and a
  random split puts copies on both sides.
- **One factorial field experiment, not farm data.** `C#S#G#` means 2
  conditions x 3 treatments x 6 genotypes, with 35 combinations present and 3
  replicates. None of the codes is documented, so the genotypes and treatments
  are anonymous.
- **The features are lab-only or post-harvest.** Chlorophyll a and b, sugars,
  protein and leaf water content need a lab. Pods, seeds per pod, seed weight
  and biomass exist only after harvest.
- **Yield is mostly treatment, not traits.** 93% of its variance lies between
  treatment codes, and it correlates only 0.57 with pods x seeds per pod x seed
  weight.
- **The yield unit is not stated.** Soybean is not an app crop.

Model 15 (`ml/MODEL_RESULTS.md` §15) fails on this data.

### 2.13 Sugarcane farm CSV — synthetic (supplied 2026-09-24)

_Added 2026-09-24, during ML training._

**`datasets/sugarcane_dataset/FINAL_SUGARCANE_DATASET.csv`**: 3,000 rows and
81 columns covering weather, soil, irrigation, management, crop traits,
location (Haridwar district, one sugar mill) and yield in quintals per acre,
2018-2024. Despite its farm-record appearance, **it is generated, not
collected.**

- **Weather does not follow the seasons.** Monthly rainfall averages about
  1,400 mm in every month, including December and January.
- **Soil texture is impossible.** Sand + silt + clay ranges from 13.5% to 136%
  instead of summing to 100.
- **Dates contradict each other.** `Crop_Duration_Days` disagrees with the
  planting and harvest dates, for example 104 days between the dates against a
  stated 255, and 3.4 years against 288.
- **The categories look generated.** Three varieties, four soil types, three
  irrigation methods and every other category are near-perfectly uniform.
- **Missing values look injected.** About 4% are missing in every column,
  independently.
- **Yield follows a few rules.** It depends on nitrogen (r = 0.47), potassium
  and disease severity (low 351, medium 293, high 195 q/acre). Variety, soil,
  irrigation, season and growth stage have no effect. A linear model recovers
  it with R-squared 0.89.

It must not be used as evidence about sugarcane: not for model training that
is served, and not for statistics shown to users. It is the second synthetic
dataset in this folder, after `Fertilizer.csv`. Model 16
(`ml/MODEL_RESULTS.md` §16) was trained on it for the record and is never
served.

### 2.14 Tobacco leaf lesion segmentation dataset (supplied 2026-09-24)

_Added 2026-09-24, during ML training._

**`datasets/tobacco_dataset`**: a curated 40% subset of Kaggle "Dataset for
Tobacco Leaf Disease Segmentation". It has 1,400 800x800 PNG tiles with binary
masks (0 background/healthy, 1 lesion) and a shipped split of 1,120 / 280. Its
metadata CSVs record each tile's source path and whether it is real or
augmented.

- **Lesions are small:** about 2% of pixels on average, 0-18% per tile. No
  disease is named.
- **Only 320 tiles are real,** cut from **84 photos** taken on 14-15 October
  2023 (the timestamp is in the name, e.g. `IMG_20231015_110523_7`). In the
  shipped split, **34 photos have tiles on both sides**, so it leaks.
- **1,080 tiles (77%) are augmented**, with no source recorded.
  - The 540 in `data1/` derive from the real tiles: nearest real tile at
    median similarity 0.90, against 0.66 between tiles of different photos.
  - The 540 in `data2/` derive from originals **not included** here.
- **Use:** evaluate on real tiles only, split by capture session, and keep each
  augmented tile on the side of its source. Model 17 does this
  (`ml/MODEL_RESULTS.md` §17).

### 2.15 Historical mandi prices (supplied 2026-09-24)

_Added 2026-09-24, during ML training._

**`datasets/historical_price_dataset`**: Agmarknet/data.gov.in daily prices. It
holds 1,381 daily CSVs plus yearly files, `market_prices_<year>.csv`, which
contain exactly the same rows. About 8.87 million rows (1.6 GB) cover
**2023-01-01 to 2026-09-24 continuously**, plus an isolated 13 days of 2020.
The columns are date, state, district, market, commodity, variety, grade and
the min/max/modal price in Rs/quintal. There are 72 commodities in 7,374
markets across 34 states. This replaces the single-day
`market datasets(1)/csv` as the price source.

- **Defects:**
  - 168,502 duplicate market-day-commodity-variety-grade rows;
  - 4,547 rows with min > max;
  - 20,435 rows with the modal outside [min, max];
  - unit or typo outliers, such as rice at Rs 61,899 against a median of
    Rs 3,250.
- **Karnataka coverage for the app's crops.**
  - Individual markets report sparsely; few report on even 300 of 1,206 days.
  - A statewide weekly series is near-continuous for rice, maize, cotton and
    jaggery (174-187 of 196 weeks).
  - Paddy and ragi have 139-140 weeks, because they are traded only after
    harvest.
- **Sugarcane is essentially absent** (365 rows nationally, none in Karnataka).
  It is sold to mills at the FRP, not in mandis. Jaggery is the nearest mandi
  proxy.
- **"Rice" is milled rice.** Paddy is a separate commodity.

### 2.16 Vegetable produce images — labels corrupted at source (supplied 2026-09-24)

_Added 2026-09-24, during ML training._

**`datasets/Vegetables Image Dataset for Machine Applications`** contains
harvested-produce photos from Pune: 6 vegetables in 14 folders. Chilli has 3
varieties, although the published description says 13 classes. There are
22,804 512x512 JPEGs, shot on 2025-04-06, of single items on white sheets and
often beside a ruler. The folder names say `-aug`, meaning augmented copies. It
is a produce-grading set, not a crop-health set, and none of these vegetables is
an app crop. The user confirmed on 2026-09-24 that this is the original source.

**The labels are corrupted, in the source itself.**

- The 22,804 files are only **12,519 distinct**.
- **6,368 byte-identical files sit in more than one class folder**, including
  across vegetable types. The same tomato photos are filed under Okra Long, Okra
  Short, Tomato Gaavran and Tomato Regular, and some also under Potato medium
  and small. Chilli photos sit in all three chilli varieties.
- **Share of each folder's files that also appear in another class:**
  - 99-100%: Tomato Regular, Tomato Gaavran, Okra Short, Potato small, Beans
    Long, Chili Sitara, Chili Jipoor;
  - 77-82%: Okra Long, Chili Jwala;
  - 49-51%: Beans Short, Potato medium;
  - **0%**: only Cucumber Gaavran, Cucumber Regular and Potato Large.
- **Uncontradicted distinct files per class:**

  | Class | Files |
  |---|---|
  | Tomato Regular | **0** |
  | Chili Sitara | 7 |
  | Beans Long | 10 |
  | Chili Jipoor | 13 |
  | Potato small | 13 |
  | Okra Short | 15 |
  | Tomato Gaavran | 16 |
  | Chili Jwala | 344 |
  | Okra Long | 879 |
  | Potato medium | 938 |
  | Potato Large | 955 |
  | Cucumber Regular | 978 |
  | Beans Short | 990 |
  | Cucumber Gaavran | 993 |

**Consequence.** The variety or size of a contradicted file cannot be
recovered, so **the published 13-class task cannot be trained or measured
honestly from this data**. Any accuracy reported on it is partly accuracy on
wrong labels. Only cucumber variety (Regular vs Gaavran) is fully clean.

### 2.17 Labelled soil tests, Karnataka and pan-India (supplied 2026-09-25)

_Added 2026-09-25, during ML training._

**`datasets/soil_dataset/`** now holds four files (the earlier KVK Bareilly
files, which were unlabelled, were replaced):

- `karnataka_soil_fertility_dataset.csv`: 1,831 rows, 1,500 fields, 12
  districts, sampled 2022-2024.
- `pan_india_soil_fertility_dataset.csv`: 3,805 rows, 10 states, 819 in
  Karnataka.
- `soil_12_features_ml_ready.csv` and `pan_india_soil_12_features_ml_ready.csv`:
  column subsets of the two above.

The two full files share no sample, field or nutrient row. Their columns are
IDs, state, district, taluk, village, GPS, agro-climatic zone, soil type,
previous crop, date, season, the 12 soil-test values, `Fertility_Index`,
`Fertility_Class` and `Lab_Source`.

- **The label is a formula.** `Fertility_Class` is `Fertility_Index` cut at
  1.70 and 2.35, identically in both files, and the index is computed from the
  nutrients.
- **Provenance is undisclosed.** The user states the data is real.
  - Against: the files were created minutes after a message specifying this
    column set; N and OC correlate at 0.90; a few rows share exact P, Fe and Mn
    values across states.
  - For: the coordinates sit inside their districts, and fields are re-tested
    across years.
- **Not merged with `soil_fertility.csv`**, whose 0/1/2 labels follow a
  different, undocumented scheme.

Used by model 5b (`ml/MODEL_RESULTS.md` §5b).

### 2.18 Seven image datasets supplied 2026-09-25 (coffee, tea, cauliflower, onion, potato, tomato, wheat kernels)

_Added 2026-09-26, after ML training._ The figures were measured at pixel or
byte level, not inferred from file names.

| Folder | What it is | Measured |
|---|---|---|
| `coffee_dataset` | leaves: Health / leaf rust / phoma, 256 px | 3,322 files: **102 empty (0-byte)**; of the 3,220 real files, 1,809 distinct contents. 437 images are stored 2-24 times under different names. 1 content is filed as both rust and phoma. File-name prefixes (1, 1200, 2300) are class codes, not source ids |
| `tea_leaves_datasets` | leaves: Fresh / Helopeltis / Red Spider | 35,299 files: every `IMG_####` photo has 11 files (`_result` plus blur 3-9, noise 2/4 %, grey, binary, rotate +-15; the 3x3 blur differs from the original by 1/255). 3,097 source photos. 1,221 are `.heic` at 300x450, in Fresh and Red Spider only, and need `pillow-heif`. EXIF present |
| `Cauliflower Dataset` | two tasks: curd (6 classes) and leaves (3) | 2,677 files, 48 byte duplicates, mixed sizes and formats. Curd photos are highly alike (median same-class similarity 0.795). Curd Alternaria has 45 images |
| `Red and White Onion Dataset` | two tasks: bulbs (healthy/unhealthy; red/white; single/multiple; Mixed ratio folders) and leaves (healthy/unhealthy) | 24,000 files, all distinct, EXIF on all. "Unhealthy" names no cause |
| `potato_dataset` | Kaggle `arajmishra/potato-dataset` (PlantVillage): early blight / late blight / healthy | 2,152 distinct files, **healthy only 152**. Lab photos |
| `tomato_dataset` | Kaggle `enalis/tomatoes-dataset`: fruit Damaged / Old / Ripe / Unripe | 7,226 files; each image is saved as .jpg and .png under one stem. **The shipped train/val split leaks** (13 identical files cross it) |
| `Wheat Dataset for Species Classification and Sunn Pest Damage Detection` | grain heaps, 6 Turkish cultivars, damaged / healthy | 170 PNGs at 5184x2920; the zips repeat the extracted folders. **Average photo colour alone separates damaged from healthy at 0.94-0.96** |

Trained as models 20-28 (`ml/MODEL_RESULTS.md` §20-28). None of these crops is
an app crop except wheat.

Also noted 2026-09-26: the sugarcane leaf image folder (`Sugarcane Leaf Image
Dataset`) is **no longer in `datasets/`**. The model 10 result stands, but it
cannot be re-audited.

## 3. Reading order for whoever picks up the training work next

1. `datasets/README.md` — what each dataset is and what limits it
2. `ml/prep/common.py` — the vocabulary reconciliation everything depends on
3. This file, §2 — the integrity findings above, before trusting any raw number
