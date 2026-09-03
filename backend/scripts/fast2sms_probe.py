"""THROWAWAY script — makes one real Fast2SMS call and prints the raw response.

Sends a real SMS and spends account credit. Run only with explicit go-ahead.
Delete this file once core/sms.py's send_otp_sms is finalized against the
real response shape.

Usage (from repo root, venv active):
    python -m backend.scripts.fast2sms_probe <10-digit-phone-number>
"""

from __future__ import annotations

import sys

import httpx

from backend.core.config import settings


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python -m backend.scripts.fast2sms_probe <phone_number>")
        raise SystemExit(1)

    phone_number = sys.argv[1]
    test_otp = "123456"

    resp = httpx.post(
        "https://www.fast2sms.com/dev/bulkV2",
        headers={"authorization": settings.fast2sms_api_key},
        data={
            "variables_values": test_otp,
            "route": "otp",
            "numbers": phone_number,
        },
    )

    print("status:", resp.status_code)
    print("headers:", dict(resp.headers))
    print("body:", resp.text)


if __name__ == "__main__":
    main()
