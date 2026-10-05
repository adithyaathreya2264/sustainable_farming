"""
ml/training/build_city_climatology.py

NOT a trained model — same reasoning as build_fertilizer_lookup.py. This
is hourly historical weather (96,432 rows per city, 2009-2020+): raw
observations, not labeled examples of anything to predict. Forcing a
supervised model onto it (e.g. "predict tomorrow's temp from today's")
would be a legitimate ML task, but a different one than what this data
is naturally suited for here — which is what your frontend's weather.ts
service and Task 1.7's Weather API fallback actually need: "what's
typical for this city in this month", a climatology lookup.

This aggregates the 8 cities' hourly data into monthly climate normals
(avg temp, avg humidity, avg rainfall) — a legitimate reference artifact,
not a disguised lookup pretending to be ML.

If you want an actual forecasting model from this data (e.g. next-day
temperature prediction), that's a real, different, buildable task — ask
and I'll build train_weather_forecast_model.py separately.
"""
import os as _os
BASE_DIR = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))  # -> .../ml, works regardless of where this project is placed
import pandas as pd
import json
import glob
import os

SRC_DIR = _os.path.join(BASE_DIR, "datasets/city_weather")
OUT_PATH = _os.path.join(BASE_DIR, "saved_models/city_climatology.json")


def main():
    climatology = {}
    for path in sorted(glob.glob(f"{SRC_DIR}/*.csv")):
        city = os.path.splitext(os.path.basename(path))[0]
        df = pd.read_csv(path)
        df["date_time"] = pd.to_datetime(df["date_time"])
        df["month"] = df["date_time"].dt.month

        monthly = df.groupby("month").agg(
            avg_temp_c=("tempC", "mean"),
            avg_humidity_percent=("humidity", "mean"),
            avg_rainfall_mm=("precipMM", "mean"),
        ).round(2)

        climatology[city] = monthly.to_dict(orient="index")
        print(f"{city}: {len(df)} hourly rows -> 12 monthly averages")

    with open(OUT_PATH, "w") as f:
        json.dump(climatology, f, indent=2)
    print(f"Saved -> {OUT_PATH}")
    print("Sample (Bengaluru, June):", climatology.get("bengaluru", {}).get(6))


if __name__ == "__main__":
    main()
