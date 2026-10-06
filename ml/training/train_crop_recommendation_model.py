"""N/P/K + weather -> crop. Random Forest over 6,596 rows and 51 classes.

Run:  python -m ml.training.train_crop_recommendation_model

## What changed from the inherited version, and why

The original was the soundest script in the set — it already stratified and
kept preprocessing out of the leakage path. Three changes:

1. **Three-way split.** It reported accuracy on the same fold it used to judge
   the model. That fold is now validation; test is touched once, at the end.

2. **The bar is per-seeded-crop recall, not accuracy.** The original printed
   overall accuracy and a 51-class report. But the class sizes run from 7 rows
   (`pumpkin`) to 461, with 14 classes under 50 — so a macro average is
   dominated by classes too small to learn or to measure, and an overall
   accuracy is dominated by the large ones. Neither answers the question that
   matters: is this right about the four crops the app can actually plant?
   Rice, ragi, maize and cotton have 100/293/100/100 rows, which is enough to
   measure honestly. See MODEL_BARS.md section 1.

3. **Labels are translated into the app's vocabulary** at serve time via
   `ml/labels.py`, and the model's own classes are checked against the seeded
   crops here so the sugarcane gap is stated by the build rather than
   discovered by a farmer.

## The sugarcane gap

`merged_crop_dataset.csv` has no sugarcane among its 51 labels. Sugarcane is
one of the five crops seeded in the app's `crops` table. This model therefore
cannot ever recommend it — not a bug to be fixed here, but a limit that has to
travel with the output.

## What a good score here does and does not mean

The feature values carry nine decimal places and the classes are cleanly
separated; this is the well-known Kaggle crop-recommendation dataset, sampled
from per-crop distributions rather than measured in fields. A high score is
evidence the pipeline is wired correctly. It is not evidence that the model
knows what to plant on a particular acre in Karnataka. Ships provisional.
"""

from __future__ import annotations

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, f1_score

from ml import paths
from ml.evaluation import Report, majority_class_baseline, per_class_recall, three_way_split
from ml.prep.common import SEEDED_CROPS, crop_key

FEATURES = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]
TARGET = "label"

# Bars from MODEL_BARS.md section 1.
BAR_SEEDED_RECALL = 0.85
BAR_WEIGHTED_F1 = 0.90

# The four seeded crops this dataset actually contains, as they are spelled in
# its `label` column. Sugarcane is absent - see the module docstring.
SEEDED_IN_DATASET = ["rice", "ragi", "maize", "cotton"]


def main() -> None:
    df = pd.read_csv(paths.require(paths.CROP_RECOMMENDATION_CSV))
    X, y = df[FEATURES], df[TARGET]

    report = Report("Crop recommendation (N/P/K + weather)")

    present = set(y.unique())
    # Compare through crop_key rather than raw strings: the dataset spells
    # things its own way, and the point is which of the app's seeded crops this
    # model can reach, not which literals happen to match.
    reachable = {crop_key(label) for label in present}
    missing_seeded = sorted(set(SEEDED_CROPS) - reachable)
    if missing_seeded:
        report.note(
            f"seeded crop(s) absent from this dataset entirely, so the model can "
            f"never recommend them: {missing_seeded}"
        )
        print(f"NOTE: unreachable seeded crops: {missing_seeded}")

    split = three_way_split(X, y)
    print(f"Split: {split.strategy}  ({split.sizes()})")
    print(f"{y.nunique()} classes, {len(df)} rows")

    model = RandomForestClassifier(n_estimators=300, random_state=42, n_jobs=-1)
    model.fit(split.X_train, split.y_train)

    # Validation is where any tuning decision would be made. Printed so the
    # gap between validation and test is visible; a large gap means the test
    # number was lucky rather than earned.
    val_pred = model.predict(split.X_val)
    val_f1 = f1_score(split.y_val, val_pred, average="weighted", zero_division=0)
    print(f"\nValidation weighted-F1: {val_f1:.4f}")

    # Test fold: touched once, here.
    test_pred = model.predict(split.X_test)
    test_f1 = f1_score(split.y_test, test_pred, average="weighted", zero_division=0)
    macro_f1 = f1_score(split.y_test, test_pred, average="macro", zero_division=0)
    baseline = majority_class_baseline(split.y_train, split.y_test)

    print(f"Test weighted-F1:       {test_f1:.4f}")
    print(f"Test macro-F1:          {macro_f1:.4f}  (reported, not barred - see docstring)")
    print(f"Majority baseline acc:  {baseline:.4f}")

    recalls = per_class_recall(split.y_test, test_pred, SEEDED_IN_DATASET)
    print("\nPer-seeded-crop recall (this is the bar):")
    for crop, score in recalls.items():
        print(f"  {crop:10s} {score:.4f}")

    print("\nFull classification report (51 classes):")
    print(classification_report(split.y_test, test_pred, zero_division=0))

    report.check("weighted-F1 (test)", BAR_WEIGHTED_F1, float(test_f1))
    for crop, score in recalls.items():
        report.check(f"recall({crop})", BAR_SEEDED_RECALL, score)
    report.note(f"majority-class baseline accuracy was {baseline:.4f}")
    report.note(
        "dataset is synthetically sampled and highly separable; a high score "
        "evidences a correct pipeline, not field accuracy"
    )
    print(report.render())

    paths.ensure_artifacts_dir()
    joblib.dump(
        {
            "model": model,
            "features": FEATURES,
            "classes": sorted(present),
            "split_strategy": split.strategy,
            "passed_bar": report.passed,
        },
        paths.CROP_RECOMMENDATION_MODEL,
    )
    print(f"\nSaved -> {paths.CROP_RECOMMENDATION_MODEL.relative_to(paths.REPO_ROOT)}")


if __name__ == "__main__":
    main()
