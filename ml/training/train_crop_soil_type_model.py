"""Soil type + weather -> crop. Random Forest over 3,100 rows and 31 classes.

Run:  python -m ml.training.train_crop_soil_type_model

## What changed from the inherited version, and why

1. **Three-way split** — the original scored on the fold it had already used to
   judge the model. Test is now touched once.

2. **`soil_type_vocab` is computed on the training split only.** The original
   saved `sorted(df["Soil type"].unique())` over the *entire* dataframe, so the
   artifact's advertised vocabulary included categories the model may never
   have been fitted on. The encoder itself was always fitted correctly inside
   the Pipeline, so this was metadata rather than a scoring leak — but the
   metadata is what a caller consults to decide "does this model know my soil
   type?", and that answer was wrong.

3. **Bar is macro-F1**, which is a fair average here precisely because the
   classes are exactly balanced — unlike the N/P/K model, where they are not.

## The vocabulary mismatch with the photo classifier

Kept verbatim from the inherited docstring, because it is still true and still
the main limit on the "photograph your soil" feature:

    train_soil_type_model.py (the photo-based one) only recognizes 4 classes:
    Alluvial, Black, Cinder, Red. This dataset's "Soil type" column has 26
    distinct values after cleaning (Sandy loam, Laterite, Clay loam, Arid and
    Desert, ...), only 3 of which (Alluvial/Red/Black) overlap with the image
    classifier's vocabulary, and none of which is "Cinder".

`soil_to_crop_bridge.py` maps the three that map and fails loudly on Cinder
rather than substituting a "close enough" soil type the model never saw.

## Exactly 100 rows per class, across 31 classes

Real crop distributions are not uniform. That balance is a synthetic-generation
signature, and it means a strong macro-F1 here overstates what this would do on
observed data. Reported with that caveat; ships provisional.
"""

from __future__ import annotations

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, f1_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from ml import paths
from ml.evaluation import Report, majority_class_baseline, three_way_split

CATEGORICAL = ["Soil type"]
NUMERIC = ["temperature", "humidity", "ph", "rainfall"]
TARGET = "label"

# Bar from MODEL_BARS.md section 2.
BAR_MACRO_F1 = 0.75


def main() -> None:
    df = pd.read_csv(paths.require(paths.CROP_SOIL_TYPE_CSV))
    df["Soil type"] = df["Soil type"].str.strip()

    X, y = df[CATEGORICAL + NUMERIC], df[TARGET]
    report = Report("Crop-from-soil-type")

    split = three_way_split(X, y)
    print(f"Split: {split.strategy}  ({split.sizes()})")
    print(f"{y.nunique()} crops, {df['Soil type'].nunique()} soil-type categories")

    preprocessor = ColumnTransformer(
        [("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL)],
        remainder="passthrough",
    )
    model = Pipeline(
        [
            ("preprocess", preprocessor),
            ("classifier", RandomForestClassifier(n_estimators=300, random_state=42, n_jobs=-1)),
        ]
    )
    model.fit(split.X_train, split.y_train)

    val_pred = model.predict(split.X_val)
    val_f1 = f1_score(split.y_val, val_pred, average="macro", zero_division=0)
    print(f"\nValidation macro-F1: {val_f1:.4f}")

    test_pred = model.predict(split.X_test)
    test_f1 = f1_score(split.y_test, test_pred, average="macro", zero_division=0)
    baseline = majority_class_baseline(split.y_train, split.y_test)
    print(f"Test macro-F1:       {test_f1:.4f}")
    print(f"Majority baseline:   {baseline:.4f}")

    print("\nClassification report:")
    print(classification_report(split.y_test, test_pred, zero_division=0))

    # Vocabulary the model was actually fitted on - training split only.
    fitted_vocab = sorted(split.X_train["Soil type"].unique())
    all_vocab = sorted(df["Soil type"].unique())
    unseen = sorted(set(all_vocab) - set(fitted_vocab))
    if unseen:
        report.note(
            f"soil types present in the dataset but absent from the training "
            f"split, so the model was never fitted on them: {unseen}"
        )

    report.check("macro-F1 (test)", BAR_MACRO_F1, float(test_f1))
    report.note(f"majority-class baseline accuracy was {baseline:.4f}")
    report.note(
        "exactly 100 rows per class across 31 classes is a synthetic-generation "
        "signature; this overstates performance on observed data"
    )
    report.note(
        "only 3 of the photo classifier's 4 soil classes exist in this "
        "vocabulary; Cinder has no mapping at all"
    )
    print(report.render())

    paths.ensure_artifacts_dir()
    joblib.dump(
        {
            "model": model,
            "categorical": CATEGORICAL,
            "numeric": NUMERIC,
            "soil_type_vocab": fitted_vocab,
            "split_strategy": split.strategy,
            "passed_bar": report.passed,
        },
        paths.CROP_SOIL_TYPE_MODEL,
    )
    print(f"\nSaved -> {paths.CROP_SOIL_TYPE_MODEL.relative_to(paths.REPO_ROOT)}")


if __name__ == "__main__":
    main()
