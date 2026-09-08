"""Soil-nutrient gap advice: crop target minus measured soil reading.

Deterministic, no model. The output is a *gap*, never a prescription — it
names which nutrient is short and by how much against the crop's target, and
stops there. Turning that into a product and a dose is out of scope by design,
matching the `agri_catalog` rule that catalog rows carry product identity only
with no baked-in dosage (see `models/crop_nutrient_target.py`).

The soil reading this compares against is usually a **state average**, not a
soil test (`services/soil_lookup.get_soil_nutrients`). That is a very coarse
input, so every result reports which source it used and carries a caveat, in
the same spirit as `services/rule_engine._UNVERIFIED_PREFIX`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.crop_nutrient_target import CropNutrientTarget

_CAVEAT = (
    "[Unverified guidance] Nutrient targets come from a dataset of unverified "
    "provenance, and the soil figures may be a state-wide average rather than "
    "a test of your field. Treat this as a prompt to get a soil test or ask "
    "your local agriculture officer, not as a fertiliser recommendation."
)

# Below this fraction of the target, a nutrient is called short. Deliberately
# generous: with a state-average soil reading, a 10% gap is well inside the
# noise and flagging it would be false precision.
_DEFICIT_FRACTION = Decimal("0.75")
_SURPLUS_FRACTION = Decimal("1.25")

Status = Literal["low", "adequate", "high"]


@dataclass(frozen=True)
class NutrientGap:
    nutrient: Literal["N", "P", "K", "pH"]
    measured: Decimal
    target: Decimal
    status: Status


@dataclass(frozen=True)
class FertilizerAdvice:
    crop_key: str
    display_name: str
    gaps: list[NutrientGap]
    soil_source: str
    caveat: str

    @property
    def shortfalls(self) -> list[NutrientGap]:
        return [gap for gap in self.gaps if gap.status == "low"]


def _status(measured: Decimal, target: Decimal) -> Status:
    if target <= 0:
        return "adequate"
    ratio = measured / target
    if ratio < _DEFICIT_FRACTION:
        return "low"
    if ratio > _SURPLUS_FRACTION:
        return "high"
    return "adequate"


def advise(
    db: Session,
    crop_key: str,
    *,
    n: Decimal | float | int,
    p: Decimal | float | int,
    k: Decimal | float | int,
    ph: Decimal | float | int | None = None,
    soil_source: str,
) -> FertilizerAdvice | None:
    """Compare a soil reading against a crop's nutrient targets.

    Returns None when the crop has no target row — 97 crops are covered, but
    Sugarcane (one of the five seeded crops) is not, so callers must handle
    the miss rather than assume every planting can be advised.
    """
    target = db.scalar(
        select(CropNutrientTarget).where(CropNutrientTarget.crop_key == crop_key)
    )
    if target is None:
        return None

    gaps = [
        NutrientGap("N", Decimal(str(n)), Decimal(target.target_n), _status(Decimal(str(n)), Decimal(target.target_n))),
        NutrientGap("P", Decimal(str(p)), Decimal(target.target_p), _status(Decimal(str(p)), Decimal(target.target_p))),
        NutrientGap("K", Decimal(str(k)), Decimal(target.target_k), _status(Decimal(str(k)), Decimal(target.target_k))),
    ]

    if ph is not None:
        measured_ph = Decimal(str(ph))
        target_ph = Decimal(str(target.target_ph))
        # pH is a log scale — a ratio test is meaningless on it. Half a unit
        # either way is the conventional "close enough" band.
        if measured_ph < target_ph - Decimal("0.5"):
            ph_status: Status = "low"
        elif measured_ph > target_ph + Decimal("0.5"):
            ph_status = "high"
        else:
            ph_status = "adequate"
        gaps.append(NutrientGap("pH", measured_ph, target_ph, ph_status))

    return FertilizerAdvice(
        crop_key=target.crop_key,
        display_name=target.display_name,
        gaps=gaps,
        soil_source=soil_source,
        caveat=_CAVEAT,
    )
