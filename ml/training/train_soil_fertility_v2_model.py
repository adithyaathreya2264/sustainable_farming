"""Soil fertility class (Low / Medium / High) from 12 soil-test values (model 5b).

Run:
    python -m ml.training.train_soil_fertility_v2_model

Bar: MODEL_BARS.md section 9, 2026-09-25 entry "model 5b". Test macro-F1 at
least 0.75, recall(High) at least 0.50, and Karnataka-slice macro-F1 at least
0.75.

## What a pass means

The two supplied files label each sample by cutting `Fertility_Index` at 1.70
and 2.35, and the index is computed from the nutrients. A pass means the model
reproduces that rating scheme from the 12 values on a soil-test card. The
index itself is excluded from the features. The files' source was not
disclosed, so every artifact records `provenance_verified: False`.

## Pipeline

1. Combine the Karnataka and pan-India files (no shared sample, field or row).
2. Split 60/20/20 by `Field_ID`, stratified, so repeat tests of one field stay
   on one side.
3. Choose among logistic regression, random forest and gradient boosting on
   validation macro-F1; refit on train + validation; read test once.
4. Report the Karnataka slice (barred) and a leave-one-Karnataka-district-out
   figure (reported only).
"""

from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score, recall_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ml import paths
from ml.evaluation import Report

FEATURES = ["N", "P", "K", "pH", "EC", "OC", "S", "Zn", "Fe", "Cu", "Mn", "B"]
CLASSES = ["Low", "Medium", "High"]
BAR_MACRO_F1 = 0.75
BAR_HIGH_RECALL = 0.50
BAR_KARNATAKA_MACRO_F1 = 0.75
SEED = 42


def _load() -> pd.DataFrame:
    frames = [pd.read_csv(paths.require(p)) for p in (paths.SOIL_TESTS_KARNATAKA_CSV, paths.SOIL_TESTS_PAN_INDIA_CSV)]
    df = pd.concat(frames, ignore_index=True)
    if df["Sample_ID"].duplicated().any():
        raise SystemExit("Sample_IDs repeat across the two files; they were expected to be disjoint")
    if df[FEATURES].isna().any().any():
        raise SystemExit("Missing nutrient values")
    return df


def _candidates() -> dict:
    return {
        "logistic": make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced")),
        "random_forest": RandomForestClassifier(n_estimators=500, min_samples_leaf=2, class_weight="balanced",
                                                random_state=SEED, n_jobs=-1),
        "gradient_boosting": HistGradientBoostingClassifier(max_iter=400, learning_rate=0.05,
                                                            class_weight="balanced", random_state=SEED),
    }


def _macro(y_true, y_pred) -> float:
    return float(f1_score(y_true, y_pred, labels=CLASSES, average="macro", zero_division=0))


def main() -> None:
    report = Report("Soil fertility class, new soil tests (model 5b)")
    df = _load()
    y, groups = df["Fertility_Class"].to_numpy(), df["Field_ID"].to_numpy()
    print(f"{len(df)} samples, {df['Field_ID'].nunique()} fields, {df['State'].nunique()} states; "
          f"classes {df['Fertility_Class'].value_counts().to_dict()}")

    outer = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
    rest, test = next(outer.split(df, y, groups))
    inner = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=SEED)
    fit_i, val_i = next(inner.split(df.iloc[rest], y[rest], groups[rest]))
    train, val = rest[fit_i], rest[val_i]
    print(f"Split by field: train {len(train)}  val {len(val)}  test {len(test)}")

    X = df[FEATURES]
    val_scores = {}
    for name, model in _candidates().items():
        model.fit(X.iloc[train], y[train])
        val_scores[name] = _macro(y[val], model.predict(X.iloc[val]))
        print(f"  val {name:18s} macro-F1 {val_scores[name]:.4f}")
    chosen = max(val_scores, key=val_scores.get)
    print(f"Chosen on validation: {chosen}")

    model = _candidates()[chosen].fit(X.iloc[rest], y[rest])

    # Test, read once.
    predicted = model.predict(X.iloc[test])
    truth = y[test]
    macro = _macro(truth, predicted)
    high = float(recall_score(truth, predicted, labels=["High"], average="macro", zero_division=0))
    ka = (df["State"].iloc[test] == "Karnataka").to_numpy()
    ka_macro = _macro(truth[ka], predicted[ka])
    baseline = float((truth == pd.Series(y[rest]).mode()[0]).mean())
    print(f"\nTEST  macro-F1 {macro:.4f}  recall(High) {high:.4f}  accuracy {(truth == predicted).mean():.4f}  "
          f"majority baseline {baseline:.4f}")
    print(f"      Karnataka slice: {ka.sum()} samples, macro-F1 {ka_macro:.4f}")
    print(classification_report(truth, predicted, labels=CLASSES, zero_division=0))

    report.check("macro-F1 (test)", BAR_MACRO_F1, macro)
    report.check("recall(High) (test)", BAR_HIGH_RECALL, high)
    report.check(f"Karnataka-slice macro-F1 (test, n={int(ka.sum())})", BAR_KARNATAKA_MACRO_F1, ka_macro)

    # Leave one Karnataka district out: trained on everything else, not barred.
    held_out = {}
    for district in sorted(df.loc[df["State"] == "Karnataka", "District"].unique()):
        mask = ((df["State"] == "Karnataka") & (df["District"] == district)).to_numpy()
        m = _candidates()[chosen].fit(X[~mask], y[~mask])
        held_out[district] = _macro(y[mask], m.predict(X[mask]))
    print("Leave-one-Karnataka-district-out macro-F1: " +
          ", ".join(f"{d} {v:.3f}" for d, v in held_out.items()))
    report.note(f"held-out-district macro-F1 range {min(held_out.values()):.3f}-{max(held_out.values()):.3f} (not barred)")
    report.note(f"chosen on validation: {chosen}; majority baseline {baseline:.4f}")
    report.note("labels are a threshold of a nutrient index: a pass means the rating scheme is reproduced")
    report.note("PROVENANCE UNVERIFIED: user states the data is real and declined to name the source")
    print(report.render())

    joblib.dump({"model": model, "features": FEATURES, "classes": CLASSES, "passed_bar": report.passed,
                 "provenance_verified": False}, paths.SOIL_FERTILITY_V2_MODEL)
    paths.SOIL_FERTILITY_V2_MODEL.with_name("soil_fertility_v2_metrics.json").write_text(json.dumps({
        "passed_bar": report.passed, "provenance_verified": False, "chosen": chosen, "validation": val_scores,
        "test": {"macro_f1": macro, "recall_high": high, "karnataka_macro_f1": ka_macro,
                 "karnataka_rows": int(ka.sum()), "rows": int(len(test)), "baseline": baseline},
        "held_out_district_macro_f1": held_out,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Saved -> {paths.SOIL_FERTILITY_V2_MODEL.relative_to(paths.REPO_ROOT)}")


if __name__ == "__main__":
    main()
