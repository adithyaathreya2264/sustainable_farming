"""Every dataset and artifact path the ML layer uses, resolved in one place.

## Why this file exists

The inherited training/inference scripts each computed their own
`BASE_DIR = dirname(dirname(__file__))` and then joined `"datasets/..."` onto
it. That assumed a `datasets/` directory living *inside* the ML package, which
has never existed in this repo — the raw data sits at the repo root under
directory names containing spaces (`farm datasets`, `soil datasets`). The
result was that not a single training script would run.

Worse, the assumption was not even internally consistent: the training scripts
looked for `datasets/farm_datasets/state_weather_data_1997_2020.csv` while
`algorithms/yield_prediction.py` looked for the *same file* at a flat
`datasets/state_weather_data_1997_2020.csv`. A model and its serving code
disagreeing about where their shared input lives is the kind of thing that
silently produces two different feature distributions.

So: no module computes a dataset path. They import one from here.

## Two dataset layouts coexist on disk, deliberately

`datasets/` contains the same tabular files twice, under two naming
conventions, and both are load-bearing:

- **Flat, space-separated** (`datasets/farm datasets/crop_yield.csv`) — what
  `ml/prep/*.py` reads. Those cleaners are correct, byte-deterministic and
  already run; repointing them would be churn for no gain.
- **Nested, underscore-separated** (`datasets/datasets/farm_datasets/...`) —
  the tree the inherited training scripts were written against. It arrived one
  directory deeper than intended during the copy, which is the whole reason
  nothing ran.

The duplicates are byte-identical (md5-verified), so which one a given module
reads is a matter of convention, not correctness. Training reads the nested
tree; `ml/prep` keeps its flat paths. Nothing under `datasets/` is moved —
moving it would break the cleaners to save an import.

Paths are resolved but deliberately NOT existence-checked at import time: a
module that only needs the yield CSV should not fail because the soil images
are absent. Use `require()` at the point of use instead.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# --------------------------------------------------------------------------
# Dataset roots
# --------------------------------------------------------------------------

DATASETS_DIR = REPO_ROOT / "datasets"

# The inherited scripts' expected tree, one level deeper than they assumed.
ML_DATASETS = DATASETS_DIR / "datasets"

# --------------------------------------------------------------------------
# Tabular sources
# --------------------------------------------------------------------------

# N/P/K/temperature/humidity/ph/rainfall -> crop. 6,596 rows, 51 classes.
# Note: contains no sugarcane, so crop recommendation can never return one of
# the app's five seeded crops. See MODEL_RESULTS.md.
CROP_RECOMMENDATION_CSV = ML_DATASETS / "crop_datasets" / "merged_crop_dataset.csv"

# Soil type + weather -> crop. 3,100 rows, exactly 100 per crop — that perfect
# balance is a synthetic-generation signature, not a natural distribution.
CROP_SOIL_TYPE_CSV = ML_DATASETS / "crop_datasets" / "crop_soil_type_dataset.csv"

# 12 soil chemistry features -> fertility class 0/1/2. 879 rows, and class 2 is
# only 4.4% (39 samples). Has NO geography column at all, so its relevance to
# any particular region is unverifiable by construction.
SOIL_FERTILITY_CSV = ML_DATASETS / "soil_fertility.csv"

# Crop nutrient targets. Synthetically expanded: 97 crops x ~19 near-duplicate
# rows where N/P/K are constant per crop and only pH is jittered. Read via
# ml/prep/clean_fertilizer_targets.py, which asserts that constancy.
FERTILIZER_CSV = ML_DATASETS / "Fertilizer.csv"

# 19,689 rows, 1997-2020. The `yield` column has no usable unit — see
# DATASETS_STATUS.md 2.1. Never present its values as an absolute figure.
CROP_YIELD_CSV = ML_DATASETS / "farm_datasets" / "crop_yield.csv"

# State climate normals, joined onto crop_yield by (state, year). Coverage ends
# at 2020, which is why any prediction for a later year is an extrapolation.
STATE_WEATHER_CSV = ML_DATASETS / "farm_datasets" / "state_weather_data_1997_2020.csv"
STATE_WEATHER_LAST_YEAR = 2020

# One row per state. Header carries a UTF-8 BOM, so read with encoding="utf-8-sig".
# Values are suspiciously round across all 30 states, reading as hand-authored
# rather than survey-derived.
STATE_SOIL_CSV = ML_DATASETS / "farm_datasets" / "state_soil_data.csv"

# Q&A corpus, not a reference table: 2,231 rows over 88 distinct (crop, disease)
# pairs, ~25 phrasings each. Do not flatten to one row per disease.
DISEASE_QA_CSV = (
    ML_DATASETS / "disease_qa" / "Indian_Crop_Disease_Dataset_Hindi_and_Marathi_NLP.csv"
)

# --------------------------------------------------------------------------
# Image sources
# --------------------------------------------------------------------------

# Note the doubled directory nesting — it is in the source data, not a typo.
_SOIL_IMAGES = DATASETS_DIR / "soil datasets" / "soil datasets(1)"
SOIL_IMAGES_TRAIN = _SOIL_IMAGES / "Soil Train" / "Soil Train"
SOIL_IMAGES_TEST = _SOIL_IMAGES / "Soil Test" / "Soil Test"

# Leaf condition photos, one dataset per crop, supplied 2026-09-23.

# Sugarcane: the class folders sit at uneven depths - diseases are nested one
# level deeper than the dried and healthy folders - so the loader walks for
# leaf directories rather than assuming a fixed layout.
SUGARCANE_LEAF_IMAGES = (
    DATASETS_DIR / "Sugarcane Leaf Image Dataset" / "Sugarcane Leaf Image Dataset"
)

# Rice: supplied 2026-09-23. Four disease classes and NO healthy class, so a
# model trained on it can never answer "this leaf is healthy".
RICE_LEAF_IMAGES = DATASETS_DIR / "rice_leafs_disease"

# Pearl millet (bajra): supplied 2026-09-24 as "millets_dataset". Blast and rust
# come from one camera source (256px, DSC_#### shots, several crops of each);
# its Healthy folder is a different source (640px phone photos, Roboflow
# export) and is excluded - see EXCLUDED_FOLDERS in ml/leaf_conditions.py.
PEARL_MILLET_LEAF_IMAGES = DATASETS_DIR / "millets_dataset"

# Models 20-27, supplied 2026-09-25. One root per task; cauliflower and onion
# each hold two tasks (leaves, and curd or bulb).
COFFEE_LEAF_IMAGES = DATASETS_DIR / "coffee_dataset"
TEA_LEAF_IMAGES = DATASETS_DIR / "tea_leaves_datasets"
_CAULIFLOWER = DATASETS_DIR / "Cauliflower Dataset"
_ONION = DATASETS_DIR / "Red and White Onion Dataset" / "New Onion"
POTATO_LEAF_IMAGES = DATASETS_DIR / "potato_dataset" / "PlantVillage"
TOMATO_FRUIT_IMAGES = DATASETS_DIR / "tomato_dataset"  # train/ and val/ pooled; shipped split leaks

LEAF_IMAGE_ROOTS = {
    "sugarcane": SUGARCANE_LEAF_IMAGES,
    "rice": RICE_LEAF_IMAGES,
    "pearl millet": PEARL_MILLET_LEAF_IMAGES,
    "coffee": COFFEE_LEAF_IMAGES,
    "tea": TEA_LEAF_IMAGES,
    "cauliflower": _CAULIFLOWER / "Leaves Categories",
    "cauliflower curd": _CAULIFLOWER / "Cauliflower Categories",
    "onion": _ONION / "Leaves",
    "onion bulb": _ONION / "Bulb",
    "potato": POTATO_LEAF_IMAGES,
    "tomato fruit": TOMATO_FRUIT_IMAGES,
}

# Wheat kernels (sunn pest damage), model 28. The extracted folders; the .zip
# files beside them hold the same images.
WHEAT_KERNEL_IMAGES = (
    DATASETS_DIR / "Wheat Dataset for Species Classification and Sunn Pest Damage Detection" / "Wheat Dataset"
)

# Insect detection: Roboflow RF100 "insects" v2, YOLOv8 export, CC BY 4.0.
# Ships its own train/valid/test split and data.yaml.
INSECTS_YOLO_ROOT = DATASETS_DIR / "insects.v2-release.yolov8"

# Wheat: GlobalWheat GWFSS v1.0, organ segmentation (background/head/stem/leaf),
# supplied 2026-09-24 as a 40% download. Shipped split train/ and val/, each
# with images/ (512px JPEG) and masks/ (indexed PNG, values 0-3).
WHEAT_SEGMENTATION_ROOT = DATASETS_DIR / "wheat_dataset"

# Soybean: one factorial field experiment (108 unique plots), shipped as a CSV
# in which every row is repeated about 500 times. See MODEL_BARS.md, model 15.
SOYBEAN_CSV = DATASETS_DIR / "soybean_dataset" / "Advanced Soybean Agricultural Dataset.csv"

# Sugarcane farm CSV, supplied 2026-09-24. SYNTHETIC (see MODEL_BARS.md, model
# 16): trained for the record, never served.
SUGARCANE_SYNTHETIC_CSV = DATASETS_DIR / "sugarcane_dataset" / "FINAL_SUGARCANE_DATASET.csv"

# Tobacco: lesion segmentation (binary), a 40% curated subset of a Kaggle set,
# supplied 2026-09-24. Same layout as wheat; metadata CSVs record each tile's
# source path and whether it is real or augmented. See MODEL_BARS.md, model 17.
TOBACCO_SEGMENTATION_ROOT = DATASETS_DIR / "tobacco_dataset"

# Mandi prices: Agmarknet/data.gov.in daily records, 2023-01-01 onward, one
# yearly CSV per year (the daily/ folder holds the same rows). See
# MODEL_BARS.md, model 18.
PRICE_HISTORY_DIR = DATASETS_DIR / "historical_price_dataset"

# Labelled soil tests supplied 2026-09-25 (provenance undisclosed - see
# MODEL_BARS.md, model 5b). The *_ml_ready.csv files are column subsets.
SOIL_TESTS_DIR = DATASETS_DIR / "soil_dataset"
SOIL_TESTS_KARNATAKA_CSV = SOIL_TESTS_DIR / "karnataka_soil_fertility_dataset.csv"
SOIL_TESTS_PAN_INDIA_CSV = SOIL_TESTS_DIR / "pan_india_soil_fertility_dataset.csv"

# Vegetable produce images (Pune), 14 variety/size folders. Labels partly
# corrupted at source - see DATASETS_STATUS.md section 2.16 and MODEL_BARS.md,
# model 19.
VEGETABLE_IMAGES = (
    DATASETS_DIR / "Vegetables Image Dataset for Machine Applications" / "Vegetables Images" / "Vegetables"
)

# --------------------------------------------------------------------------
# Outputs
# --------------------------------------------------------------------------

ARTIFACTS_DIR = REPO_ROOT / "ml" / "artifacts"

CROP_RECOMMENDATION_MODEL = ARTIFACTS_DIR / "crop_recommendation_model.pkl"
CROP_SOIL_TYPE_MODEL = ARTIFACTS_DIR / "crop_soil_type_model.pkl"
SOIL_FERTILITY_MODEL = ARTIFACTS_DIR / "soil_fertility_model.pkl"
SOIL_TYPE_MODEL = ARTIFACTS_DIR / "soil_type_model.pkl"
SOIL_TYPE_CNN_MODEL = ARTIFACTS_DIR / "soil_type_cnn_model.pt"
YIELD_MODEL = ARTIFACTS_DIR / "yield_model.pkl"
YIELD_BENCHMARKS = ARTIFACTS_DIR / "yield_benchmarks.json"
DISEASE_QA_INDEX = ARTIFACTS_DIR / "disease_qa_index.pkl"
WHEAT_SEGMENTATION_MODEL = ARTIFACTS_DIR / "wheat_canopy_segmentation.pt"
SOYBEAN_YIELD_MODEL = ARTIFACTS_DIR / "soybean_yield_model.pkl"
SUGARCANE_SYNTHETIC_YIELD_MODEL = ARTIFACTS_DIR / "sugarcane_synthetic_yield_model.pkl"
TOBACCO_LESION_MODEL = ARTIFACTS_DIR / "tobacco_lesion_segmentation.pt"
PRICE_FORECAST_MODEL = ARTIFACTS_DIR / "price_forecast_model.pkl"
VEGETABLE_CLASSIFIER_MODEL = ARTIFACTS_DIR / "vegetable_classifier.pt"
SOIL_FERTILITY_V2_MODEL = ARTIFACTS_DIR / "soil_fertility_v2_model.pkl"
WHEAT_KERNEL_MODEL = ARTIFACTS_DIR / "wheat_kernel_damage.pt"
FERTILIZER_TARGETS = ARTIFACTS_DIR / "fertilizer_targets.json"

# Pre-resized copies of training photos. Lives under artifacts/ so it is
# gitignored; safe to delete, rebuilt on the next training run.
IMAGE_CACHE_DIR = ARTIFACTS_DIR / "image_cache"


def crop_slug(crop: str) -> str:
    """Filesystem-safe form of a crop key ("pearl millet" -> "pearl_millet")."""
    return crop.replace(" ", "_")


def leaf_condition_model(crop: str) -> Path:
    return ARTIFACTS_DIR / f"leaf_condition_{crop_slug(crop)}.pt"


def require(path: Path) -> Path:
    """Return `path`, or raise with the repo-relative name and a usable hint.

    A bare FileNotFoundError on an absolute Windows path containing spaces is
    genuinely hard to act on, and "nothing runs because of a path" is the exact
    failure this module exists to eliminate.
    """
    if not path.exists():
        try:
            shown = path.relative_to(REPO_ROOT)
        except ValueError:
            shown = path
        raise FileNotFoundError(
            f"Missing required input: {shown}\n"
            f"  Raw datasets are gitignored and are not fetched automatically. "
            f"Confirm the file exists under datasets/ before running this script."
        )
    return path


def ensure_artifacts_dir() -> Path:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    return ARTIFACTS_DIR
