"""Request/response shapes for the user-profile endpoints.

The frontend collects the whole profile during onboarding
((onboarding)/step-1..4) and lets it be edited later ((tabs)/profile.tsx), but
until now had nowhere to send it — `verify-otp` auto-creates the `User` row
with empty defaults and nothing ever filled them in. These back
`GET`/`PATCH /api/v1/users/me`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class UserProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    phone_number: str
    name: str
    language_pref: str
    default_unit: str
    total_area_hectares: float
    irrigation_type: str
    state: str
    district: str
    onboarding_complete: bool


class UserProfileUpdateIn(BaseModel):
    """Every field optional — the profile screen PATCHes one picker at a time,
    onboarding PATCHes the whole set plus `onboarding_complete: true`.
    """

    name: str | None = Field(default=None, max_length=120)
    language_pref: str | None = Field(default=None, max_length=8)
    default_unit: str | None = Field(default=None, max_length=16)
    total_area_hectares: float | None = Field(default=None, ge=0)
    irrigation_type: str | None = Field(default=None, max_length=32)
    state: str | None = Field(default=None, max_length=80)
    district: str | None = Field(default=None, max_length=80)
    onboarding_complete: bool | None = None
