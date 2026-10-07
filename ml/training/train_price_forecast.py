"""Mandi price 13 weeks ahead for Karnataka, plus a seasonal outlook (model 18).

Run:
    python -m ml.training.train_price_forecast
    python -m ml.training.train_price_forecast --audit-only

Bar: MODEL_BARS.md section 9, 2026-09-24 entry "model 18". Per crop: test MAE
of log price at least 10% below persistence and no worse than seasonal-naive.
Pooled: direction accuracy at least 0.60 on moves of 5% or more. Crops that
pass ship; the rest fall back to the seasonal outlook, which has no bar.

## Pipeline

1. **Read** the yearly Agmarknet files for 2023-2026 (the 13 days of 2020 are
   an isolated fragment and are dropped), keeping only the commodities in
   `COMMODITIES`.
2. **Clean**: exact duplicates, min > max, modal outside [min, max], and
   modal more than 3x away from that commodity's all-India weekly median.
3. **Weekly series**: the median modal price per Karnataka district and for the
   state as a whole. A district series is modelled only if it has a price in
   at least 40% of training weeks.
4. **Features at forecast week t** use nothing after t. The target is the log
   change from t to t+13, and only weeks with an observed price are scored.
5. **Split by target week**: last 26 = test, the 26 before = validation, the
   rest = training. Model settings are chosen on validation, then the model is
   refitted on training + validation and the test fold is read once.
"""

from __future__ import annotations

import argparse
import json
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from ml import paths
from ml.evaluation import Report

# Dataset commodity name -> stable key, and the app crop it informs (None when
# the crop is not seeded in the app).
COMMODITIES = {
    "Paddy(Dhan)(Common)": ("paddy", "rice"),
    "Rice": ("rice", "rice"),
    "Ragi (Finger Millet)": ("ragi", "ragi"),
    "Maize": ("maize", "maize"),
    "Cotton": ("cotton", "cotton"),
    "Gur(Jaggery)": ("jaggery", "sugarcane"),
    "Wheat": ("wheat", None),
    "Bajra(Pearl Millet/Cumbu)": ("bajra", None),
    "Jowar(Sorghum)": ("jowar", None),
    "Soyabean": ("soyabean", None),
    "Arhar (Tur/Red Gram)(Whole)": ("arhar", None),
    "Groundnut": ("groundnut", None),
    "Bengal Gram(Gram)(Whole)": ("bengal_gram", None),
}
STATE = "Karnataka"
STATE_SERIES = "__state__"

HORIZON = 13
TEST_WEEKS = VAL_WEEKS = 26
DISTRICT_MIN_SHARE = 0.40
OUTLIER_FACTOR = 3.0
FFILL_LIMIT = 2
MOVE_THRESHOLD = np.log(1.05)

BAR_VS_PERSISTENCE = 0.90
BAR_DIRECTION = 0.60
SEED = 42

KEY = ["Arrival_Date", "State", "District", "Market", "Commodity", "Variety", "Grade"]


def _read() -> pd.DataFrame:
    root = paths.require(paths.PRICE_HISTORY_DIR)
    frames = []
    for year in (2023, 2024, 2025, 2026):
        for chunk in pd.read_csv(root / f"market_prices_{year}.csv", chunksize=1_000_000,
                                 usecols=KEY + ["Min_Price", "Max_Price", "Modal_Price"]):
            frames.append(chunk[chunk["Commodity"].isin(COMMODITIES)])
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["Arrival_Date"], format="%d/%m/%Y")
    return df


def _clean(df: pd.DataFrame, report: Report) -> pd.DataFrame:
    counts = {"read": len(df)}
    df = df.drop_duplicates(subset=KEY)
    counts["duplicates"] = counts["read"] - len(df)
    bad = (df["Min_Price"] > df["Max_Price"]) | (df["Modal_Price"] < df["Min_Price"]) | (
        df["Modal_Price"] > df["Max_Price"]) | (df["Modal_Price"] <= 0)
    counts["inconsistent"] = int(bad.sum())
    df = df[~bad].copy()
    df["week"] = df["date"].dt.to_period("W-SUN").dt.start_time
    national = df.groupby(["Commodity", "week"])["Modal_Price"].transform("median")
    ratio = df["Modal_Price"] / national
    outlier = (ratio > OUTLIER_FACTOR) | (ratio < 1 / OUTLIER_FACTOR)
    counts["outliers"] = int(outlier.sum())
    df = df[~outlier]
    df = df[df["State"] == STATE]
    counts["karnataka_rows_kept"] = len(df)
    print("Cleaning:", counts)
    report.note(f"cleaning (13 commodities, all India): {counts}")
    return df


def _weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Weekly median modal price: one column per (commodity key, district or state)."""
    df = df.assign(crop=df["Commodity"].map(lambda c: COMMODITIES[c][0]))
    district = df.groupby(["crop", "District", "week"])["Modal_Price"].median()
    state = df.groupby(["crop", "week"])["Modal_Price"].median()
    state.index = pd.MultiIndex.from_tuples([(c, STATE_SERIES, w) for c, w in state.index])
    combined = pd.concat([district, state])
    combined.index = combined.index.set_names(["crop", "District", "week"])
    series = combined.unstack(["crop", "District"])
    weeks = pd.date_range(series.index.min(), series.index.max(), freq="W-MON")
    return np.log(series.reindex(weeks))


def _split_weeks(weeks: pd.DatetimeIndex):
    test_start = weeks[-TEST_WEEKS]
    val_start = weeks[-TEST_WEEKS - VAL_WEEKS]
    return val_start, test_start


def _eligible(series: pd.DataFrame, val_start) -> list:
    training = series[series.index < val_start]
    share = training.notna().mean()
    keep = [col for col in series.columns if col[1] == STATE_SERIES or share[col] >= DISTRICT_MIN_SHARE]
    return keep


def _profile(series: pd.DataFrame, end) -> dict:
    """Month-of-year median, IQR and year count per series, from weeks before `end`."""
    window = series[series.index < end]
    out = {}
    for col in window.columns:
        s = window[col].dropna()
        if s.empty:
            continue
        frame = pd.DataFrame({"v": np.exp(s.values), "m": s.index.month, "y": s.index.year})
        stats = {}
        for month, g in frame.groupby("m"):
            if g["y"].nunique() >= 2:
                stats[int(month)] = {"median": float(g["v"].median()), "p25": float(g["v"].quantile(.25)),
                                     "p75": float(g["v"].quantile(.75)), "years": int(g["y"].nunique())}
        out[col] = stats
    return out


def _rows(series: pd.DataFrame, columns, profile) -> pd.DataFrame:
    """One row per (series, forecast week t) with features known at t and the target."""
    filled = series.ffill(limit=FFILL_LIMIT)
    weeks = series.index
    rows = []
    for col in columns:
        crop, district = col
        state = filled[(crop, STATE_SERIES)]
        own, raw = filled[col], series[col]
        prof = profile.get(col) or profile.get((crop, STATE_SERIES), {})
        med = {m: np.log(v["median"]) for m, v in prof.items()}
        frame = pd.DataFrame({
            "week": weeks,
            "crop": crop,
            "district": district,
            "is_state": district == STATE_SERIES,
            "now": own.values,
            "lag1": own.shift(1).values, "lag2": own.shift(2).values, "lag4": own.shift(4).values,
            "lag8": own.shift(8).values, "lag13": own.shift(13).values,
            "mean4": own.rolling(4, min_periods=2).mean().values,
            "mean13": own.rolling(13, min_periods=4).mean().values,
            "state_now": state.values, "state_lag4": state.shift(4).values, "state_lag13": state.shift(13).values,
            "target_week": weeks + pd.Timedelta(weeks=HORIZON),
            "future": raw.shift(-HORIZON).values,
            "sn_change": (own.shift(52 - HORIZON) - own.shift(52)).values,
        })
        frame["origin_month"] = frame["week"].dt.month
        frame["target_month"] = frame["target_week"].dt.month
        frame["season_delta"] = frame["target_month"].map(med) - frame["origin_month"].map(med)
        rows.append(frame)
    df = pd.concat(rows, ignore_index=True)
    df = df[df["now"].notna()]
    for c in ["lag1", "lag2", "lag4", "lag8", "lag13", "mean4", "mean13", "state_now", "state_lag4", "state_lag13"]:
        df[c] = df[c] - df["now"]  # relative to today's price, so crops share one scale
    df["change"] = df["future"] - df["now"]
    for name, month in (("origin", "origin_month"), ("target", "target_month")):
        df[f"{name}_sin"] = np.sin(2 * np.pi * df[month] / 12)
        df[f"{name}_cos"] = np.cos(2 * np.pi * df[month] / 12)
    return df


FEATURES = ["lag1", "lag2", "lag4", "lag8", "lag13", "mean4", "mean13", "state_now", "state_lag4",
            "state_lag13", "season_delta", "origin_sin", "origin_cos", "target_sin", "target_cos",
            "is_state", "crop_code"]
SETTINGS = {
    "shallow": dict(max_depth=3, learning_rate=0.05, max_iter=300, min_samples_leaf=40),
    "deeper": dict(max_depth=6, learning_rate=0.05, max_iter=400, min_samples_leaf=20),
}


def _model(setting: str, n_features: int):
    return HistGradientBoostingRegressor(loss="absolute_error", random_state=SEED,
                                         categorical_features=[n_features - 1], **SETTINGS[setting])


def _scores(frame: pd.DataFrame, predicted: np.ndarray) -> dict:
    truth = frame["change"].to_numpy()
    out = {"rows": len(frame), "mae": float(np.abs(predicted - truth).mean()),
           "persistence_mae": float(np.abs(truth).mean())}
    sn = frame["sn_change"].notna().to_numpy()
    out["sn_rows"] = int(sn.sum())
    out["mae_on_sn_rows"] = float(np.abs(predicted[sn] - truth[sn]).mean()) if sn.any() else float("nan")
    out["seasonal_naive_mae"] = float(np.abs(frame["sn_change"].to_numpy()[sn] - truth[sn]).mean()) if sn.any() else float("nan")
    moves = np.abs(truth) >= MOVE_THRESHOLD
    out["moves"] = int(moves.sum())
    out["direction_accuracy"] = float((np.sign(predicted[moves]) == np.sign(truth[moves])).mean()) if moves.any() else float("nan")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()
    started = time.time()

    report = Report("Mandi price 13 weeks ahead, Karnataka (model 18)")
    series = _weekly(_clean(_read(), report))
    val_start, test_start = _split_weeks(series.index)  # target weeks inside the data
    # Target-week boundaries translated back to forecast weeks.
    val_origin, test_origin = val_start - pd.Timedelta(weeks=HORIZON), test_start - pd.Timedelta(weeks=HORIZON)
    columns = _eligible(series, val_origin)
    districts = sorted({(c, d) for c, d in columns if d != STATE_SERIES})
    print(f"Weeks {series.index.min().date()} -> {series.index.max().date()} ({len(series)}); "
          f"target weeks: validation from {val_start.date()}, test from {test_start.date()}")
    print(f"Series modelled: {len(columns)} ({len(districts)} district series meeting the 40% rule + "
          f"{len(COMMODITIES)} state series)")
    for crop in sorted({c for c, _ in columns}):
        print(f"  {crop:12s} districts: {sorted(d for c, d in districts if c == crop) or '-'}")
    if args.audit_only:
        return

    feature_profile = _profile(series, val_origin)  # training weeks only
    rows = _rows(series, columns, feature_profile)
    crop_codes = {c: i for i, c in enumerate(sorted(COMMODITIES[k][0] for k in COMMODITIES))}
    rows["crop_code"] = rows["crop"].map(crop_codes)
    rows["is_state"] = rows["is_state"].astype(int)
    scored = rows[rows["change"].notna()]
    train = scored[scored["target_week"] < val_start]
    val = scored[(scored["target_week"] >= val_start) & (scored["target_week"] < test_start)]
    test = scored[scored["target_week"] >= test_start]
    print(f"Rows: train {len(train)}  val {len(val)}  test {len(test)}")

    val_results = {}
    for setting in SETTINGS:
        model = _model(setting, len(FEATURES)).fit(train[FEATURES], train["change"])
        val_results[setting] = _scores(val, model.predict(val[FEATURES]))
        v = val_results[setting]
        print(f"  val {setting:8s} MAE {v['mae']:.4f}  persistence {v['persistence_mae']:.4f}  "
              f"direction {v['direction_accuracy']:.3f}")
    chosen = min(val_results, key=lambda s: val_results[s]["mae"])
    print(f"Chosen on validation: {chosen}")

    fit = pd.concat([train, val])
    model = _model(chosen, len(FEATURES)).fit(fit[FEATURES], fit["change"])

    # Test, read once.
    predicted = model.predict(test[FEATURES])
    pooled = _scores(test, predicted)
    print(f"\nTEST pooled: rows {pooled['rows']}  MAE {pooled['mae']:.4f}  persistence {pooled['persistence_mae']:.4f}  "
          f"seasonal-naive {pooled['seasonal_naive_mae']:.4f} (on {pooled['sn_rows']} rows)  "
          f"direction {pooled['direction_accuracy']:.3f} on {pooled['moves']} moves >= 5%")
    report.check("pooled direction accuracy on >=5% moves (test)", BAR_DIRECTION, pooled["direction_accuracy"])

    per_crop, shipped = {}, []
    print(f"\n{'crop':12s} {'rows':>5s} {'MAE':>7s} {'persist':>7s} {'ratio':>6s} {'MAE(sn)':>8s} {'seas-nv':>7s} {'dir':>6s}")
    for crop in sorted(test["crop"].unique()):
        mask = (test["crop"] == crop).to_numpy()
        s = _scores(test[mask], predicted[mask])
        s["ratio_vs_persistence"] = s["mae"] / s["persistence_mae"]
        s["passes"] = bool(s["ratio_vs_persistence"] <= BAR_VS_PERSISTENCE and
                           (np.isnan(s["seasonal_naive_mae"]) or s["mae_on_sn_rows"] <= s["seasonal_naive_mae"]))
        per_crop[crop] = s
        print(f"{crop:12s} {s['rows']:5d} {s['mae']:7.4f} {s['persistence_mae']:7.4f} {s['ratio_vs_persistence']:6.3f} "
              f"{s['mae_on_sn_rows']:8.4f} {s['seasonal_naive_mae']:7.4f} {s['direction_accuracy']:6.3f}  "
              f"{'PASS' if s['passes'] else 'fail'}")
        if s["passes"]:
            shipped.append(crop)
    report.note(f"crops passing their per-crop bar: {shipped or 'none'}")
    report.note("test = 26 target weeks with overlapping 13-week horizons: correlated, about half a season")
    if not report.passed:
        shipped = []
    report.check("crops that ship", 1, len(shipped))
    print(report.render())

    # Seasonal outlook from training + validation weeks (not test).
    outlook = _profile(series, test_origin)
    coverage = []
    for col in columns:
        stats = outlook.get(col, {})
        actual = series.loc[series.index >= test_start, col].dropna()
        for week, value in actual.items():
            month = stats.get(week.month)
            if month:
                coverage.append(month["p25"] <= np.exp(value) <= month["p75"])
    iqr_coverage = float(np.mean(coverage)) if coverage else float("nan")
    print(f"Seasonal outlook: test-period actuals inside the historical IQR {iqr_coverage:.1%} "
          f"({len(coverage)} weeks; 50% if calibrated)")

    latest = series.ffill(limit=FFILL_LIMIT).iloc[-1]
    artifact = {
        "model": model,
        "features": FEATURES,
        "crop_codes": crop_codes,
        "commodities": COMMODITIES,
        "shipped_crops": shipped,
        "passed_bar": bool(shipped),
        "series_columns": columns,
        "feature_profile": feature_profile,
        "outlook": outlook,
        "recent_series": series.iloc[-60:],
        "data_end": str(series.index.max().date()),
        "horizon_weeks": HORIZON,
    }
    joblib.dump(artifact, paths.PRICE_FORECAST_MODEL)
    paths.PRICE_FORECAST_MODEL.with_name("price_forecast_metrics.json").write_text(json.dumps({
        "chosen": chosen, "validation": val_results, "test_pooled": pooled, "test_per_crop": per_crop,
        "shipped_crops": shipped, "outlook_iqr_coverage": iqr_coverage,
        "rows": {"train": len(train), "val": len(val), "test": len(test)},
        "data_end": artifact["data_end"], "latest_known_weeks": int(latest.notna().sum()),
        "minutes": round((time.time() - started) / 60, 1),
    }, indent=2, default=float) + "\n", encoding="utf-8")
    print(f"Saved -> {paths.PRICE_FORECAST_MODEL.relative_to(paths.REPO_ROOT)}")


if __name__ == "__main__":
    main()
