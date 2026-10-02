"""datasets/farm datasets/state_weather_data_1997_2020.csv
    -> state_climate_normals.json

Collapses 24 years of per-state annual weather into a climate normal plus a
spread. The spread is the point: `core/weather.py` already reports what the
weather *is*, and a normal without a range can't tell you whether today is
unusual. Consumers compare a live reading against `rainfall_p25/p75` to decide
if a season is genuinely dry, rather than against the mean alone.
"""

from __future__ import annotations

import statistics
from collections import defaultdict

from ml.prep.common import (
    DATASETS_DIR,
    normalize_state,
    percentile,
    read_csv,
    write_seed_json,
)

SOURCE = DATASETS_DIR / "farm datasets" / "state_weather_data_1997_2020.csv"


def build() -> list[dict]:
    by_state: dict[str, list[dict]] = defaultdict(list)
    unresolved: set[str] = set()

    for raw in read_csv(SOURCE):
        state = normalize_state(raw["state"])
        if state is None:
            unresolved.add(raw["state"])
            continue
        by_state[state].append(
            {
                "year": int(raw["year"]),
                "temp": float(raw["avg_temp_c"]),
                "rain": float(raw["total_rainfall_mm"]),
                "humidity": float(raw["avg_humidity_percent"]),
            }
        )

    if unresolved:
        raise SystemExit(f"unresolved states: {sorted(unresolved)}")

    rows: list[dict] = []
    for state, records in sorted(by_state.items()):
        rain = sorted(record["rain"] for record in records)
        years = [record["year"] for record in records]
        rows.append(
            {
                "state": state,
                "year_from": min(years),
                "year_to": max(years),
                "sample_years": len(records),
                "avg_temp_c": round(statistics.mean(r["temp"] for r in records), 2),
                "avg_humidity_percent": round(
                    statistics.mean(r["humidity"] for r in records), 2
                ),
                "avg_rainfall_mm": round(statistics.mean(rain), 2),
                "rainfall_p25_mm": round(percentile(rain, 0.25), 2),
                "rainfall_p75_mm": round(percentile(rain, 0.75), 2),
            }
        )

    return rows


def main() -> None:
    print(f"cleaning {SOURCE.name}")
    rows = build()
    write_seed_json("state_climate_normals.json", rows, describe="states")


if __name__ == "__main__":
    main()
