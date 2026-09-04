"""Phone + OTP auth endpoints (Slice 2)."""

from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.jwt import create_access_token
from backend.core.otp import generate_otp, hash_otp
from backend.core.sms import send_otp_sms
from backend.core.config import settings
from backend.models.base import utcnow
from backend.models.otp import OtpRequest
from backend.models.user import User
from backend.schemas.auth import RequestOtpIn, RequestOtpOut, VerifyOtpIn, VerifyOtpOut

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_RATE_LIMIT_WINDOW_MINUTES = 10
_RATE_LIMIT_MAX_REQUESTS = 3
_MAX_VERIFY_ATTEMPTS = 5


def _get_or_create_user(db: Session, phone_number: str) -> User:
    user = db.scalar(select(User).where(User.phone_number == phone_number))
    if user is None:
        user = User(
            id=str(uuid.uuid4()),
            phone_number=phone_number,
            # Placeholder onboarding defaults — filled in by the app's
            # onboarding flow (PATCH /api/v1/users/me), not by this endpoint.
            name="",
            language_pref="en",
            default_unit="hectare",
            total_area_hectares=0,
            irrigation_type="rainfed",
            state="",
            district="",
        )
        db.add(user)
    return user


@router.post("/request-otp", response_model=RequestOtpOut)
def request_otp(body: RequestOtpIn, db: Session = Depends(get_db)) -> RequestOtpOut:
    if settings.dev_auth_bypass:
        # No SMS, no rate limit, no OtpRequest row — verify-otp accepts the
        # fixed dev OTP directly. See core/config.py:dev_auth_bypass.
        return RequestOtpOut()

    window_start = utcnow() - timedelta(minutes=_RATE_LIMIT_WINDOW_MINUTES)
    recent_count = db.scalar(
        select(func.count())
        .select_from(OtpRequest)
        .where(
            OtpRequest.phone_number == body.phone_number,
            OtpRequest.created_at >= window_start,
        )
    )
    if recent_count is not None and recent_count >= _RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many OTP requests. Try again later.",
        )

    otp = generate_otp()
    otp_request = OtpRequest(
        id=str(uuid.uuid4()),
        phone_number=body.phone_number,
        otp_hash=hash_otp(otp),
        expires_at=utcnow() + timedelta(minutes=settings.otp_expiry_minutes),
    )
    db.add(otp_request)
    db.commit()

    if not send_otp_sms(body.phone_number, otp):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not send OTP. Try again shortly.",
        )

    return RequestOtpOut()


@router.post("/verify-otp", response_model=VerifyOtpOut)
def verify_otp(body: VerifyOtpIn, db: Session = Depends(get_db)) -> VerifyOtpOut:
    if settings.dev_auth_bypass:
        if body.otp != settings.dev_auth_otp:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired OTP.",
            )
        user = _get_or_create_user(db, body.phone_number)
        db.commit()
        token = create_access_token(user_id=user.id, phone_number=user.phone_number)
        return VerifyOtpOut(access_token=token)

    otp_request = db.scalar(
        select(OtpRequest)
        .where(
            OtpRequest.phone_number == body.phone_number,
            OtpRequest.consumed_at.is_(None),
        )
        .order_by(OtpRequest.created_at.desc())
        .limit(1)
    )

    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired OTP."
    )

    if otp_request is None:
        raise invalid
    if otp_request.expires_at < utcnow():
        raise invalid
    if otp_request.attempt_count >= _MAX_VERIFY_ATTEMPTS:
        raise invalid

    if otp_request.otp_hash != hash_otp(body.otp):
        otp_request.attempt_count += 1
        db.commit()
        raise invalid

    otp_request.consumed_at = utcnow()

    user = _get_or_create_user(db, body.phone_number)

    db.commit()

    token = create_access_token(user_id=user.id, phone_number=user.phone_number)
    return VerifyOtpOut(access_token=token)
