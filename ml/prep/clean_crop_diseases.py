"""datasets/crop disease/Indian_Crop_Disease_Dataset_Hindi_and_Marathi_NLP.csv
    -> crop_diseases.json + crop_disease_symptoms.json

The file is 2,231 rows but only 88 distinct (crop, disease) pairs — roughly 25
rows per disease, each a *different way a farmer might describe the same
disease*, paired with a remedy. It is a symptom->remedy corpus, not a disease
reference table, so it normalises into two levels:

- **crop_diseases** (88 rows) — what is stable per disease. Checked, not
  assumed: `cause` and `disease_type` are identical across all rows of every
  one of the 88 pairs.
- **crop_disease_symptoms** (2,231 rows) — what varies row to row:
  `question`, `remedy`, `severity_level`, `season`, `affected_plant_part` and
  `indian_state(major)` each differ within ~all pairs, so none of them is a
  property of the disease. Flattening them into the parent would mean picking
  one arbitrary remedy per disease and discarding two dozen others.

Confidence: the dataset cites no agronomic authority for its remedies, so
every row is seeded `unverified` and the serving layer prefixes it the same
way `services/rule_engine.py` prefixes unverified rules. Hindi and Marathi
text is passed through untouched; the app's other 8 locales have no
translation here and must fall back to English rather than machine-translate
agronomic advice.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict

from ml.prep.common import (
    DATASETS_DIR,
    SEEDED_CROPS,
    crop_display_name,
    crop_key,
    normalize_season,
    normalize_state,
    read_csv,
    write_seed_json,
)

SOURCE = (
    DATASETS_DIR
    / "crop disease"
    / "Indian_Crop_Disease_Dataset_Hindi_and_Marathi_NLP.csv"
)


def _stable_id(*parts: str) -> str:
    """Deterministic id from the row's natural key.

    Re-running the cleaner must produce the same ids, otherwise the seeder
    cannot be idempotent (it checks ids before inserting) and every re-run
    would duplicate the whole corpus.
    """
    digest = hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()
    return digest[:32]


def _clean(value: str | None) -> str:
    return " ".join((value or "").split())


def build() -> tuple[list[dict], list[dict]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)

    for raw in read_csv(SOURCE):
        key = crop_key(raw["crop_name_en"])
        disease = _clean(raw["disease_name_en"])
        if not key or not disease:
            continue
        grouped[(key, disease)].append(raw)

    diseases: list[dict] = []
    symptoms: list[dict] = []
    unresolved_states: set[str] = set()
    unresolved_seasons: set[str] = set()

    for (key, disease_name), records in sorted(grouped.items()):
        causes = {_clean(r["cause"]) for r in records}
        types = {_clean(r["disease_type"]) for r in records}
        if len(causes) != 1 or len(types) != 1:
            raise SystemExit(
                f"{key}/{disease_name}: cause or disease_type varies within the "
                f"pair (causes={causes}, types={types}) — these were verified "
                "stable across all 88 pairs; re-check before promoting them to "
                "the parent table"
            )

        disease_id = _stable_id(key, disease_name)
        diseases.append(
            {
                "id": disease_id,
                "crop_key": key,
                "crop_display_name": crop_display_name(key),
                "seeded_crop_name": SEEDED_CROPS.get(key),
                "disease_name_en": disease_name,
                "disease_name_hi": _clean(records[0]["disease_name_hi"]),
                "disease_name_mr": _clean(records[0]["disease_name_mr"]),
                "disease_type": types.pop(),
                "cause": causes.pop(),
                "symptom_count": len(records),
            }
        )

        for record in records:
            question = _clean(record["question_en"])
            remedy = _clean(record["remedy_en"])
            if not question or not remedy:
                continue

            state = None
            raw_state = _clean(record["indian_state(major)"])
            if raw_state:
                state = normalize_state(raw_state)
                if state is None:
                    unresolved_states.add(raw_state)

            season = None
            raw_season = _clean(record["season"])
            if raw_season:
                season = normalize_season(raw_season)
                if season is None:
                    unresolved_seasons.add(raw_season)

            symptoms.append(
                {
                    "id": _stable_id(key, disease_name, question),
                    "disease_id": disease_id,
                    "question_en": question,
                    "question_hi": _clean(record["question_hi"]),
                    "question_mr": _clean(record["question_mr"]),
                    "remedy_en": remedy,
                    "remedy_hi": _clean(record["remedy_hi"]),
                    "remedy_mr": _clean(record["remedy_mr"]),
                    "severity_level": _clean(record["severity_level"]) or None,
                    "season": season,
                    "affected_plant_part": _clean(record["affected_plant_part"]) or None,
                    "major_state": state,
                }
            )

    # Distinct questions can repeat verbatim within a disease; the id is
    # derived from the text, so collapse rather than emit a duplicate key.
    deduped: dict[str, dict] = {}
    collisions = 0
    for row in symptoms:
        if row["id"] in deduped:
            collisions += 1
            continue
        deduped[row["id"]] = row
    symptoms = list(deduped.values())

    print(f"  {len(diseases)} diseases, {len(symptoms)} symptom rows")
    if collisions:
        print(f"  {collisions} duplicate symptom phrasings collapsed")
    if unresolved_states:
        print(f"  NOTE: states left null (unrecognised): {sorted(unresolved_states)}")
    if unresolved_seasons:
        print(f"  NOTE: seasons left null (unrecognised): {sorted(unresolved_seasons)}")

    matched = sorted({d["crop_key"] for d in diseases} & set(SEEDED_CROPS))
    print(f"  seeded crops covered: {matched}")

    return diseases, symptoms


def main() -> None:
    print(f"cleaning {SOURCE.name}")
    diseases, symptoms = build()
    write_seed_json("crop_diseases.json", diseases, describe="diseases")
    write_seed_json("crop_disease_symptoms.json", symptoms, describe="symptom rows")


if __name__ == "__main__":
    main()
