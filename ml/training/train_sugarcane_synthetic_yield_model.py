"""Sugarcane yield from the synthetic farm CSV (model 16). Never served.

Run:
    python -m ml.training.train_sugarcane_synthetic_yield_model

Bar: MODEL_BARS.md section 9, 2026-09-24 entry "model 16". R-squared at least
0.60 and MAE at least 10% below the training-mean baseline on the 2024 fold.

## Why this model is never served

`FINAL_SUGARCANE_DATASET.csv` is generated, not collected:

- monthly rainfall is about 1,400 mm in every month;
- sand + silt + clay does not sum to 100;
- dates contradict the stated crop duration;
- categories are near-uniform, with about 4% missing injected into every column;
- yield follows nitrogen, potassium and a disease-severity step, while
  variety, soil, irrigation and season have no effect at all.

A good score measures how well the model recovers that formula. The artifact
records `served: False` and there is no serving module.

## Pipeline

1. Drop constant columns, the plot ID and the raw date strings.
2. Train on 2018-2022 (plus rows with no year), validate on 2023, test on 2024.
3. Compare ridge regression (median/most-frequent imputation, one-hot) with
   histogram gradient boosting (native missing-value handling) on validation.
4. Refit the winner on train + validation; read the 2024 fold once.
"""

from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

from ml import paths
from ml.evaluation import Report

BAR_R2 = 0.60
BAR_MAE_IMPROVEMENT = 0.10

TARGET = "Yield_Quintal_per_Acre"
DROP = ["State", "District", "Region", "Sugar_Mill", "Khasra_No", "Planting_Date", "Harvesting_Date"]
VAL_YEAR, TEST_YEAR = 2023, 2024
SEED = 42


def _load() -> pd.DataFrame:
    df = pd.read_csv(paths.require(paths.SUGARCANE_SYNTHETIC_CSV))
    # "h:mm" -> hours, so the column is numeric rather than 400 categories.
    parts = df["Sunshine_Hours_hh_mm"].str.split(":", expand=True).astype(float)
    df["Sunshine_Hours_hh_mm"] = parts[0] + parts[1] / 60
    constant = [c for c in DROP[:4] if df[c].nunique(dropna=True) > 1]
    if constant:
        raise SystemExit(f"Expected constant columns vary: {constant}")
    return df.drop(columns=DROP)


def _candidates(numeric, categorical) -> dict:
    ridge = Pipeline([
        ("prep", ColumnTransformer([
            ("num", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), numeric),
            ("cat", make_pipeline(SimpleImputer(strategy="most_frequent"),
                                  OneHotEncoder(handle_unknown="ignore")), categorical),
        ])),
        ("model", RidgeCV(alphas=np.logspace(-3, 3, 25))),
    ])
    boosting = Pipeline([
        ("prep", ColumnTransformer([
            ("num", "passthrough", numeric),
            ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=np.nan,
                                   encoded_missing_value=np.nan), categorical),
        ])),
        ("model", HistGradientBoostingRegressor(
            max_iter=400, learning_rate=0.05, min_samples_leaf=20,
            categorical_features=list(range(len(numeric), len(numeric) + len(categorical))),
            random_state=SEED,
        )),
    ])
    return {"ridge": ridge, "hist_gradient_boosting": boosting}


def main() -> None:
    report = Report("Sugarcane yield, synthetic CSV (model 16)")
    df = _load()
    features = [c for c in df.columns if c != TARGET]
    numeric = [c for c in features if pd.api.types.is_numeric_dtype(df[c]) and c != "Year"]
    categorical = [c for c in features if c not in numeric and c != "Year"]

    test = df[df["Year"] == TEST_YEAR]
    val = df[df["Year"] == VAL_YEAR]
    train = df[~df["Year"].isin([VAL_YEAR, TEST_YEAR])]  # includes rows with no year
    print(f"{len(df)} rows; {len(numeric)} numeric + {len(categorical)} categorical features")
    print(f"Split by year: train {len(train)} (<= 2022 or unknown)  val {len(val)} (2023)  test {len(test)} (2024)")

    cols = numeric + categorical
    val_scores = {}
    for name, model in _candidates(numeric, categorical).items():
        model.fit(train[cols], train[TARGET])
        predicted = model.predict(val[cols])
        val_scores[name] = {"mae": float(mean_absolute_error(val[TARGET], predicted)),
                            "r2": float(r2_score(val[TARGET], predicted))}
        print(f"  val {name:24s} MAE {val_scores[name]['mae']:7.2f}  R2 {val_scores[name]['r2']:.4f}")
    chosen = min(val_scores, key=lambda n: val_scores[n]["mae"])
    print(f"Chosen on validation: {chosen}")

    fit = pd.concat([train, val])
    model = _candidates(numeric, categorical)[chosen].fit(fit[cols], fit[TARGET])

    # Test, read once.
    predicted = model.predict(test[cols])
    mae = float(mean_absolute_error(test[TARGET], predicted))
    r2 = float(r2_score(test[TARGET], predicted))
    baseline_mae = float(mean_absolute_error(test[TARGET], np.full(len(test), fit[TARGET].mean())))
    improvement = 1 - mae / baseline_mae
    print(f"\nTEST (2024)  R2 {r2:.4f}  MAE {mae:.2f}  baseline MAE {baseline_mae:.2f}  improvement {improvement:.1%}")

    report.check("R-squared (2024 test)", BAR_R2, r2)
    report.check("MAE improvement over mean baseline (2024 test)", BAR_MAE_IMPROVEMENT, improvement)
    report.note(f"chosen on 2023 validation: {chosen} ({val_scores[chosen]})")
    report.note("SYNTHETIC DATA: a pass measures recovery of the generator's formula; "
                "NEVER SERVED regardless of verdict")
    print(report.render())

    joblib.dump({"pipeline": model, "passed_bar": report.passed, "served": False,
                 "synthetic_data": True, "features": cols, "target": TARGET},
                paths.SUGARCANE_SYNTHETIC_YIELD_MODEL)
    metrics_path = paths.SUGARCANE_SYNTHETIC_YIELD_MODEL.with_name("sugarcane_synthetic_yield_metrics.json")
    metrics_path.write_text(json.dumps({
        "passed_bar": report.passed, "served": False, "synthetic_data": True, "chosen": chosen,
        "validation": val_scores,
        "test": {"r2": r2, "mae": mae, "baseline_mae": baseline_mae, "improvement": improvement,
                 "rows": int(len(test))},
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Saved -> {paths.SUGARCANE_SYNTHETIC_YIELD_MODEL.relative_to(paths.REPO_ROOT)}")


if __name__ == "__main__":
    main()
