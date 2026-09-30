"""
ml/algorithms/market_price_prediction.py
One model per commodity (see train_market_price_model.py). Needs recent
price history for the specific market — this predicts "what will the
price be next, given recent prices", not "what is the price with zero
context", since lag/rolling features are what the model was trained on.
Pass a list of recent Modal_Price values (oldest first) and this computes
lag_1 / rolling_7 itself, rather than making the caller pre-compute them.
"""
import os as _os
BASE_DIR = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))  # -> .../ml, works regardless of where this project is placed
import joblib
import pandas as pd
from datetime import date
import os

MODEL_DIR = _os.path.join(BASE_DIR, "saved_models/market_price_models")
_cache = {}


def _load(commodity: str):
    key = commodity.lower()
    if key not in _cache:
        path = f"{MODEL_DIR}/{key}_price_model.pkl"
        if not os.path.exists(path):
            available = [f.replace("_price_model.pkl", "") for f in os.listdir(MODEL_DIR)]
            raise ValueError(f"No model for '{commodity}'. Available: {available}")
        _cache[key] = joblib.load(path)
    return _cache[key]


def predict_market_price(commodity: str, state: str, district: str, market: str,
                          recent_prices: list, target_date: date) -> dict:
    """
    recent_prices: most recent known Modal_Price values for this exact
    market, oldest first — at least 1 needed (lag_1), ideally 7+ for a
    meaningful rolling_7 average.
    """
    bundle = _load(commodity)
    model, features = bundle["model"], bundle["features"]

    lag_1 = recent_prices[-1]
    rolling_7 = sum(recent_prices[-7:]) / len(recent_prices[-7:])

    row = pd.DataFrame([{
        "STATE": state, "District Name": district, "Market Name": market,
        "lag_1": lag_1, "rolling_7": rolling_7,
        "month": target_date.month, "day_of_week": target_date.weekday(),
    }])[features]

    prediction = model.predict(row)[0]
    return {"predicted_modal_price": round(float(prediction), 2)}


if __name__ == "__main__":
    print(predict_market_price(
        "Potato", state="Uttar Pradesh", district="mainpuri", market="Bewar",
        recent_prices=[800, 810, 805, 795, 815, 820, 810],
        target_date=date(2025, 12, 10),
    ))
