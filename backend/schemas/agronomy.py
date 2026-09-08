"""Response shapes for the yield-benchmark and fertiliser-gap endpoints.

`YieldBenchmarkOut` has no `unit` field, and that is intentional rather than
an omission — the source dataset's yield column carries no usable unit (see
`models/yield_benchmark.py`). `unit_note` is required so a client cannot
render `median` without having the caveat in hand, and `band` is the field a
UI should actually show.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class YieldBenchmarkOut(BaseModel):
    crop_key: str
    display_name: str
    scope: Literal["state_season", "state", "national"]
    state: str | None
    season: str | None
    median: Decimal
    p25: Decimal
    p75: Decimal
    sample_count: int
    year_from: int
    year_to: int
    unit_note: str


class YieldPositionOut(BaseModel):
    benchmark: YieldBenchmarkOut
    observed: Decimal
    band: Literal["below_typical", "typical", "above_typical"]


class NutrientGapOut(BaseModel):
    nutrient: Literal["N", "P", "K", "pH"]
    measured: Decimal
    target: Decimal
    status: Literal["low", "adequate", "high"]


class FertilizerAdviceOut(BaseModel):
    crop_key: str
    display_name: str
    gaps: list[NutrientGapOut]
    soil_source: str
    caveat: str


class SoilNutrientsOut(BaseModel):
    n: int
    p: int
    k: int
    ph: Decimal
    confidence: Literal["state"]
    source: str
