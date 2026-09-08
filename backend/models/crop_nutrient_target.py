"""Per-crop nutrient targets, for soil-gap advice.

Seeded from `crop_nutrient_targets.json`. Server-owned reference data.

These are **targets, not doses**. The gap between a target and a soil reading
is the whole feature; turning that gap into a product and a quantity is
deliberately out of scope, matching the `agri_catalog` rule that catalog rows
carry product identity only with no baked-in dosage. A farmer told "your soil
N is well below the target for Rice" can act on it with local advice; a farmer
told "apply 43 kg of urea" has been given a prescription this data cannot
support.
"""

from __future__ import annotations

from sqlalchemy import Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin


class CropNutrientTarget(Base, TimestampMixin):
    __tablename__ = "crop_nutrient_targets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # unique=True already creates the index; index=True would add a second.
    crop_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    seeded_crop_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    target_n: Mapped[int] = mapped_column(Integer, nullable=False)
    target_p: Mapped[int] = mapped_column(Integer, nullable=False)
    target_k: Mapped[int] = mapped_column(Integer, nullable=False)
    target_ph: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
