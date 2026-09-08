"""Crop disease knowledge base: diseases and their symptom->remedy rows.

Seeded from `crop_diseases.json` + `crop_disease_symptoms.json`. Server-owned
reference data, not synced.

## Why two tables

The source is 2,231 rows over only 88 distinct (crop, disease) pairs — ~25
rows per disease, each a different way a farmer might phrase the same
complaint, paired with a remedy. `cause` and `disease_type` were verified
identical across every row of every pair, so they are properties of the
disease. `remedy`, `severity_level`, `season`, `affected_plant_part` and
`major_state` all vary within nearly every pair, so they are properties of the
*presentation*, not the disease. Flattening them into one table would mean
picking one arbitrary remedy per disease and discarding two dozen others.

## Confidence

The dataset cites no agronomic authority for any remedy. Everything here is
`unverified` and must be surfaced with the same prefix
`services/rule_engine.py` applies to unverified rules. There is no
`confidence` column because there is nothing to vary: if a verified source is
ever added, that is the moment to add one.

## Languages

English, Hindi and Marathi come from the source. The app's other 8 locales
have no translation here and must fall back to English — machine-translating
agronomic advice is not acceptable.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class CropDisease(Base, TimestampMixin):
    """What is stable about a disease: its identity, type and cause."""

    __tablename__ = "crop_diseases"
    __table_args__ = (
        Index("ix_crop_diseases_crop", "crop_key"),
    )

    # Deterministic hash of (crop_key, disease_name_en) from the cleaner, not a
    # random UUID — re-running prep must produce the same ids or the seeder
    # cannot stay idempotent.
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    crop_key: Mapped[str] = mapped_column(String(120), nullable=False)
    crop_display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    seeded_crop_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    disease_name_en: Mapped[str] = mapped_column(String(200), nullable=False)
    disease_name_hi: Mapped[str | None] = mapped_column(String(200), nullable=True)
    disease_name_mr: Mapped[str | None] = mapped_column(String(200), nullable=True)

    disease_type: Mapped[str] = mapped_column(String(40), nullable=False)
    cause: Mapped[str | None] = mapped_column(String(255), nullable=True)
    symptom_count: Mapped[int] = mapped_column(Integer, nullable=False)

    symptoms: Mapped[list["CropDiseaseSymptom"]] = relationship(
        back_populates="disease"
    )


class CropDiseaseSymptom(Base, TimestampMixin):
    """One phrasing of a complaint, and the remedy paired with it."""

    __tablename__ = "crop_disease_symptoms"
    __table_args__ = (
        Index("ix_crop_disease_symptoms_filter", "season", "major_state"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    disease_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("crop_diseases.id"), nullable=False, index=True
    )

    question_en: Mapped[str] = mapped_column(Text, nullable=False)
    question_hi: Mapped[str | None] = mapped_column(Text, nullable=True)
    question_mr: Mapped[str | None] = mapped_column(Text, nullable=True)

    remedy_en: Mapped[str] = mapped_column(Text, nullable=False)
    remedy_hi: Mapped[str | None] = mapped_column(Text, nullable=True)
    remedy_mr: Mapped[str | None] = mapped_column(Text, nullable=True)

    severity_level: Mapped[str | None] = mapped_column(String(24), nullable=True)
    season: Mapped[str | None] = mapped_column(String(24), nullable=True)
    affected_plant_part: Mapped[str | None] = mapped_column(String(80), nullable=True)
    major_state: Mapped[str | None] = mapped_column(String(80), nullable=True)

    disease: Mapped["CropDisease"] = relationship(back_populates="symptoms")
