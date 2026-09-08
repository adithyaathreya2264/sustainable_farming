"""Response shapes for GET/POST /api/v1/advisory/*.

`remedy` arrives already prefixed with "[Unverified guidance] " by
`services/disease_advisory`, and `caveat` is a required field. Neither is
optional: the corpus cites no agronomic authority, so a client cannot be given
the option of rendering a treatment without its warning.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AdvisoryMatchOut(BaseModel):
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
    language: str
    caveat: str


class AdvisoryListOut(BaseModel):
    matches: list[AdvisoryMatchOut]


class DiagnoseIn(BaseModel):
    symptom_text: str = Field(min_length=3, max_length=1000)
    crop_key: str | None = None
    # Defaults to the caller's profile language when omitted.
    language: str | None = None
