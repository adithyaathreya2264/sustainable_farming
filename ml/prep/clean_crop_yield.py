"""datasets/farm datasets/crop_yield.csv -> crop_yield_benchmarks.json

Aggregates 19,689 crop/year/season/state rows into typical-yield bands at
three scopes, so the serving side can do the same 3-tier fallback that
`services/soil_lookup.py` already does for soil type:

    state_season  ->  state  ->  national

## The unit problem (read before displaying any of these numbers)

The source `yield` column has no documented unit, and two things about it are
established rather than assumed:

1. **It is not `production / area`.** Recomputing that disagrees with the
   stated `yield` in 13,663 of 19,689 rows (69%), so the column has been
   transformed by whoever assembled the dataset and cannot be re-derived.
2. **Its scale is crop-dependent.** Median yield is 8,466 for Coconut
   (plainly nuts/ha), 53 for Sugarcane and 2.2 for Rice (both plausible
   t/ha). There is no single unit across crops.

Within a single crop the values *are* consistent and agronomically sensible
(Rice p05-p95 = 1.01-3.56), so a crop's own distribution is a sound basis for
comparison. What is not sound is printing "2.6 t/acre" next to it — that would
attach a unit the data does not carry.

So every row here is emitted with `"unit": null` and the serving layer is
expected to present a *relative* answer ("your yield sits around the 60th
percentile for Rice in Karnataka, Kharif") rather than an absolute agronomic
figure. `unit_note` travels with the data so the caveat cannot be lost by
someone reading only the JSON.
"""

from __future__ import annotations

import statistics
from collections import defaultdict

from ml.prep.common import (
    DATASETS_DIR,
    SEEDED_CROPS,
    crop_display_name,
    crop_key,
    normalize_season,
    normalize_state,
    percentile,
    read_csv,
    write_seed_json,
)

SOURCE = DATASETS_DIR / "farm datasets" / "crop_yield.csv"

UNIT_NOTE = (
    "Unit is undocumented in the source dataset and differs per crop; these "
    "values are comparable only against other rows for the same crop. Present "
    "as a relative position, never as an absolute yield figure."
)

# A band needs enough observations to mean anything. Below this the median is
# noise dressed up as guidance, so the scope is dropped and the caller falls
# back to a wider one.
MIN_SAMPLES = 5


def _band(values: list[float]) -> dict:
    values = sorted(values)
    return {
        "median": round(statistics.median(values), 4),
        "p25": round(percentile(values, 0.25), 4),
        "p75": round(percentile(values, 0.75), 4),
        "sample_count": len(values),
    }


def build() -> dict:
    by_state_season: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    by_state: dict[tuple[str, str], list[float]] = defaultdict(list)
    by_crop: dict[str, list[float]] = defaultdict(list)
    years: dict[str, list[int]] = defaultdict(list)

    total = kept = 0
    dropped_yield = dropped_state = dropped_season = dropped_crop = 0

    for raw in read_csv(SOURCE):
        total += 1

        raw_yield = (raw.get("yield") or "").strip()
        if not raw_yield:
            dropped_yield += 1
            continue
        value = float(raw_yield)
        # Zero/negative yield is a missing observation recorded as a number,
        # not a real harvest of nothing — including it would drag every
        # median it touches downward.
        if value <= 0:
            dropped_yield += 1
            continue

        key = crop_key(raw["crop"])
        if key is None:
            dropped_crop += 1
            continue
        state = normalize_state(raw["state"])
        if state is None:
            dropped_state += 1
            continue
        season = normalize_season(raw["season"])
        if season is None:
            dropped_season += 1
            continue

        by_state_season[(key, state, season)].append(value)
        by_state[(key, state)].append(value)
        by_crop[key].append(value)
        years[key].append(int(raw["year"]))
        kept += 1

    rows: list[dict] = []

    for (key, state, season), values in sorted(by_state_season.items()):
        if len(values) < MIN_SAMPLES:
            continue
        rows.append(
            {
                "crop_key": key,
                "display_name": crop_display_name(key),
                "seeded_crop_name": SEEDED_CROPS.get(key),
                "scope": "state_season",
                "state": state,
                "season": season,
                **_band(values),
            }
        )

    for (key, state), values in sorted(by_state.items()):
        if len(values) < MIN_SAMPLES:
            continue
        rows.append(
            {
                "crop_key": key,
                "display_name": crop_display_name(key),
                "seeded_crop_name": SEEDED_CROPS.get(key),
                "scope": "state",
                "state": state,
                "season": None,
                **_band(values),
            }
        )

    for key, values in sorted(by_crop.items()):
        if len(values) < MIN_SAMPLES:
            continue
        rows.append(
            {
                "crop_key": key,
                "display_name": crop_display_name(key),
                "seeded_crop_name": SEEDED_CROPS.get(key),
                "scope": "national",
                "state": None,
                "season": None,
                **_band(values),
            }
        )

    all_years = [year for values in years.values() for year in values]
    payload = {
        "unit": None,
        "unit_note": UNIT_NOTE,
        "source": "datasets/farm datasets/crop_yield.csv",
        "year_from": min(all_years),
        "year_to": max(all_years),
        "min_samples_per_band": MIN_SAMPLES,
        "benchmarks": rows,
    }

    print(
        f"  {kept}/{total} rows kept "
        f"(dropped: yield {dropped_yield}, state {dropped_state}, "
        f"season {dropped_season}, crop {dropped_crop})"
    )
    scopes = defaultdict(int)
    for row in rows:
        scopes[row["scope"]] += 1
    print(f"  bands: {dict(scopes)}")
    return payload


def main() -> None:
    print(f"cleaning {SOURCE.name}")
    payload = build()
    write_seed_json(
        "crop_yield_benchmarks.json", payload["benchmarks"], describe="benchmark bands"
    )
    # The caveat metadata rides alongside so the seeder can stamp it onto rows.
    write_seed_json(
        "crop_yield_benchmarks_meta.json",
        {k: v for k, v in payload.items() if k != "benchmarks"},
        describe="metadata keys",
    )


if __name__ == "__main__":
    main()
