"""Crop disease advisory: symptom search and proactive per-crop browsing.

Backed by 88 diseases and 2,140 symptom->remedy rows in English, Hindi and
Marathi (see `models/crop_disease.py`).

## Confidence

The source cites no agronomic authority for any remedy, so everything this
module returns is prefixed the same way `services/rule_engine.py` prefixes an
unverified rule. That prefix is applied here, in the service, rather than left
to each caller — a route that forgets it would be shipping unattributed
pesticide advice to a farmer.

## Matching

`search()` scores a farmer's free-text complaint against the stored symptom
phrasings by token overlap. This is deliberately a simple lexical scorer, not
an embedding model: it needs no artifact in the runtime path, it is
inspectable when a match looks wrong, and with ~25 phrasings per disease the
corpus is dense enough that overlap works. If it proves too blunt, MySQL
FULLTEXT over `question_en` is the next step and this signature does not have
to change.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.models.crop_disease import CropDisease, CropDiseaseSymptom

Language = Literal["en", "hi", "mr"]

UNVERIFIED_PREFIX = "[Unverified guidance] "

# Words that carry no diagnostic signal. Kept short on purpose: an aggressive
# stoplist throws away the plant-part and colour words that actually
# discriminate between diseases.
_STOPWORDS = frozenset(
    """
    a an the my me i is are was were be been being on in at of to for from with
    and or but it its this that these those there here have has had do does did
    my plant plants crop crops field seeing see saw looks look looking started
    start am not no if so as by
    """.split()
)

_TOKEN = re.compile(r"[a-z]+")


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in _TOKEN.findall(text.lower())
        if len(token) > 2 and token not in _STOPWORDS
    }


@dataclass(frozen=True)
class AdvisoryMatch:
    disease_id: str
    disease_name: str
    crop_display_name: str
    disease_type: str
    cause: str | None
    matched_symptom: str
    remedy: str
    severity_level: str | None
    season: str | None
    affected_plant_part: str | None
    score: float
    language: Language
    caveat: str


def _localised(row: CropDiseaseSymptom, field: str, language: Language) -> str:
    """Pick a language column, falling back to English.

    The corpus only has en/hi/mr; the app has 10 locales. A caller asking for
    Kannada gets English rather than a machine translation — mistranslated
    agronomic advice is worse than untranslated advice.
    """
    value = getattr(row, f"{field}_{language}", None)
    return value or getattr(row, f"{field}_en")


def search(
    db: Session,
    query_text: str,
    *,
    crop_key: str | None = None,
    language: Language = "en",
    limit: int = 5,
) -> list[AdvisoryMatch]:
    """Rank symptom rows against a free-text complaint.

    Returns an empty list when nothing overlaps, rather than the least-bad
    match — offering an unrelated disease because it shared one word is worse
    than saying nothing.
    """
    query_tokens = _tokens(query_text)
    if not query_tokens:
        return []

    statement = select(CropDiseaseSymptom).options(
        joinedload(CropDiseaseSymptom.disease)
    )
    if crop_key:
        statement = statement.join(CropDiseaseSymptom.disease).where(
            CropDisease.crop_key == crop_key
        )

    scored: list[tuple[float, CropDiseaseSymptom]] = []
    for row in db.scalars(statement).unique().all():
        row_tokens = _tokens(row.question_en)
        if not row_tokens:
            continue
        overlap = query_tokens & row_tokens
        if not overlap:
            continue
        # Jaccard-style, normalised by the query so a long stored phrasing
        # isn't penalised for containing extra words the farmer didn't use.
        score = len(overlap) / len(query_tokens | row_tokens)
        scored.append((score, row))

    scored.sort(key=lambda pair: pair[0], reverse=True)

    matches: list[AdvisoryMatch] = []
    seen_diseases: set[str] = set()
    for score, row in scored:
        # One row per disease: 25 phrasings of the same disease filling the
        # results would crowd out the alternatives worth considering.
        if row.disease_id in seen_diseases:
            continue
        seen_diseases.add(row.disease_id)

        disease = row.disease
        matches.append(
            AdvisoryMatch(
                disease_id=disease.id,
                disease_name=_disease_name(disease, language),
                crop_display_name=disease.crop_display_name,
                disease_type=disease.disease_type,
                cause=disease.cause,
                matched_symptom=_localised(row, "question", language),
                remedy=UNVERIFIED_PREFIX + _localised(row, "remedy", language),
                severity_level=row.severity_level,
                season=row.season,
                affected_plant_part=row.affected_plant_part,
                score=round(score, 4),
                language=language,
                caveat=_CAVEAT,
            )
        )
        if len(matches) >= limit:
            break

    return matches


_CAVEAT = (
    "Sourced from a dataset with no cited agronomic authority. Confirm with "
    "your local Krishi Vigyan Kendra or agriculture officer before applying "
    "any treatment."
)


def _disease_name(disease: CropDisease, language: Language) -> str:
    value = getattr(disease, f"disease_name_{language}", None)
    return value or disease.disease_name_en


def for_crop(
    db: Session,
    crop_key: str,
    *,
    season: str | None = None,
    state: str | None = None,
    language: Language = "en",
) -> list[AdvisoryMatch]:
    """Diseases recorded for a crop, optionally narrowed by season and state.

    Proactive browsing rather than diagnosis — "what should I be watching for
    in Cotton this Kharif". Season/state narrow but do not exclude: if nothing
    matches the narrower filter the unfiltered set for the crop is returned,
    because an empty screen is less useful than a broader list.
    """
    statement = (
        select(CropDiseaseSymptom)
        .options(joinedload(CropDiseaseSymptom.disease))
        .join(CropDiseaseSymptom.disease)
        .where(CropDisease.crop_key == crop_key)
    )

    narrowed = statement
    if season:
        narrowed = narrowed.where(CropDiseaseSymptom.season == season)
    if state:
        narrowed = narrowed.where(CropDiseaseSymptom.major_state == state)

    rows = db.scalars(narrowed).unique().all()
    if not rows:
        rows = db.scalars(statement).unique().all()

    matches: list[AdvisoryMatch] = []
    seen: set[str] = set()
    for row in rows:
        if row.disease_id in seen:
            continue
        seen.add(row.disease_id)
        disease = row.disease
        matches.append(
            AdvisoryMatch(
                disease_id=disease.id,
                disease_name=_disease_name(disease, language),
                crop_display_name=disease.crop_display_name,
                disease_type=disease.disease_type,
                cause=disease.cause,
                matched_symptom=_localised(row, "question", language),
                remedy=UNVERIFIED_PREFIX + _localised(row, "remedy", language),
                severity_level=row.severity_level,
                season=row.season,
                affected_plant_part=row.affected_plant_part,
                score=0.0,  # not a ranked result
                language=language,
                caveat=_CAVEAT,
            )
        )

    matches.sort(key=lambda match: match.disease_name)
    return matches
