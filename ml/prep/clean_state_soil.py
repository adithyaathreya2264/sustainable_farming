"""datasets/farm datasets/state_soil_data.csv -> state_soil_baseline.json

One N/P/K/pH row per state. This is a *state-wide average*, nowhere near a
soil test — it exists to pre-fill a field form and to give the crop
recommender something to work with when the farmer has no soil report. Every
consumer must surface it as an estimate, never as a measurement.
"""

from __future__ import annotations

from ml.prep.common import (
    DATASETS_DIR,
    normalize_state,
    read_csv,
    write_seed_json,
)

SOURCE = DATASETS_DIR / "farm datasets" / "state_soil_data.csv"


def build() -> list[dict]:
    rows: list[dict] = []
    unresolved: list[str] = []

    for raw in read_csv(SOURCE):
        state = normalize_state(raw["state"])
        if state is None:
            unresolved.append(raw["state"])
            continue
        rows.append(
            {
                "state": state,
                "n": int(raw["N"]),
                "p": int(raw["P"]),
                "k": int(raw["K"]),
                "ph": float(raw["pH"]),
            }
        )

    rows.sort(key=lambda row: row["state"])

    if unresolved:
        raise SystemExit(
            f"{len(unresolved)} state(s) did not resolve against locations.json: "
            f"{sorted(set(unresolved))}"
        )

    seen = {row["state"] for row in rows}
    if len(seen) != len(rows):
        raise SystemExit("duplicate state rows in state_soil_data.csv")

    return rows


def main() -> None:
    print(f"cleaning {SOURCE.name}")
    rows = build()
    write_seed_json("state_soil_baseline.json", rows, describe="states")


if __name__ == "__main__":
    main()
