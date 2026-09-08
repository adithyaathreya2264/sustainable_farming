"""Seed the dataset-derived reference tables from `seed_data/*.json`.

Usage (from repo root, venv active):
    python -m ml.prep.run_all            # raw datasets/ -> seed_data/*.json
    python -m backend.scripts.seed_datasets

Kept separate from `seed_reference_data.py` on purpose. That script seeds
data this repo authored and stands behind (crops, catalog, schemes, with
sourcing notes per row). This one seeds ~6,500 rows derived from third-party
datasets of **unverified provenance** (see `datasets/README.md`) — a different
confidence story, a different volume, and a different refresh cycle.

## Why this syncs rather than skipping

`seed_reference_data.py` is insert-only: it checks a natural key and skips
what exists, which is right for hand-curated rows that only ever get appended
to. These tables are *regenerated* — fix a crop alias in `ml/prep/common.py`,
re-run the cleaners, and rows legitimately change or disappear. Insert-only
seeding would leave the stale ones behind forever and quietly serve them.

So each table is synced: insert new rows, update changed ones, delete rows no
longer present in the artifact. Nothing in the schema references these tables
by id, so deleting a row is safe. Re-running with unchanged artifacts is a
no-op, which is the property that makes it safe to run in any environment.
"""

from __future__ import annotations

import json
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Callable, Iterable

from sqlalchemy.orm import Session

from backend.core.database import SessionLocal
from backend.models.base import Base
from backend.models.crop_disease import CropDisease, CropDiseaseSymptom
from backend.models.crop_nutrient_target import CropNutrientTarget
from backend.models.market_price import MarketPrice
from backend.models.state_baseline import SoilBaseline, StateClimateNormal
from backend.models.yield_benchmark import YieldBenchmark

_SEED_DATA_DIR = Path(__file__).resolve().parent / "seed_data"


def _load(filename: str):
    path = _SEED_DATA_DIR / filename
    if not path.exists():
        raise SystemExit(
            f"missing {path.name} — run `python -m ml.prep.run_all` first"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _equal(current: object, value: object) -> bool:
    """Compare a persisted column value against an artifact value.

    A plain `!=` reports a difference on every run for `Numeric` columns:
    MySQL hands back `Decimal("6.90")` where the artifact holds `6.9`, and
    the string forms differ too. Comparing numerics as normalised `Decimal`
    is what makes a re-seed with unchanged artifacts a true no-op instead of
    rewriting several thousand rows each time.
    """
    if current is None or value is None:
        return current is None and value is None
    numeric = (Decimal, float, int)
    if (
        isinstance(current, numeric)
        and isinstance(value, numeric)
        and not isinstance(current, bool)
        and not isinstance(value, bool)
    ):
        return Decimal(str(current)).normalize() == Decimal(str(value)).normalize()
    return current == value


def _sync(
    db: Session,
    model: type[Base],
    rows: Iterable[dict],
    *,
    key: Callable[[dict], tuple],
    row_key: Callable[[object], tuple],
    label: str,
) -> None:
    """Insert/update/delete `model` rows so the table matches `rows` exactly.

    `key` derives the natural key from an artifact dict; `row_key` derives the
    same key from a persisted object. They are separate because the artifact
    and the column names don't always line up.
    """
    desired = {key(row): row for row in rows}
    existing = {row_key(obj): obj for obj in db.query(model).all()}

    inserted = updated = deleted = 0

    for natural_key, row in desired.items():
        obj = existing.get(natural_key)
        if obj is None:
            values = dict(row)
            values.setdefault("id", str(uuid.uuid4()))
            db.add(model(**values))
            inserted += 1
            continue
        changed = False
        for field, value in row.items():
            if field == "id":
                continue
            current = getattr(obj, field)
            if not _equal(current, value):
                setattr(obj, field, value)
                changed = True
        if changed:
            updated += 1

    for natural_key, obj in existing.items():
        if natural_key not in desired:
            db.delete(obj)
            deleted += 1

    db.commit()
    print(
        f"  {label}: {inserted} inserted, {updated} updated, {deleted} deleted "
        f"({len(desired)} total)"
    )


def seed_soil_baselines(db: Session) -> None:
    rows = [
        {"state": r["state"], "n": r["n"], "p": r["p"], "k": r["k"], "ph": r["ph"]}
        for r in _load("state_soil_baseline.json")
    ]
    _sync(
        db,
        SoilBaseline,
        rows,
        key=lambda r: (r["state"],),
        row_key=lambda o: (o.state,),
        label="soil_baselines",
    )


def seed_climate_normals(db: Session) -> None:
    fields = (
        "state",
        "year_from",
        "year_to",
        "sample_years",
        "avg_temp_c",
        "avg_humidity_percent",
        "avg_rainfall_mm",
        "rainfall_p25_mm",
        "rainfall_p75_mm",
    )
    rows = [
        {field: r[field] for field in fields}
        for r in _load("state_climate_normals.json")
    ]
    _sync(
        db,
        StateClimateNormal,
        rows,
        key=lambda r: (r["state"],),
        row_key=lambda o: (o.state,),
        label="state_climate_normals",
    )


def seed_nutrient_targets(db: Session) -> None:
    fields = (
        "crop_key",
        "display_name",
        "seeded_crop_name",
        "target_n",
        "target_p",
        "target_k",
        "target_ph",
    )
    rows = [
        {field: r[field] for field in fields}
        for r in _load("crop_nutrient_targets.json")
    ]
    _sync(
        db,
        CropNutrientTarget,
        rows,
        key=lambda r: (r["crop_key"],),
        row_key=lambda o: (o.crop_key,),
        label="crop_nutrient_targets",
    )


def seed_yield_benchmarks(db: Session) -> None:
    meta = _load("crop_yield_benchmarks_meta.json")
    rows = []
    for r in _load("crop_yield_benchmarks.json"):
        rows.append(
            {
                "crop_key": r["crop_key"],
                "display_name": r["display_name"],
                "seeded_crop_name": r["seeded_crop_name"],
                "scope": r["scope"],
                "state": r["state"],
                "season": r["season"],
                "median": r["median"],
                "p25": r["p25"],
                "p75": r["p75"],
                "sample_count": r["sample_count"],
                # Stamped from the artifact's metadata so the caveat travels
                # with every row rather than living only in a README.
                "year_from": meta["year_from"],
                "year_to": meta["year_to"],
                "unit_note": meta["unit_note"],
            }
        )
    _sync(
        db,
        YieldBenchmark,
        rows,
        # scope is part of the key: the same crop+state exists at both
        # "state" scope (season NULL) and "state_season" scope.
        key=lambda r: (r["crop_key"], r["scope"], r["state"], r["season"]),
        row_key=lambda o: (o.crop_key, o.scope, o.state, o.season),
        label="yield_benchmarks",
    )


def seed_market_prices(db: Session) -> None:
    meta = _load("market_prices_meta.json")
    rows = []
    for r in _load("market_prices.json"):
        rows.append(
            {
                "state": r["state"],
                "district": r["district"],
                "district_canonical": r["district_canonical"],
                "market": r["market"],
                "commodity": r["commodity"],
                "commodity_key": r["commodity_key"],
                "variety": r["variety"] or None,
                "min_price": r["min_price"],
                "max_price": r["max_price"],
                "modal_price": r["modal_price"],
                "price_unit": meta["price_unit"],
                "snapshot_date": date.fromisoformat(r["arrival_date"]),
            }
        )
    _sync(
        db,
        MarketPrice,
        rows,
        key=lambda r: (
            r["state"],
            r["district"],
            r["market"],
            r["commodity"],
            r["variety"],
        ),
        row_key=lambda o: (o.state, o.district, o.market, o.commodity, o.variety),
        label="market_prices",
    )


def seed_crop_diseases(db: Session) -> None:
    """Diseases before symptoms — the child table FKs into the parent."""
    disease_fields = (
        "id",
        "crop_key",
        "crop_display_name",
        "seeded_crop_name",
        "disease_name_en",
        "disease_name_hi",
        "disease_name_mr",
        "disease_type",
        "cause",
        "symptom_count",
    )
    diseases = [
        {field: r[field] for field in disease_fields}
        for r in _load("crop_diseases.json")
    ]
    _sync(
        db,
        CropDisease,
        diseases,
        # The cleaner derives this id deterministically from
        # (crop_key, disease_name_en), so it *is* the natural key.
        key=lambda r: (r["id"],),
        row_key=lambda o: (o.id,),
        label="crop_diseases",
    )

    symptom_fields = (
        "id",
        "disease_id",
        "question_en",
        "question_hi",
        "question_mr",
        "remedy_en",
        "remedy_hi",
        "remedy_mr",
        "severity_level",
        "season",
        "affected_plant_part",
        "major_state",
    )
    symptoms = [
        {field: r[field] for field in symptom_fields}
        for r in _load("crop_disease_symptoms.json")
    ]
    _sync(
        db,
        CropDiseaseSymptom,
        symptoms,
        key=lambda r: (r["id"],),
        row_key=lambda o: (o.id,),
        label="crop_disease_symptoms",
    )


def main() -> None:
    db = SessionLocal()
    try:
        print("seeding dataset-derived reference tables")
        seed_soil_baselines(db)
        seed_climate_normals(db)
        seed_nutrient_targets(db)
        seed_yield_benchmarks(db)
        seed_market_prices(db)
        seed_crop_diseases(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
