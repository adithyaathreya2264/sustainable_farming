"""Crop disease advisory endpoints.

`POST /diagnose` — a farmer describes what they see, gets ranked matches.
`GET  /diseases` — what to watch for on a crop this season.

Diagnose is a POST because the symptom text is free-form prose that can run to
a couple of sentences; putting it in a query string invites truncation and
awkward encoding for Devanagari input.

Language falls back to the caller's `language_pref`, then to English. The
corpus only holds en/hi/mr, and `services/disease_advisory` degrades to
English for the app's other 7 locales rather than machine-translating
agronomic advice.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.deps import get_current_user
from backend.models.user import User
from backend.schemas.advisory import AdvisoryListOut, AdvisoryMatchOut, DiagnoseIn
from backend.services.disease_advisory import Language, for_crop, search

router = APIRouter(prefix="/api/v1/advisory", tags=["advisory"])

_SUPPORTED: tuple[Language, ...] = ("en", "hi", "mr")


def _resolve_language(requested: str | None, user: User) -> Language:
    for candidate in (requested, user.language_pref):
        if candidate in _SUPPORTED:
            return candidate  # type: ignore[return-value]
    return "en"


@router.post("/diagnose", response_model=AdvisoryListOut)
def diagnose(
    payload: DiagnoseIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdvisoryListOut:
    matches = search(
        db,
        payload.symptom_text,
        crop_key=payload.crop_key,
        language=_resolve_language(payload.language, current_user),
    )
    # An empty list is a valid, honest answer — see services/disease_advisory,
    # which returns nothing rather than the least-bad match.
    return AdvisoryListOut(
        matches=[AdvisoryMatchOut(**match.__dict__) for match in matches]
    )


@router.get("/diseases", response_model=AdvisoryListOut)
def diseases_for_crop(
    crop_key: str = Query(..., description="Normalised crop slug, e.g. 'rice'"),
    season: str | None = Query(None),
    state: str | None = Query(None),
    language: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdvisoryListOut:
    matches = for_crop(
        db,
        crop_key,
        season=season,
        state=state or current_user.state,
        language=_resolve_language(language, current_user),
    )
    return AdvisoryListOut(
        matches=[AdvisoryMatchOut(**match.__dict__) for match in matches]
    )
