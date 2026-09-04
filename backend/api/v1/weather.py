"""Live weather for the dashboard widget (`GET /api/v1/weather`).

Resolves the farmer's `state` / `district` (from their profile, or an explicit
override query) to coordinates and returns current conditions + a short
forecast. Always 200 — see services/weather_report.py for the graceful-
degradation contract (`available: false` instead of an error).

Results are cached in-process for a few minutes: the widget is polled from the
same connectivity/foreground triggers as sync, and Open-Meteo's free tier is
rate-limited, so hammering it per foreground event is wasteful.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Query

from backend.core.deps import get_current_user
from backend.models.user import User
from backend.schemas.weather import WeatherOut
from backend.services.weather_report import get_weather_report

router = APIRouter(prefix="/api/v1/weather", tags=["weather"])

_CACHE_TTL_SECONDS = 10 * 60
_cache: dict[tuple[str, str], tuple[float, WeatherOut]] = {}


@router.get("", response_model=WeatherOut)
def current_weather(
    state: str | None = Query(None),
    district: str | None = Query(None),
    current_user: User = Depends(get_current_user),
) -> WeatherOut:
    resolved_state = (state or current_user.state or "").strip()
    resolved_district = (district or current_user.district or "").strip()

    key = (resolved_state.lower(), resolved_district.lower())
    now = time.monotonic()
    hit = _cache.get(key)
    if hit is not None and now - hit[0] < _CACHE_TTL_SECONDS:
        return hit[1]

    report = get_weather_report(resolved_state, resolved_district)
    out = WeatherOut.model_validate(report)
    # Only cache a real answer — a transient provider failure shouldn't stick
    # for 10 minutes.
    if out.available:
        _cache[key] = (now, out)
    return out
