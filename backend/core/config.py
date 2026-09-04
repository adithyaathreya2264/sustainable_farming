"""Environment-driven configuration.

Secrets (DB URL, credentials) are read from ``backend/.env`` or the real
environment. Nothing is hardcoded here.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # e.g. mysql+pymysql://sf_app:pw@localhost:3306/sustainable-farming?charset=utf8mb4
    database_url: str

    # Present only while provisioning the schema/app user; not required at runtime.
    mysql_root_password: str | None = None

    # --- Auth (Slice 2: phone + OTP via Fast2SMS, JWT issuance) ---
    fast2sms_api_key: str
    otp_expiry_minutes: int = 5
    otp_length: int = 6
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60 * 24 * 7  # 7 days

    # --- Internal endpoints (Phase 4: cron-triggered recommendation/scheme
    # matching runs, not farmer JWT — see core/deps.py:require_internal_key) ---
    internal_api_key: str

    # --- Dev auth bypass (demo / evaluation only) ---
    # When true, POST /api/v1/auth/verify-otp accepts `dev_auth_otp` for ANY
    # phone number — no SMS sent, no rate limit, no OtpRequest row needed — and
    # still issues a real JWT, so sync / profile / alerts / catalog all keep
    # working. `request-otp` becomes a no-op that always reports success.
    # Approved for this project's auth story; MUST be false in a real deploy.
    dev_auth_bypass: bool = False
    dev_auth_otp: str = "123456"

    # --- CORS ---
    # Comma-separated origins for a browser client (`expo start --web`, etc.).
    # Expo Go native doesn't enforce CORS; "*" is a fine dev default, tighten
    # for a real deployment. Parsed from a plain string so `.env` stays simple.
    cors_allow_origins: str = "*"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


settings = Settings()
