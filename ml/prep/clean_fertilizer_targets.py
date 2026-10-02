"""datasets/soil datasets/2/Fertilizer.csv -> crop_nutrient_targets.json

The raw file is 97 crops x 19 near-duplicate rows: N/P/K are identical across
a crop's 19 rows and only pH is jittered (Rice: 5.32-5.68 around 5.5). It
reads as a synthetically expanded table, so this cleaner collapses it back to
one row per crop and takes the median pH. The N/P/K constancy is *asserted*,
not assumed — if a refreshed dump ever varies them, collapsing would quietly
invent a number, so the run fails loudly instead.

These are crop nutrient *targets*, not fertiliser doses. The gap between a
target and a soil reading is the whole feature; converting that gap into a
product and a quantity is deliberately not done here (see the agri_catalog
"product identity only, no baked-in dosage" rule).
"""

from __future__ import annotations

import statistics
from collections import defaultdict

from ml.prep.common import (
    DATASETS_DIR,
    SEEDED_CROPS,
    crop_display_name,
    crop_key,
    read_csv,
    write_seed_json,
)

SOURCE = DATASETS_DIR / "soil datasets" / "2" / "Fertilizer.csv"


def build() -> list[dict]:
    by_crop: dict[str, list[dict[str, str]]] = defaultdict(list)
    for raw in read_csv(SOURCE):
        key = crop_key(raw["Crop"])
        if key is None:
            continue
        by_crop[key].append(raw)

    rows: list[dict] = []
    for key, records in sorted(by_crop.items()):
        npk = {(r["N"], r["P"], r["K"]) for r in records}
        if len(npk) != 1:
            raise SystemExit(
                f"crop {key!r} has varying N/P/K across its rows ({sorted(npk)}) — "
                "collapsing would fabricate a target; fix the cleaner before seeding"
            )
        nitrogen, phosphorus, potassium = npk.pop()
        ph_values = [float(r["pH"]) for r in records]
        rows.append(
            {
                "crop_key": key,
                "display_name": crop_display_name(key),
                "seeded_crop_name": SEEDED_CROPS.get(key),
                "target_n": int(nitrogen),
                "target_p": int(phosphorus),
                "target_k": int(potassium),
                "target_ph": round(statistics.median(ph_values), 2),
                "source_rows": len(records),
            }
        )

    return rows


def main() -> None:
    print(f"cleaning {SOURCE.name}")
    rows = build()
    matched = [row for row in rows if row["seeded_crop_name"]]
    print(f"  {len(matched)}/{len(SEEDED_CROPS)} seeded crops have a nutrient target")
    missing = set(SEEDED_CROPS) - {row["crop_key"] for row in rows}
    if missing:
        print(f"  NOTE: no target for seeded crop(s): {sorted(missing)}")
    write_seed_json("crop_nutrient_targets.json", rows, describe="crops")


if __name__ == "__main__":
    main()
