"""12 soil chemistry features -> fertility class 0/1/2. Random Forest, 880 rows.

Run:  python -m ml.training.train_soil_fertility_model

## What changed from the inherited version, and why

The original already got the important thing right: it used
`class_weight="balanced"` and printed a per-class report rather than optimising
accuracy, with a docstring explaining that accuracy "would look good by just
guessing the majority classes and ignoring class 2." That reasoning is correct
and is why the bar below is macro-F1 plus class-2 recall specifically.

Changes: a three-way split, and the majority-class baseline is now computed in
both accuracy and macro-F1 so the gap between them is visible — on this dataset
a do-nothing predictor scores about 0.50 accuracy but only about 0.22 macro-F1,
which is exactly the trap the original docstring warned about.

## Why this model ships provisional no matter what it scores

`soil_fertility.csv` has columns N, P, K, pH, EC, OC, S, Zn, Fe, Cu, Mn, B and
Output. There is **no state, district, date or provenance column anywhere in
it.** Whether these 880 samples resemble Karnataka farmland is not merely
unverified — it is unverifiable from the data we hold.

That is a different and worse situation than a model with a known weakness. A
model can be statistically sound on its training distribution and still be
systematically wrong for our users, with nothing in the metrics to reveal it.
The same caution already applies to this project's non-Karnataka land-unit
conversions.

So: provisional label mandatory, per MODEL_BARS.md section 5, regardless of
macro-F1.

## Why class 2 gets its own bar

Class 2 is high-fertility soil and is 4.4% of the data (39 rows). A model that
never predicts it still looks strong overall. But failing to detect fertile
soil means telling a farmer to fertilise land that does not need it — wasted
money and leached nutrients. The bar is 0.50 recall, low in absolute terms and
set there only because roughly 8 class-2 rows land in the test fold, giving
recall a resolution of about 0.12. A finer threshold would be measuring noise.
"""

from __future__ import annotations

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, f1_score

from ml import paths
from ml.evaluation import (
    Report,
    macro_f1_of_majority_baseline,
    majority_class_baseline,
    per_class_recall,
    three_way_split,
)

FEATURES = ["N", "P", "K", "pH", "EC", "OC", "S", "Zn", "Fe", "Cu", "Mn", "B"]
TARGET = "Output"

# Bars from MODEL_BARS.md section 5.
BAR_MACRO_F1 = 0.75
BAR_CLASS2_RECALL = 0.50

FERTILITY_LABELS = {0: "Low fertility", 1: "Medium fertility", 2: "High fertility"}


def _predict(model, threshold, X):
    """Argmax, except class 2 wins whenever its probability clears `threshold`.

    Serving must apply the identical rule, so the threshold is persisted in the
    artifact and read back by `ml/algorithms/fertilizer_recommendation.py`. A
    threshold that exists only in the training script is train/serve skew
    waiting to happen — the model would keep returning predictions, just
    different ones than were measured here.
    """
    proba = model.predict_proba(X)
    idx2 = list(model.classes_).index(2)
    argmax = model.classes_[proba.argmax(axis=1)]
    return np.where(proba[:, idx2] >= threshold, 2, argmax)


def _tune(split):
    """Grid over leaf size and class-2 threshold, selected on validation.

    Chosen by macro-F1, tie-broken toward the LOWER threshold: the metric
    plateaus across several thresholds on this data, and a lower one detects
    more high-fertility soil. That is the cheaper error direction — a false
    "high fertility" means skipping fertiliser that was not needed anyway,
    whereas a miss means paying to fertilise land that did not need it.

    This grid is searched against 176 validation rows, of which 8 are class 2.
    A threshold chosen on 8 samples is a fragile thing, and the test result
    below should be read with that in mind.
    """
    best = None
    for min_leaf in (1, 2, 4):
        model = RandomForestClassifier(
            n_estimators=500,
            min_samples_leaf=min_leaf,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )
        model.fit(split.X_train, split.y_train)
        for threshold in (0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50):
            pred = _predict(model, threshold, split.X_val)
            score = f1_score(split.y_val, pred, average="macro", zero_division=0)
            key = (round(float(score), 4), -threshold)
            if best is None or key > best[0]:
                best = (key, model, threshold, float(score))
    _, model, threshold, score = best
    return model, threshold, score


def main() -> None:
    df = pd.read_csv(paths.require(paths.SOIL_FERTILITY_CSV))
    X, y = df[FEATURES], df[TARGET]

    report = Report("Soil fertility")

    counts = y.value_counts().sort_index()
    print("Class distribution:")
    for cls, n in counts.items():
        print(f"  {cls} ({FERTILITY_LABELS.get(int(cls), '?'):16s}) {n:4d}  {n/len(y):.3%}")

    split = three_way_split(X, y)
    print(f"\nSplit: {split.strategy}  ({split.sizes()})")
    print(f"class-2 rows in test fold: {(split.y_test == 2).sum()}")

    # Tuning happens here, against validation only. `class_weight="balanced"`
    # alone leaves class 2 badly under-detected (recall 0.375 on validation),
    # because with 23 training rows the trees rarely make it the argmax. The
    # effective lever is the decision threshold: predict class 2 whenever its
    # probability clears a low bar, rather than only when it wins outright.
    model, threshold, val_f1 = _tune(split)
    print(
        f"\nSelected: min_samples_leaf={model.min_samples_leaf}, "
        f"class-2 threshold={threshold:.2f}"
    )
    print(f"Validation macro-F1: {val_f1:.4f}")

    test_pred = _predict(model, threshold, split.X_test)
    macro_f1 = f1_score(split.y_test, test_pred, average="macro", zero_division=0)
    accuracy = accuracy_score(split.y_test, test_pred)
    baseline_acc = majority_class_baseline(split.y_train, split.y_test)
    baseline_f1 = macro_f1_of_majority_baseline(split.y_train, split.y_test)

    print(f"Test macro-F1:       {macro_f1:.4f}   (this is the bar)")
    print(f"Test accuracy:       {accuracy:.4f}   (reported, deliberately NOT the bar)")
    print(f"Baseline macro-F1:   {baseline_f1:.4f}")
    print(f"Baseline accuracy:   {baseline_acc:.4f}   <- why accuracy is not the bar")

    recalls = per_class_recall(split.y_test, test_pred, [0, 1, 2])
    print("\nPer-class recall:")
    for cls, score in recalls.items():
        print(f"  {cls} ({FERTILITY_LABELS.get(int(cls), '?'):16s}) {score:.4f}")

    print("\nClassification report:")
    print(classification_report(split.y_test, test_pred, zero_division=0))

    report.check("macro-F1 (test)", BAR_MACRO_F1, float(macro_f1))
    report.check("recall(class 2, high fertility)", BAR_CLASS2_RECALL, recalls["2"])
    report.note(
        f"majority-class baseline: {baseline_acc:.4f} accuracy but only "
        f"{baseline_f1:.4f} macro-F1"
    )
    report.note(
        "PROVISIONAL LABEL MANDATORY: soil_fertility.csv has no geography, date "
        "or provenance column, so its relevance to Karnataka farmland is "
        "unverifiable by construction, not merely unverified"
    )
    report.note(
        f"class-2 recall measured on {(split.y_test == 2).sum()} test rows; "
        f"resolution is roughly {1 / max(1, (split.y_test == 2).sum()):.3f}"
    )
    print(report.render())

    paths.ensure_artifacts_dir()
    joblib.dump(
        {
            "model": model,
            "features": FEATURES,
            "class2_threshold": threshold,
            "class_labels": FERTILITY_LABELS,
            "split_strategy": split.strategy,
            "passed_bar": report.passed,
            "confidence_ceiling": "provisional",
        },
        paths.SOIL_FERTILITY_MODEL,
    )
    print(f"\nSaved -> {paths.SOIL_FERTILITY_MODEL.relative_to(paths.REPO_ROOT)}")


if __name__ == "__main__":
    main()
