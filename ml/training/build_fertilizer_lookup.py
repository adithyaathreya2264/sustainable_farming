"""Crop -> ideal N/P/K and acceptable pH range. A lookup, not a model.

Run:  python -m ml.training.build_fertilizer_lookup

## Why there is no model here

Kept from the inherited reasoning, which is correct: inspecting `Fertilizer.csv`
shows N, P and K are a *single fixed value per crop* (Rice is always N=80,
P=40, K=40 across every one of its rows). Only pH varies, as a small sweep of
acceptable values rather than measurement noise. There is no learnable pattern
beyond "look up the crop". Training a regressor on this would be an expensive
way to memorise a dictionary.

## What changed: the constancy is asserted, not assumed

The inherited version took `group["N"].iloc[0]` — the first row's value —
silently. That is only correct *if* N/P/K really are constant within a crop,
and nothing checked. If a refreshed dump ever varied them, this would quietly
fabricate a nutrient target that no row in the source actually states, and
would keep doing so indefinitely.

`ml/prep/clean_fertilizer_targets.py` already solved this properly: it asserts
the constancy and fails loudly otherwise. That assertion is not hypothetical
insurance — it previously caught two real crop-alias bugs in this repo, where
coriander leaf was being merged with coriander seed (N 10 vs 90) and mustard
with rapeseed (N 100 vs 50). Collapsing those would have produced a confident,
wrong fertiliser target for four crops.

So this build now asserts first and collapses second.

## What changed: keyed by crop_key, and the pH range is kept

Two things are merged from the two prior implementations:

- **From `ml/prep`**: the constancy assertion, and keying rows by `crop_key()`
  so the output speaks the same crop vocabulary as the rest of the app rather
  than raw source spellings like `Jowar(Sorghum)`.
- **From the inherited version**: emitting `ph_min`/`ph_max` rather than a
  single median pH. `fertilizer_recommendation.py` needs the range to say
  "too acidic" or "too alkaline"; a median alone cannot express a tolerance
  band, and every value in the sweep is a real acceptable value for the crop.

## Known gap

`Fertilizer.csv` has no sugarcane row. Sugarcane is one of the app's five
seeded crops, so one of them has no nutrient target and the serving layer must
handle its absence rather than assume coverage.
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict

import pandas as pd

from ml import paths
from ml.evaluation import Report
from ml.prep.common import SEEDED_CROPS, crop_display_name, crop_key


def main() -> None:
    df = pd.read_csv(paths.require(paths.FERTILIZER_CSV))
    report = Report("Fertilizer targets (lookup)")

    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in df.to_dict("records"):
        key = crop_key(str(record["Crop"]))
        if key is None:
            continue
        grouped[key].append(record)

    lookup: dict[str, dict] = {}
    violations: list[str] = []

    for key, records in sorted(grouped.items()):
        # The assertion. Every row for a crop must agree on N/P/K.
        distinct = {(r["N"], r["P"], r["K"]) for r in records}
        if len(distinct) != 1:
            violations.append(
                f"{key!r}: {len(distinct)} distinct N/P/K combinations {sorted(distinct)}"
            )
            continue

        nitrogen, phosphorus, potassium = distinct.pop()
        ph_values = [float(r["pH"]) for r in records]
        lookup[key] = {
            "crop_key": key,
            "display_name": crop_display_name(key),
            "is_seeded_crop": key in SEEDED_CROPS,
            "N": float(nitrogen),
            "P": float(phosphorus),
            "K": float(potassium),
            "ph_min": round(min(ph_values), 2),
            "ph_max": round(max(ph_values), 2),
            "ph_median": round(statistics.median(ph_values), 2),
            "source_rows": len(records),
        }

    if violations:
        # Loud, and fatal. Collapsing a crop whose rows disagree would invent a
        # nutrient target, which is worse than having none.
        print("\nN/P/K CONSTANCY ASSERTION FAILED:")
        for line in violations:
            print(f"  {line}")
        raise SystemExit(
            "Refusing to build the lookup: collapsing these crops would fabricate "
            "a nutrient target no source row states. Fix the crop aliases in "
            "ml/prep/common.py before rebuilding."
        )

    print(f"{len(lookup)} crops, collapsed from {len(df)} rows")
    print("N/P/K constancy assertion passed for every crop")

    missing = sorted(set(SEEDED_CROPS) - set(lookup))
    if missing:
        print(f"NOTE: no nutrient target for seeded crop(s): {missing}")
        report.note(f"no nutrient target exists for seeded crop(s): {missing}")

    covered = sorted(k for k in lookup if lookup[k]["is_seeded_crop"])
    print(f"seeded crops covered: {covered}")

    report.check("N/P/K constancy assertion", 1.0, 1.0)
    report.note(
        "this is a lookup table, not a model - N/P/K are fixed per crop in the "
        "source and only pH varies"
    )
    report.note(
        "Fertilizer.csv is synthetically expanded (97 crops x ~19 near-duplicate "
        "rows); the collapse is lossless only because of the assertion above"
    )
    print(report.render())

    paths.ensure_artifacts_dir()
    paths.FERTILIZER_TARGETS.write_text(
        json.dumps(lookup, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"\nSaved -> {paths.FERTILIZER_TARGETS.relative_to(paths.REPO_ROOT)}")


if __name__ == "__main__":
    main()
