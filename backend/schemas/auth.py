"""Request/response models for the phone+OTP auth endpoints."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

# 10-digit Indian mobile number, optionally prefixed with +91/0.
_PHONE_RE = re.compile(r"^(?:\+91|0)?[6-9]\d{9}$")


def _normalize_phone(v: str) -> str:
    """Validate and collapse +91/0-prefixed input to a bare 10-digit number,
    so `request-otp` and `verify-otp` always key off the same string."""
    if not _PHONE_RE.match(v):
        raise ValueError("must be a valid 10-digit Indian mobile number")
    return v[-10:]


class RequestOtpIn(BaseModel):
    phone_number: str = Field(..., examples=["9876543210"])

    @field_validator("phone_number")
    @classmethod
    def _valid_phone(cls, v: str) -> str:
        return _normalize_phone(v)


class RequestOtpOut(BaseModel):
    # Deliberately generic — never echoes the OTP or whether the number exists.
    message: str = "OTP sent"


class VerifyOtpIn(BaseModel):
    phone_number: str
    otp: str

    @field_validator("phone_number")
    @classmethod
    def _valid_phone(cls, v: str) -> str:
        return _normalize_phone(v)


class VerifyOtpOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
