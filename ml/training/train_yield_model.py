"""Crop yield, XGBoost regression, evaluated on held-out YEARS.

Run:  python -m ml.training.train_yield_model

## What changed from the inherited version, and why

The inherited script reported R-squared = 0.9501 from a random
`train_test_split` over state x crop x year panel data, and the obvious
suspicion was that this was panel memorisation — adjacent years of the same
crop in the same state are near-duplicates, so a random split seats most test
rows next to their own neighbours in training.

**That suspicion was tested and turned out to be wrong.** On a held-out-years
split the same model scores R-squared 0.9495, essentially unchanged. The
random split was not inflating R-squared.

The real problem is that R-squared was never the informative metric here. Crop
identity alone explains almost all the variance, because the crops sit on
wildly different scales (coconut median 8,466, rice 2.2). A plain
per-(crop, state, season) median lookup — no model at all — scores R-squared
0.9189 on the same held-out years. So 0.95 sounds excellent while being barely
distinguishable from looking the answer up in a table.

Measured against that lookup instead, the inherited configuration was **19%
worse than doing nothing**, with a scale-free median error of 0.99 against the
lookup's 0.26. That is what the baseline comparison in MODEL_BARS.md exists to
catch and what R-squared completely hid.

Changes:

1. **Held-out years, not random rows.** Train 1997-2014, validate 2015-2017,
   test 2018-2020. This asks the only question a farmer cares about: given
   history, what happens in a year we have not seen?

2. **A real baseline.** The repo already computes per-(crop, state, season)
   percentile bands in `ml/prep/clean_crop_yield.py`. That median lookup is
   the thing this model has to beat, and it is a genuinely strong baseline for
   agricultural yield. If XGBoost cannot beat a median by a clear margin, then
   it buys nothing but a serving dependency and a failure mode, and the correct
   outcome is to ship the lookup instead. MODEL_BARS.md section 6.

3. **A Karnataka slice.** Karnataka is the best-represented state (1,432 rows)
   and the one our farmers are in. A national average can hide a local failure,
   so Karnataka is scored separately and must also beat its own baseline.

4. **The per-hectare conversion is kept**, along with the original reasoning:
   the source `area`, `fertilizer` and `pesticide` columns are state-level
   absolute totals for that crop/year/season, not per-field rates (fertilizer
   correlates about 0.97 with area). A farmer can answer "how much urea per
   acre", not "how much urea did my entire state apply".

## The yield column has no usable unit - this constrains the output, not the model

`DATASETS_STATUS.md` section 2.1 established by recomputation that `yield` is
not production/area (they disagree in 13,663 of 19,689 rows) and that its scale
is crop-dependent: median 8,466 for coconut, 53 for sugarcane, 2.2 for rice.
Within one crop the values are consistent, so a crop's own distribution is a
sound basis for comparison; across crops, nothing is.

Two consequences:

- **Serving returns a percentile, never a number.** This script also emits
  `yield_benchmarks.json` so the serving layer can convert a raw prediction
  into "around the 60th percentile for Rice in Karnataka, Kharif".
- **A global MAE is barely interpretable**, being dominated by coconut-scale
  crops. It is still a fair *comparison* between model and baseline, since both
  are measured on the same rows, so the bar stands. A scale-free per-crop
  normalised error is also reported, purely to make the result readable.

## Rows dropped

`yield <= 0` (112 rows) is a missing observation recorded as a number, not a
harvest of nothing. Dropped, matching `ml/prep/clean_crop_yield.py`.
"""

from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.compose import ColumnTransformer
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from ml import paths
from ml.evaluation import Report
from ml.prep.common import percentile

CATEGORICAL = ["crop", "season", "state"]
NUMERIC = [
    "year",
    "fertilizer_per_ha",
    "pesticide_per_ha",
    "avg_temp_c",
    "total_rainfall_mm",
    "avg_humidity_percent",
]
TARGET = "yield"

TRAIN_MAX_YEAR = 2014
VAL_MAX_YEAR = 2017

# Bars from MODEL_BARS.md section 6.
BAR_MAE_IMPROVEMENT = 0.10
BAR_R2 = 0.60

MIN_SAMPLES_PER_BAND = 5


def _load() -> pd.DataFrame:
    df = pd.read_csv(paths.require(paths.CROP_YIELD_CSV))
    weather = pd.read_csv(paths.require(paths.STATE_WEATHER_CSV))

    for col in CATEGORICAL:
        # The source pads these ("Kharif     ", "Whole Year ").
        df[col] = df[col].str.strip()
    weather["state"] = weather["state"].str.strip()

    df = df.dropna(subset=CATEGORICAL + ["area", "fertilizer", "pesticide", "year", TARGET])
    before_zero = len(df)
    df = df[df[TARGET] > 0]
    df = df[df["area"] > 0]
    print(f"Dropped {before_zero - len(df)} rows with non-positive yield or area")

    # State-level absolute totals -> per-hectare rates a farmer can supply.
    df["fertilizer_per_ha"] = df["fertilizer"] / df["area"]
    df["pesticide_per_ha"] = df["pesticide"] / df["area"]

    before = len(df)
    df = df.merge(weather, on=["state", "year"], how="left")
    df = df.dropna(subset=["avg_temp_c", "total_rainfall_mm", "avg_humidity_percent"])
    print(f"Weather join: {len(df)}/{before} rows matched")
    return df


def _baseline_table(train: pd.DataFrame) -> dict:
    """Three-tier median lookup built from training years only.

    Mirrors the fallback `ml/prep/clean_crop_yield.py` and `soilLookup.js` both
    use: most specific scope first, widening until something is known.
    """
    return {
        "crop_state_season": train.groupby(["crop", "state", "season"])[TARGET].median().to_dict(),
        "crop_state": train.groupby(["crop", "state"])[TARGET].median().to_dict(),
        "crop": train.groupby("crop")[TARGET].median().to_dict(),
        "global": float(train[TARGET].median()),
    }


def _baseline_predict(table: dict, rows: pd.DataFrame) -> np.ndarray:
    out = []
    for crop, state, season in zip(rows["crop"], rows["state"], rows["season"]):
        value = table["crop_state_season"].get((crop, state, season))
        if value is None:
            value = table["crop_state"].get((crop, state))
        if value is None:
            value = table["crop"].get(crop)
        if value is None:
            value = table["global"]
        out.append(value)
    return np.asarray(out, dtype=float)


def _normalised_error(y_true: np.ndarray, y_pred: np.ndarray, crops: pd.Series, table: dict) -> float:
    """Median absolute error scaled by each crop's own median.

    Scale-free, so it is not swamped by coconut. Reported only; not a bar.
    """
    scales = np.asarray([max(table["crop"].get(c, table["global"]), 1e-9) for c in crops])
    return float(np.median(np.abs(y_true - y_pred) / scales))


def _predict(model, rows) -> np.ndarray:
    """Invert the log1p target transform, clipped at zero.

    The model is fitted on log1p(yield), so every call site must expm1 the
    output. Serving imports this rather than reimplementing it — the inherited
    codebase already had one case of a feature computed two ways in two files,
    and this is the same hazard.
    """
    return np.expm1(model.predict(rows)).clip(min=0.0)


def _score(name: str, y_true, y_pred, crops, table) -> dict:
    return {
        "scope": name,
        "n": int(len(y_true)),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "r2": float(r2_score(y_true, y_pred)) if len(y_true) > 1 else float("nan"),
        "normalised_median_error": _normalised_error(
            np.asarray(y_true), np.asarray(y_pred), crops, table
        ),
    }


def _build_benchmarks(df: pd.DataFrame) -> list[dict]:
    """Percentile bands so serving can express a prediction as a position.

    Built over every year, not just training years: these are descriptive
    statistics of what this crop has historically done, not a prediction, so
    withholding recent years would only make them less accurate.
    """
    rows: list[dict] = []

    def band(values: list[float], **scope) -> None:
        if len(values) < MIN_SAMPLES_PER_BAND:
            return
        values = sorted(values)
        rows.append(
            {
                **scope,
                "p10": round(percentile(values, 0.10), 4),
                "p25": round(percentile(values, 0.25), 4),
                "median": round(percentile(values, 0.50), 4),
                "p75": round(percentile(values, 0.75), 4),
                "p90": round(percentile(values, 0.90), 4),
                "sample_count": len(values),
                # Carried on every row so it cannot be lost by someone reading
                # only the JSON. See DATASETS_STATUS.md section 2.1.
                "unit": None,
            }
        )

    for (crop, state, season), grp in df.groupby(["crop", "state", "season"]):
        band(grp[TARGET].tolist(), crop=crop, state=state, season=season, scope="crop_state_season")
    for (crop, state), grp in df.groupby(["crop", "state"]):
        band(grp[TARGET].tolist(), crop=crop, state=state, season=None, scope="crop_state")
    for crop, grp in df.groupby("crop"):
        band(grp[TARGET].tolist(), crop=crop, state=None, season=None, scope="crop")
    return rows


def main() -> None:
    df = _load()
    report = Report("Yield prediction")

    train = df[df["year"] <= TRAIN_MAX_YEAR]
    val = df[(df["year"] > TRAIN_MAX_YEAR) & (df["year"] <= VAL_MAX_YEAR)]
    test = df[df["year"] > VAL_MAX_YEAR]
    strategy = (
        f"held-out years: train <={TRAIN_MAX_YEAR}, "
        f"val {TRAIN_MAX_YEAR + 1}-{VAL_MAX_YEAR}, test >{VAL_MAX_YEAR}"
    )
    print(f"\nSplit: {strategy}")
    print(f"  train={len(train)} val={len(val)} test={len(test)}")

    table = _baseline_table(train)

    model = Pipeline(
        [
            (
                "preprocess",
                ColumnTransformer(
                    [("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL)],
                    remainder="passthrough",
                ),
            ),
            (
                "regressor",
                xgb.XGBRegressor(
                    n_estimators=600,
                    max_depth=6,
                    learning_rate=0.05,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    # Squared error on the raw target is dominated by crops on a
                    # large scale: one coconut row (median 8,466) outweighs
                    # thousands of rice rows (median 2.2), so the model spends
                    # its capacity on a handful of crops and loses to a plain
                    # median lookup everywhere else. Absolute error on a log
                    # target fixes both halves of that. Selected on validation:
                    # raw -17.6% vs baseline, log1p -3.0%, log1p+MAE +24.3%.
                    objective="reg:absoluteerror",
                    random_state=42,
                ),
            ),
        ]
    )
    features = CATEGORICAL + NUMERIC
    model.fit(train[features], np.log1p(train[TARGET]))

    val_scores = _score("validation", val[TARGET], _predict(model, val[features]), val["crop"], table)
    print(f"\nValidation  MAE={val_scores['mae']:.4f}  R2={val_scores['r2']:.4f}")

    # Test fold, touched once.
    test_pred = _predict(model, test[features])
    base_pred = _baseline_predict(table, test)

    model_scores = _score("test (national)", test[TARGET], test_pred, test["crop"], table)
    base_scores = _score("baseline (national)", test[TARGET], base_pred, test["crop"], table)

    ka = test["state"] == "Karnataka"
    ka_model = _score("test (Karnataka)", test[TARGET][ka], test_pred[ka], test["crop"][ka], table)
    ka_base = _score(
        "baseline (Karnataka)", test[TARGET][ka], base_pred[ka], test["crop"][ka], table
    )

    print(f"\n{'scope':24s} {'n':>6s} {'MAE':>12s} {'R2':>9s} {'norm.err':>10s}")
    for s in (model_scores, base_scores, ka_model, ka_base):
        print(f"{s['scope']:24s} {s['n']:6d} {s['mae']:12.4f} {s['r2']:9.4f} {s['normalised_median_error']:10.4f}")

    improvement = (base_scores["mae"] - model_scores["mae"]) / base_scores["mae"]
    ka_improvement = (ka_base["mae"] - ka_model["mae"]) / ka_base["mae"]
    print(f"\nMAE improvement over baseline  national: {improvement:+.2%}   Karnataka: {ka_improvement:+.2%}")

    report.check("MAE improvement vs median baseline (national)", BAR_MAE_IMPROVEMENT, improvement)
    report.check("MAE improvement vs median baseline (Karnataka)", BAR_MAE_IMPROVEMENT, ka_improvement)
    report.check("R-squared on held-out years", BAR_R2, model_scores["r2"])
    report.note(
        f"R-squared is a weak signal here: the median-lookup baseline alone "
        f"scores R2={base_scores['r2']:.4f} on the same rows, so the model's "
        f"{model_scores['r2']:.4f} is barely distinguishable from a table "
        f"lookup. The MAE-vs-baseline check is what actually discriminates."
    )
    report.note(
        "the inherited random split was NOT inflating R-squared as suspected "
        "(held-out years gives essentially the same value); its configuration "
        "was nonetheless 19% worse than the median baseline until the target "
        "transform was fixed"
    )
    report.note(
        "global MAE is dominated by crops on a large scale (coconut median "
        "8,466 vs rice 2.2); it is a fair model-vs-baseline comparison but not "
        "an interpretable magnitude"
    )
    report.note("served output is a percentile within crop; no unit is ever attached")
    print(report.render())

    paths.ensure_artifacts_dir()
    benchmarks = _build_benchmarks(df)
    paths.YIELD_BENCHMARKS.write_text(
        json.dumps(
            {
                "unit": None,
                "unit_note": (
                    "The source yield column has no documented unit and its scale "
                    "differs per crop. These values are comparable only against "
                    "other rows for the same crop. Present as a relative position, "
                    "never as an absolute yield figure."
                ),
                "source": "datasets/datasets/farm_datasets/crop_yield.csv",
                "year_from": int(df["year"].min()),
                "year_to": int(df["year"].max()),
                "min_samples_per_band": MIN_SAMPLES_PER_BAND,
                "bands": benchmarks,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(benchmarks)} percentile bands -> {paths.YIELD_BENCHMARKS.relative_to(paths.REPO_ROOT)}")

    joblib.dump(
        {
            "model": model,
            "categorical": CATEGORICAL,
            "numeric": NUMERIC,
            "features": features,
            "target_transform": "log1p",
            "split_strategy": strategy,
            "trained_through_year": int(train["year"].max()),
            "passed_bar": report.passed,
            "scores": [model_scores, base_scores, ka_model, ka_base],
        },
        paths.YIELD_MODEL,
    )
    print(f"Saved -> {paths.YIELD_MODEL.relative_to(paths.REPO_ROOT)}")


if __name__ == "__main__":
    main()
