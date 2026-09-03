"""Fast2SMS client wrapper.

KNOWN GAP, deliberately deferred: the Fast2SMS account isn't yet verified for
the OTP route (a probe call returned HTTP 400 / status_code 996 — "complete
website verification"), so the *success* response shape below is still an
unconfirmed best guess at Fast2SMS's documented convention
(`{"return": true, ...}`). The *failure* path is confirmed for real — a
non-200 status correctly returns False, matching the probe. Re-run
`backend/scripts/fast2sms_probe.py` once the account is verified and adjust
the success check below if the real body differs.
"""

from __future__ import annotations

import httpx

from backend.core.config import settings

_FAST2SMS_URL = "https://www.fast2sms.com/dev/bulkV2"


def send_otp_sms(phone_number: str, otp: str) -> bool:
    """Send `otp` to `phone_number` via Fast2SMS. Returns False on failure —
    never raises for an ordinary send failure, so callers can respond to the
    client instead of 500ing.
    """
    try:
        resp = httpx.post(
            _FAST2SMS_URL,
            headers={"authorization": settings.fast2sms_api_key},
            data={
                "variables_values": otp,
                "route": "otp",
                "numbers": phone_number,
            },
            timeout=10.0,
        )
    except httpx.HTTPError:
        return False

    if resp.status_code != 200:
        return False

    # Best-guess success shape (unconfirmed — see module docstring).
    data = resp.json()
    return bool(data.get("return") is True)
