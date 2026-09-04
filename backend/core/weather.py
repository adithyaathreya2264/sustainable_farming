"""Open-Meteo client (Task 4.1).

No API key needed for non-commercial use (per open-meteo.com/en/docs). Uses
`past_days` on the forecast endpoint to get recent history in one call rather
than a separate archive-API request.

Wired for real, but as of this task none of the seeded agronomic_rules
actually gate on a weather field — they're stage-only or keyed on farmer
field-scouting observations (see services/rule_engine.py). This exists for
whenever a weather-gated rule is added.
"""

from __future__ import annotations

import httpx

_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def get_weather_snapshot(lat: float, long: float) -> dict:
    """Returns Open-Meteo's `daily` block (dates + last-7-days precipitation/
    temperature) or `{}` on any failure. Never raises — a missing weather
    snapshot just means no weather-gated rule can evaluate this run, same
    graceful-degradation precedent as core/services/soil_lookup.py.
    """
    try:
        resp = httpx.get(
            _FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": long,
                "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min",
                "past_days": 7,
                "forecast_days": 1,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
    except httpx.HTTPError:
        return {}

    return resp.json().get("daily", {})
