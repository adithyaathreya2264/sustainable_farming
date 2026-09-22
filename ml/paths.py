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
FERTILIZER_TARGETS = ARTIFACTS_DIR / "fertilizer_targets.json"


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
