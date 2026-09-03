"""OTP generation and hashing.

Generation uses `secrets`, not `random` — `random` is not cryptographically
secure and an OTP is a security boundary, even at 6 digits.

Hashing uses plain SHA-256, not bcrypt: OTPs are short-lived (minutes) and
single-use, unlike passwords, so bcrypt's slow-hash property buys nothing here.
"""

from __future__ import annotations

import hashlib
import secrets

from backend.core.config import settings

_DIGITS = "0123456789"


def generate_otp() -> str:
    """A random numeric string of `settings.otp_length` digits."""
    return "".join(secrets.choice(_DIGITS) for _ in range(settings.otp_length))


def hash_otp(otp: str) -> str:
    """SHA-256 hex digest of an OTP. Never store the raw code."""
    return hashlib.sha256(otp.encode()).hexdigest()
