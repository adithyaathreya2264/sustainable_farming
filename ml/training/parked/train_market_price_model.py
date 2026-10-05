"""
ml/training/train_market_price_model.py

Algorithm: Gradient-boosted trees (XGBoost) per commodity, on engineered
time features — NOT classical ARIMA. Reasoning: the data is a panel
(many markets x many dates), not a single clean time series, and each
market/state adds real signal (a Nashik onion price differs structurally
from a Kolkata one). A boosted-tree model can use state/market as
categorical features AND lag/rolling/calendar features in one model,
which plain ARIMA per-series can't do without building hundreds of
separate models (one per market). One model per COMMODITY (not one
global model) because price dynamics genuinely differ by crop — see the
class-imbalance note in the README.

Feature engineering: for each (state, market, commodity) series, sorted
by date, we build lag-1 and rolling-7-period average price, plus
calendar features (month, day-of-week). Rows with no history yet (first
observation per series) are dropped rather than filled with zeros, since
a fabricated lag value would be actively misleading.
"""
import os as _os
BASE_DIR = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))  # -> .../ml, works regardless of where this project is placed
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
import xgboost as xgb
import joblib
import os

DATA_PATH = _os.path.join(BASE_DIR, "datasets/Agriculture_price_dataset.csv")
MODEL_DIR = _os.path.join(BASE_DIR, "saved_models/market_price_models")
os.makedirs(MODEL_DIR, exist_ok=True)

CATEGORICAL = ["STATE", "District Name", "Market Name"]


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Price Date"] = pd.to_datetime(df["Price Date"], format="%m/%d/%Y")
    df = df.sort_values(["STATE", "District Name", "Market Name", "Price Date"])

    group_keys = ["STATE", "District Name", "Market Name"]
    df["lag_1"] = df.groupby(group_keys)["Modal_Price"].shift(1)
    df["rolling_7"] = (
        df.groupby(group_keys)["Modal_Price"]
        .transform(lambda s: s.shift(1).rolling(7, min_periods=1).mean())
    )
    df["month"] = df["Price Date"].dt.month
    df["day_of_week"] = df["Price Date"].dt.dayofweek

    df = df.dropna(subset=["lag_1", "rolling_7"])
    return df


def train_one_commodity(df: pd.DataFrame, commodity: str):
    sub = df[df["Commodity"] == commodity].copy()

    # Drop obvious data-entry-error outliers (e.g. a handful of Onion rows
    # at Rs. 460,000/quintal) using a percentile cap rather than a fixed
    # threshold, so this works sensibly across commodities with very
    # different price scales.
    lower, upper = sub["Modal_Price"].quantile([0.005, 0.995])
    before = len(sub)
    sub = sub[(sub["Modal_Price"] >= lower) & (sub["Modal_Price"] <= upper)]
    dropped = before - len(sub)

    sub = build_features(sub)

    if len(sub) < 100:
        print(f"  skipping {commodity} — only {len(sub)} usable rows after lag features")
        return None

    features = CATEGORICAL + ["lag_1", "rolling_7", "month", "day_of_week"]
    X, y = sub[features], sub["Modal_Price"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    preprocessor = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
    ], remainder="passthrough")

    model = Pipeline([
        ("preprocess", preprocessor),
        ("regressor", xgb.XGBRegressor(
            n_estimators=250, max_depth=6, learning_rate=0.08, random_state=42
        )),
    ])
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    r2 = r2_score(y_test, preds)
    print(f"  {commodity}: MAE={mae:.1f}  R^2={r2:.3f}  (n={len(sub)}, dropped {dropped} outliers, price range {y.min():.0f}-{y.max():.0f})")

    path = f"{MODEL_DIR}/{commodity.lower()}_price_model.pkl"
    joblib.dump({"model": model, "features": features}, path)
    return path


def main():
    df = pd.read_csv(DATA_PATH)
    for commodity in sorted(df["Commodity"].unique()):
        train_one_commodity(df, commodity)


if __name__ == "__main__":
    main()
