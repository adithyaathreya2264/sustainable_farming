"""Soybean seed yield from plant traits, all features (model 15).

Run:
    python -m ml.training.train_soybean_yield_model

Bar: MODEL_BARS.md section 9, 2026-09-24 entry "model 15". Test R-squared at
least 0.70 and MAE at least 30% below the training-mean baseline.

## What this measures, and what it does not

The CSV is one factorial field experiment: 108 unique plots, each repeated
about 500 times. It is de-duplicated first. Several features are only known
after harvest (pods, seeds per pod, seed weight, biomass) or only in a lab
(chlorophyll, sugars, protein, leaf water), and yield is close to the product
of the harvest components. A pass means the model fits this experiment. It
does not mean a farmer could use it, and no serving module exists: none of
these inputs is available in the app.

## Pipeline

1. De-duplicate; parse `C#S#G#` into condition, treatment and genotype.
2. Hold out 20% of treatment codes as the test fold, so replicate plots of one
   treatment never straddle the boundary.
3. Choose between ridge regression and a random forest by grouped 4-fold
   cross-validation on the remaining treatments.
4. Refit the winner on all non-test rows; read the test fold once.
"""

from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ml import paths
from ml.evaluation import Report

BAR_R2 = 0.70
BAR_MAE_IMPROVEMENT = 0.30

TARGET = "Seed Yield per Unit Area (SYUA)"
FACTORS = ["condition", "treatment", "genotype"]
TEST_FRACTION = 0.20
SEED = 42


def _load() -> pd.DataFrame:
    raw = pd.read_csv(paths.require(paths.SOYBEAN_CSV))
    raw.columns = [c.strip() for c in raw.columns]
    df = raw.drop_duplicates().reset_index(drop=True)
    print(f"{len(raw):,} rows -> {len(df)} unique ({len(raw) - len(df):,} exact duplicates removed)")
    codes = df["Parameters"].str.extract(r"^C(\d)S(\d)G(\d)$")
    if codes.isna().any().any():
        raise SystemExit("Unparseable Parameters codes: " + ", ".join(df.loc[codes.isna().any(axis=1), "Parameters"]))
    df[FACTORS] = codes.values
    return df


def _numeric_features(df: pd.DataFrame) -> list[str]:
    return [c for c in df.select_dtypes("number").columns if c != TARGET]


def _candidates(numeric: list[str]) -> dict:
    def pipe(regressor, scale: bool):
        prep = ColumnTransformer([
            ("num", StandardScaler() if scale else "passthrough", numeric),
            ("cat", OneHotEncoder(handle_unknown="ignore"), FACTORS),
        ])
        return Pipeline([("prep", prep), ("model", regressor)])

    return {
        "ridge": pipe(RidgeCV(alphas=np.logspace(-3, 3, 25)), scale=True),
        "random_forest": pipe(
            RandomForestRegressor(n_estimators=500, min_samples_leaf=2, random_state=SEED, n_jobs=-1),
            scale=False,
        ),
    }


def main() -> None:
    report = Report("Soybean seed yield (model 15)")
    df = _load()
    numeric = _numeric_features(df)
    X, y, groups = df[numeric + FACTORS], df[TARGET].to_numpy(), df["Parameters"].to_numpy()
    print(f"{df['Parameters'].nunique()} treatment codes; {len(numeric)} numeric features + {FACTORS}")

    splitter = GroupShuffleSplit(n_splits=1, test_size=TEST_FRACTION, random_state=SEED)
    pool_idx, test_idx = next(splitter.split(X, y, groups))
    X_pool, y_pool, g_pool = X.iloc[pool_idx], y[pool_idx], groups[pool_idx]
    X_test, y_test = X.iloc[test_idx], y[test_idx]
    print(f"Pool {len(pool_idx)} rows ({len(set(g_pool))} treatments); "
          f"test {len(test_idx)} rows ({len(set(groups[test_idx]))} treatments)")

    # Model family chosen by grouped CV on the pool only.
    cv_scores = {}
    for name, model in _candidates(numeric).items():
        maes, r2s = [], []
        for fit, held in GroupKFold(n_splits=4).split(X_pool, y_pool, g_pool):
            model.fit(X_pool.iloc[fit], y_pool[fit])
            predicted = model.predict(X_pool.iloc[held])
            maes.append(mean_absolute_error(y_pool[held], predicted))
            r2s.append(r2_score(y_pool[held], predicted))
        cv_scores[name] = {"mae": float(np.mean(maes)), "r2": float(np.mean(r2s))}
        print(f"  CV {name:14s} MAE {np.mean(maes):8.1f}  R2 {np.mean(r2s):.4f}")
    chosen = min(cv_scores, key=lambda n: cv_scores[n]["mae"])
    print(f"Chosen on grouped CV: {chosen}")

    model = _candidates(numeric)[chosen].fit(X_pool, y_pool)

    # Test, read once.
    predicted = model.predict(X_test)
    mae = float(mean_absolute_error(y_test, predicted))
    r2 = float(r2_score(y_test, predicted))
    baseline_mae = float(mean_absolute_error(y_test, np.full_like(y_test, y_pool.mean())))
    improvement = 1 - mae / baseline_mae
    print(f"\nTEST  R2 {r2:.4f}  MAE {mae:.1f}  baseline MAE {baseline_mae:.1f}  improvement {improvement:.1%}")

    report.check("R-squared (test)", BAR_R2, r2)
    report.check("MAE improvement over mean baseline (test)", BAR_MAE_IMPROVEMENT, improvement)
    report.note(f"chosen on grouped CV: {chosen} ({cv_scores[chosen]})")
    report.note(f"{len(test_idx)} test rows from {len(set(groups[test_idx]))} treatments of one trial - a pass means 'fits this experiment'")
    report.note("features include post-harvest yield components and lab-only measurements; "
                "NOT SERVED - no app input exists")
    print(report.render())

    if chosen == "random_forest":
        forest = model.named_steps["model"]
        names = model.named_steps["prep"].get_feature_names_out()
        top = sorted(zip(forest.feature_importances_, names), reverse=True)[:6]
        print("Top importances: " + ", ".join(f"{n.split('__')[-1]} {v:.2f}" for v, n in top))

    joblib.dump({"pipeline": model, "passed_bar": report.passed, "served": False,
                 "features": numeric + FACTORS, "target": TARGET}, paths.SOYBEAN_YIELD_MODEL)
    metrics_path = paths.SOYBEAN_YIELD_MODEL.with_name("soybean_yield_metrics.json")
    metrics_path.write_text(json.dumps({
        "passed_bar": report.passed, "served": False, "chosen": chosen, "cv": cv_scores,
        "test": {"r2": r2, "mae": mae, "baseline_mae": baseline_mae, "improvement": improvement,
                 "rows": int(len(test_idx))},
        "unique_rows": int(len(df)),
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Saved -> {paths.SOYBEAN_YIELD_MODEL.relative_to(paths.REPO_ROOT)}")


if __name__ == "__main__":
    main()
