"""Seed reference data: crops/varieties, agri input catalog, govt schemes.

Idempotent — checks each row's id before inserting, safe to re-run (e.g.
after adding a new row to one of the lists below). This is source-of-truth
data, versioned in the repo, not a throwaway one-off script.

Usage (from repo root, venv active):
    python -m backend.scripts.seed_reference_data

Sourcing notes:
- crops/agri_catalog: see backend/plan/task3.4-3.5.txt and the Task 3.4/3.5
  plan — agri_catalog is product identity only (ICAR-sourced), no baked-in
  dosage. Crop varieties are common cultivar names, not a verified claim.
- govt_schemes: PM-KISAN figures are from pmkisan.gov.in directly (high
  confidence). Krishi Bhagya Yojana's department/components are confirmed
  from raitamitra.karnataka.gov.in directly; its exact current-year subsidy
  percentage is NOT independently verified this session — stored as a range
  with an explicit "confirm at application_url" caveat rather than a bare
  number. See docs/govt-schemes-sourcing.md.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from backend.core.database import SessionLocal
from backend.models.agri_catalog import AgriCatalog, AgriCatalogCategory
from backend.models.agronomic_rule import AgronomicRule
from backend.models.crop import Crop, CropVariety
from backend.models.crop_growth_stage import CropGrowthStage, DataConfidence
from backend.models.location import Location
from backend.models.recommendation import RecommendationSeverity
from backend.models.scheme import GovtScheme

_SEED_DATA_DIR = Path(__file__).resolve().parent / "seed_data"

CROPS: list[dict] = [
    {"name": "Rice", "varieties": ["IR-64", "Jyothi"]},
    {"name": "Ragi (Finger Millet)", "varieties": ["GPU-28", "Indaf-9"]},
    {"name": "Maize", "varieties": ["NK-6240", "DHM-117"]},
    {"name": "Cotton", "varieties": ["Bunny Bt", "RCH-2"]},
    {"name": "Sugarcane", "varieties": ["Co 86032", "CoM 0265"]},
]

AGRI_CATALOG: list[dict] = [
    {
        "category": AgriCatalogCategory.fertilizer,
        "name": "Urea",
        "crops": ["Rice", "Ragi (Finger Millet)", "Cotton", "Sugarcane", "Maize"],
        "unit": "kg",
    },
    {
        "category": AgriCatalogCategory.fertilizer,
        "name": "DAP",
        "crops": ["Rice", "Ragi (Finger Millet)", "Cotton", "Sugarcane", "Maize"],
        "unit": "kg",
    },
    {
        "category": AgriCatalogCategory.fertilizer,
        "name": "MOP (Muriate of Potash)",
        "crops": ["Rice", "Ragi (Finger Millet)", "Cotton", "Sugarcane", "Maize"],
        "unit": "kg",
    },
    {
        "category": AgriCatalogCategory.fertilizer,
        "name": "Zinc Sulphate (ZnSO4)",
        "crops": ["Rice", "Maize"],
        "unit": "kg",
    },
    {
        "category": AgriCatalogCategory.herbicide,
        "name": "Atrazine",
        "crops": ["Maize"],
        "unit": "litre",
    },
    {
        "category": AgriCatalogCategory.herbicide,
        "name": "Pendimethalin",
        "crops": ["Cotton"],
        "unit": "litre",
    },
    {
        "category": AgriCatalogCategory.herbicide,
        "name": "Quizalofop-p-ethyl",
        "crops": ["Cotton"],
        "unit": "ml",
    },
    {
        "category": AgriCatalogCategory.pesticide,
        "name": "Emamectin Benzoate 5SG",
        "crops": ["Maize"],
        "unit": "g",
    },
    {
        "category": AgriCatalogCategory.fungicide,
        "name": "Carbendazim",
        "crops": ["Maize"],
        "unit": "g",
    },
    {
        "category": AgriCatalogCategory.biocontrol,
        "name": "Trichoderma viride",
        "crops": ["Cotton", "Sugarcane"],
        "unit": "g",
    },
]

GROWTH_STAGE_SOURCE = (
    "General agronomy sources (LSU AgCenter, MAS Seeds, Bayer CropScience, "
    "Farmonaut, TNAU, ICAR-AICRP Small Millets summaries) — not a single "
    "ICAR/KVK document pulled per row this session, hence confidence=low "
    "throughout. See Phase 4 plan notes."
)

# crop name, stage_name, stage_order, start day, end day. Names match
# agronomic_rules.stage_name exactly for the rows that reference them (see
# AGRONOMIC_RULES below) — stage-gating is a plain string comparison.
GROWTH_STAGES: list[tuple[str, str, int, int, int]] = [
    ("Rice", "Seedling", 1, 0, 20),
    ("Rice", "Vegetative (Tillering)", 2, 20, 45),
    ("Rice", "Panicle Initiation", 3, 45, 65),
    ("Rice", "Flowering (Heading)", 4, 65, 95),
    ("Rice", "Maturity (Ripening)", 5, 95, 130),
    ("Ragi (Finger Millet)", "Seedling Establishment (0-30 DAS)", 1, 0, 30),
    ("Ragi (Finger Millet)", "Vegetative/Tillering", 2, 30, 55),
    ("Ragi (Finger Millet)", "Flowering", 3, 55, 85),
    ("Ragi (Finger Millet)", "Maturity", 4, 85, 120),
    ("Maize", "Early Whorl (V2-V6)", 1, 10, 30),
    ("Maize", "Vegetative (V7+)", 2, 30, 55),
    ("Maize", "Tasseling-Silking", 3, 55, 70),
    ("Maize", "Grain Fill/Maturity", 4, 70, 115),
    ("Cotton", "Seedling/Vegetative", 1, 0, 35),
    ("Cotton", "Squaring to Boll Development", 2, 35, 70),
    ("Cotton", "Boll Development", 3, 70, 160),
    ("Sugarcane", "Germination-Tillering (0-120 DAS)", 1, 0, 120),
    ("Sugarcane", "Grand Growth Phase (~4th-8th month)", 2, 120, 240),
    ("Sugarcane", "Maturity/Ripening", 3, 240, 360),
]

# Mapped from docs/agronomic-rules-draft.csv into the schema refined for
# Task 4.1 (condition_field/operator/threshold_value nullable trio, not
# stage_name — see the Phase 4 plan). confidence: CSV's "MEDIUM" ->
# "medium" (COTTON_PBW_ETL only, the best-sourced row), everything else
# "low" — nothing in this batch reaches "verified".
AGRONOMIC_RULES: list[dict] = [
    {
        "rule_code": "RICE_IRRIGATION_CRITICAL_PANICLE",
        "crop": "Rice",
        "stage": "Panicle Initiation",
        "condition_field": None,
        "operator": None,
        "threshold": None,
        "severity": RecommendationSeverity.critical,
        "text": (
            "Rice is highly sensitive to water stress at panicle initiation "
            "— ensure standing water/irrigation within 1-2 days of reaching "
            "this stage to avoid yield loss."
        ),
        "confidence": DataConfidence.low,
        "source": "General ICAR rice Package of Practices guidance — not pulled from a specific document this session.",
    },
    {
        "rule_code": "RICE_STEM_BORER_SCOUT",
        "crop": "Rice",
        "stage": "Vegetative (Tillering)",
        "condition_field": "dead_hearts_percent",
        "operator": ">=",
        "threshold": 5,
        "severity": RecommendationSeverity.advisory,
        "text": (
            "Dead-heart incidence has crossed 5% — scout for yellow stem "
            "borer and consider need-based control per local KVK advisory."
        ),
        "confidence": DataConfidence.low,
        "source": "Commonly cited Indian rice IPM ETL (5% dead hearts vegetative / 2% white ears reproductive) — not pulled from a specific ICAR/KVK document this session.",
    },
    {
        "rule_code": "RAGI_IRRIGATION_ESTABLISHMENT",
        "crop": "Ragi (Finger Millet)",
        "stage": "Seedling Establishment (0-30 DAS)",
        "condition_field": None,
        "operator": None,
        "threshold": None,
        "severity": RecommendationSeverity.advisory,
        "text": (
            "Finger millet is most vulnerable to moisture stress during "
            "seedling establishment — provide life-saving irrigation if "
            "available and no rainfall in the past 7 days."
        ),
        "confidence": DataConfidence.low,
        "source": "General ICAR-AICRP Small Millets dryland guidance — not pulled from a specific document this session.",
    },
    {
        "rule_code": "RAGI_BLAST_DISEASE_WATCH",
        "crop": "Ragi (Finger Millet)",
        "stage": "Flowering",
        # Reinterpreted as a stage-only reminder — the draft's "warm humid
        # conditions" trigger was never a real numeric threshold (its own
        # operator: "advisory_condition" was a placeholder). See Phase 4 plan.
        "condition_field": None,
        "operator": None,
        "threshold": None,
        "severity": RecommendationSeverity.advisory,
        "text": (
            "Warm humid conditions during flowering favor finger millet "
            "blast (neck blast) — scout earheads and consider prophylactic "
            "fungicide per local KVK advisory."
        ),
        "confidence": DataConfidence.low,
        "source": "General ICAR-AICRP Small Millets blast-risk guidance — not a hard numeric threshold; genuinely needs local KVK sign-off before use.",
    },
    {
        "rule_code": "COTTON_PBW_ETL",
        "crop": "Cotton",
        "stage": "Boll Development",
        "condition_field": "pheromone_trap_moths_per_night_3day_avg",
        "operator": ">=",
        "threshold": 8,
        "severity": RecommendationSeverity.critical,
        "text": (
            "Pink bollworm trap catch has crossed the ICAR-CICR economic "
            "threshold (8 moths/trap/night for 3 consecutive nights) — "
            "initiate control measures immediately."
        ),
        "confidence": DataConfidence.medium,
        "source": "ICAR-CICR (Central Institute for Cotton Research) published ETL — confirmed via web search against multiple corroborating sources.",
    },
    {
        "rule_code": "COTTON_IRRIGATION_SQUARE_BOLL",
        "crop": "Cotton",
        "stage": "Squaring to Boll Development",
        "condition_field": None,
        "operator": None,
        "threshold": None,
        "severity": RecommendationSeverity.advisory,
        "text": (
            "Cotton water demand peaks from squaring through boll "
            "development — avoid moisture stress in this window."
        ),
        "confidence": DataConfidence.low,
        "source": "General ICAR cotton Package of Practices guidance — not pulled from a specific document this session.",
    },
    {
        "rule_code": "SUGARCANE_IRRIGATION_GRAND_GROWTH",
        "crop": "Sugarcane",
        "stage": "Grand Growth Phase (~4th-8th month)",
        "condition_field": None,
        "operator": None,
        "threshold": None,
        "severity": RecommendationSeverity.critical,
        "text": (
            "Grand growth phase is sugarcane's most water-sensitive period "
            "— irrigation deficit here has the largest yield impact of any "
            "stage."
        ),
        "confidence": DataConfidence.low,
        "source": "General ICAR sugarcane Package of Practices guidance — not pulled from a specific document this session.",
    },
    {
        "rule_code": "SUGARCANE_EARLY_SHOOT_BORER",
        "crop": "Sugarcane",
        "stage": "Germination-Tillering (0-120 DAS)",
        "condition_field": "deadheart_percent",
        "operator": ">=",
        "threshold": 10,
        "severity": RecommendationSeverity.advisory,
        "text": (
            "Early shoot borer dead-heart incidence has crossed 10% — "
            "scout and consider need-based control per local KVK advisory."
        ),
        "confidence": DataConfidence.low,
        "source": "Commonly cited Indian sugarcane IPM ETL — sources disagree in the 5-10% range; not pulled from a specific document this session.",
    },
    {
        "rule_code": "MAIZE_FAW_ETL",
        "crop": "Maize",
        "stage": "Early Whorl (V2-V6)",
        "condition_field": "percent_plants_with_whorl_damage",
        "operator": ">=",
        "threshold": 5,
        "severity": RecommendationSeverity.advisory,
        "text": (
            "Fall armyworm whorl damage has crossed 5% of plants "
            "(ICAR-IIMR action threshold) — scout closely and consider "
            "need-based control."
        ),
        "confidence": DataConfidence.low,
        "source": "ICAR-IIMR (2019)-cited action threshold — confirmed via web search; NOTE published literature ranges 5-30% across different sources/regions. Least settled number in this batch.",
    },
    {
        "rule_code": "MAIZE_IRRIGATION_TASSELING",
        "crop": "Maize",
        "stage": "Tasseling-Silking",
        "condition_field": None,
        "operator": None,
        "threshold": None,
        "severity": RecommendationSeverity.critical,
        "text": (
            "Maize is most drought-sensitive from tasseling through "
            "silking — a moisture deficit here causes the largest yield "
            "penalty of any growth stage."
        ),
        "confidence": DataConfidence.low,
        "source": "General ICAR maize Package of Practices guidance (broadly and consistently published) — not pulled from a specific document this session.",
    },
]

GOVT_SCHEMES: list[dict] = [
    {
        "scheme_name": "PM-KISAN (Pradhan Mantri Kisan Samman Nidhi)",
        "authority": "Department of Agriculture and Farmers Welfare, Government of India",
        "eligibility_criteria": {
            "land_holding": "Cultivable land-holding farmer family (self/spouse/minor children), land registered in the farmer's name",
            "exclusions": [
                "Institutional landholders",
                "Constitutional office holders (current/former)",
                "Government employees and pensioners (except Group D / Multi-Tasking Staff)",
                "Pensioners with monthly pension ≥ ₹10,000",
                "Income tax payers",
                "Licensed professionals (doctors, engineers, lawyers, chartered accountants, architects)",
            ],
        },
        "benefit_description": (
            "₹6,000/year, paid in three equal ₹2,000 installments via Direct "
            "Benefit Transfer to Aadhaar-seeded bank accounts."
        ),
        "application_url": "https://pmkisan.gov.in/",
        "active": True,
    },
    {
        "scheme_name": "Krishi Bhagya Yojana",
        "authority": "Department of Agriculture (KSDA), Government of Karnataka",
        "eligibility_criteria": {
            "target": "Dryland/rainfed farmers, primarily in low-and-medium-rainfall (450-850mm) taluks",
            "land_holding": "Minimum 1 acre",
            "category_note": "Subsidy tier depends on SC/ST vs. general category",
        },
        "benefit_description": (
            "Subsidy (80–90% depending on category — exact current-year "
            "percentage is set by an annual circular; confirm at application_url "
            "before advising a farmer) for dryland water-conservation "
            "infrastructure: farm ponds (Krishi Honda), polyhouses, shade nets, "
            "lift irrigation, diesel pump sets."
        ),
        "application_url": "https://raitamitra.karnataka.gov.in/info-2/Krishi+Bhagya+Scheme/en",
        "active": True,
    },
]


def _get_or_create_crop(db: Session, name: str) -> Crop:
    existing = db.query(Crop).filter_by(name=name).one_or_none()
    if existing:
        return existing
    crop = Crop(id=str(uuid.uuid4()), name=name, active=True)
    db.add(crop)
    db.flush()
    return crop


def seed_crops(db: Session) -> None:
    for entry in CROPS:
        crop = _get_or_create_crop(db, entry["name"])
        for variety_name in entry["varieties"]:
            exists = (
                db.query(CropVariety)
                .filter_by(crop_id=crop.id, name=variety_name)
                .one_or_none()
            )
            if not exists:
                db.add(
                    CropVariety(id=str(uuid.uuid4()), crop_id=crop.id, name=variety_name)
                )
    db.commit()


def seed_agri_catalog(db: Session) -> None:
    for entry in AGRI_CATALOG:
        exists = (
            db.query(AgriCatalog)
            .filter_by(name=entry["name"], category=entry["category"])
            .one_or_none()
        )
        if exists:
            continue
        db.add(
            AgriCatalog(
                id=str(uuid.uuid4()),
                category=entry["category"],
                name=entry["name"],
                crop_applicability=entry["crops"],
                unit_of_measure=entry["unit"],
                typical_dosage_per_hectare=None,
                active=True,
            )
        )
    db.commit()


def _get_crop_id(db: Session, name: str) -> str:
    crop = db.query(Crop).filter_by(name=name).one_or_none()
    if crop is None:
        raise RuntimeError(f"crop {name!r} not seeded yet — run seed_crops() first")
    return crop.id


def seed_growth_stages(db: Session) -> None:
    for crop_name, stage_name, order, start, end in GROWTH_STAGES:
        crop_id = _get_crop_id(db, crop_name)
        exists = (
            db.query(CropGrowthStage)
            .filter_by(crop_id=crop_id, stage_name=stage_name)
            .one_or_none()
        )
        if exists:
            continue
        db.add(
            CropGrowthStage(
                id=str(uuid.uuid4()),
                crop_id=crop_id,
                stage_name=stage_name,
                stage_order=order,
                typical_days_from_sowing_start=start,
                typical_days_from_sowing_end=end,
                confidence=DataConfidence.low,
                source=GROWTH_STAGE_SOURCE,
            )
        )
    db.commit()


def seed_agronomic_rules(db: Session) -> None:
    for entry in AGRONOMIC_RULES:
        exists = db.query(AgronomicRule).filter_by(rule_code=entry["rule_code"]).one_or_none()
        if exists:
            continue
        db.add(
            AgronomicRule(
                id=str(uuid.uuid4()),
                rule_code=entry["rule_code"],
                crop_id=_get_crop_id(db, entry["crop"]),
                stage_name=entry["stage"],
                condition_field=entry["condition_field"],
                operator=entry["operator"],
                threshold_value=entry["threshold"],
                severity=entry["severity"],
                recommendation_text=entry["text"],
                confidence=entry["confidence"],
                source=entry["source"],
                active=True,
            )
        )
    db.commit()


def seed_govt_schemes(db: Session) -> None:
    for entry in GOVT_SCHEMES:
        exists = (
            db.query(GovtScheme).filter_by(scheme_name=entry["scheme_name"]).one_or_none()
        )
        if exists:
            continue
        db.add(
            GovtScheme(
                id=str(uuid.uuid4()),
                scheme_name=entry["scheme_name"],
                authority=entry["authority"],
                eligibility_criteria=entry["eligibility_criteria"],
                benefit_description=entry["benefit_description"],
                application_url=entry["application_url"],
                active=entry["active"],
            )
        )
    db.commit()


def seed_locations(db: Session) -> None:
    """State/district reference for the onboarding pickers. Source of truth is
    seed_data/locations.json (moved server-side from the frontend bundle).
    Idempotent on (state, district)."""
    raw = json.loads((_SEED_DATA_DIR / "locations.json").read_text(encoding="utf-8"))
    existing = {
        (state, district)
        for state, district in db.query(Location.state, Location.district).all()
    }
    for entry in raw:
        state = entry["state"]
        for district in entry["districts"]:
            if (state, district) in existing:
                continue
            db.add(
                Location(
                    id=str(uuid.uuid4()),
                    state=state,
                    district=district,
                    active=True,
                )
            )
    db.commit()


def main() -> None:
    db = SessionLocal()
    try:
        seed_crops(db)
        seed_agri_catalog(db)
        seed_growth_stages(db)
        seed_agronomic_rules(db)
        seed_govt_schemes(db)
        seed_locations(db)
    finally:
        db.close()

    db = SessionLocal()
    try:
        print(f"crops: {db.query(Crop).count()}")
        print(f"crop_varieties: {db.query(CropVariety).count()}")
        print(f"agri_catalog: {db.query(AgriCatalog).count()}")
        print(f"crop_growth_stages: {db.query(CropGrowthStage).count()}")
        print(f"agronomic_rules: {db.query(AgronomicRule).count()}")
        print(f"govt_schemes: {db.query(GovtScheme).count()}")
        print(f"locations: {db.query(Location).count()}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
