"""Response/request shapes for GET/PATCH /api/v1/alerts (Phase 4 Part 2).

Unifies Recommendation and SchemeMatch into one feed shape. Two different
confidence *scales* get mapped into one 3-value label here — see
api/v1/alerts.py's mapping functions for the reasoning (recorded there, not
duplicated in this docstring).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

AlertKind = Literal["recommendation", "scheme_match"]
ConfidenceLabel = Literal["unverified", "provisional", "verified"]


class AlertOut(BaseModel):
    id: str
    kind: AlertKind
    severity: str | None = None
    status: str
    headline: str
    detail: str | None = None
    confidence_label: ConfidenceLabel
    application_url: str | None = None
    authority: str | None = None
    eligibility_summary: list[str] | None = None
    generated_at: datetime
    planting_id: str | None = None


class AlertsListOut(BaseModel):
    items: list[AlertOut]


class AlertStatusIn(BaseModel):
    status: str
