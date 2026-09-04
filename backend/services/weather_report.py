"""Current weather for a farmer's location (state + district).

The dashboard's weather widget needs live conditions for where the farmer is,
but `User` only stores `state` / `district` names — not coordinates. So this:

1. geocodes "<district>, <state>, India" -> lat/long via Open-Meteo's free
   geocoding API (no key), and
2. pulls the `current` block + a short daily forecast from the Open-Meteo
   forecast API (same service `core/weather.py` already uses for the rule
   engine).

Graceful degradation throughout — same precedent as `services/soil_lookup.py`
and `core/weather.py`: any failure returns a result with `available=False`
rather than raising, so the endpoint is always a 200 and the widget just shows
"weather unavailable".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import httpx

_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather-interpretation codes (open-meteo.com/en/docs) collapsed to a
# short, stable group key + a plain-English label. The frontend maps the group
# to an emoji; the label is a readable fallback.
_WMO: dict[int, tuple[str, str]] = {
    0: ("clear", "Clear sky"),
    1: ("mostly_clear", "Mainly clear"),
    2: ("partly_cloudy", "Partly cloudy"),
    3: ("cloudy", "Overcast"),
    45: ("fog", "Fog"),
    48: ("fog", "Depositing rime fog"),
    51: ("drizzle", "Light drizzle"),
    53: ("drizzle", "Moderate drizzle"),
    55: ("drizzle", "Dense drizzle"),
    56: ("drizzle", "Light freezing drizzle"),
    57: ("drizzle", "Dense freezing drizzle"),
    61: ("rain", "Slight rain"),
    63: ("rain", "Moderate rain"),
    65: ("rain", "Heavy rain"),
    66: ("rain", "Light freezing rain"),
    67: ("rain", "Heavy freezing rain"),
    71: ("snow", "Slight snowfall"),
    73: ("snow", "Moderate snowfall"),
    75: ("snow", "Heavy snowfall"),
    77: ("snow", "Snow grains"),
    80: ("rain_showers", "Slight rain showers"),
    81: ("rain_showers", "Moderate rain showers"),
    82: ("rain_showers", "Violent rain showers"),
    85: ("snow", "Slight snow showers"),
    86: ("snow", "Heavy snow showers"),
    95: ("thunderstorm", "Thunderstorm"),
    96: ("thunderstorm", "Thunderstorm with slight hail"),
    99: ("thunderstorm", "Thunderstorm with heavy hail"),
}


def _describe(code: int | None) -> tuple[str, str]:
    if code is None:
        return "unknown", "Unknown"
    return _WMO.get(int(code), ("unknown", "Unknown"))


@dataclass
class ForecastDay:
    date: str
    temp_max_c: float | None
    temp_min_c: float | None
    precipitation_mm: float | None
    condition_group: str
    condition_label: str


@dataclass
class WeatherReport:
    available: bool
    location_label: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    temperature_c: float | None = None
    feels_like_c: float | None = None
    humidity_pct: int | None = None
    precipitation_mm: float | None = None
    wind_kph: float | None = None
    condition_group: str | None = None
    condition_label: str | None = None
    observed_at: datetime | None = None
    forecast: list[ForecastDay] = field(default_factory=list)


def _geocode(state: str, district: str) -> tuple[float, float, str] | None:
    """(lat, long, resolved_name) for a district, or None. Tries the district
    name first (more specific), falls back to the state."""
    for query in (f"{district}", f"{state}"):
        if not query.strip():
            continue
        try:
            resp = httpx.get(
                _GEOCODE_URL,
                params={"name": query, "count": 10, "language": "en", "format": "json"},
                timeout=10.0,
            )
            resp.raise_for_status()
        except httpx.HTTPError:
            continue

        results = resp.json().get("results") or []
        # Prefer a hit in India, and — when we queried the district — one whose
        # admin1 (state) matches, so "Bijapur" resolves to Karnataka not
        # Chhattisgarh.
        india = [r for r in results if r.get("country_code") == "IN"]
        pool = india or results
        if not pool:
            continue
        best = None
        if state.strip():
            best = next(
                (r for r in pool if state.lower() in str(r.get("admin1", "")).lower()),
                None,
            )
        chosen = best or pool[0]
        name_parts = [
            chosen.get("name"),
            chosen.get("admin1"),
            chosen.get("country"),
        ]
        label = ", ".join(p for p in name_parts if p)
        return float(chosen["latitude"]), float(chosen["longitude"]), label

    return None


def get_weather_report(state: str, district: str) -> WeatherReport:
    if not (state or "").strip() and not (district or "").strip():
        return WeatherReport(available=False)

    geo = _geocode(state, district)
    if geo is None:
        return WeatherReport(available=False)
    lat, long, label = geo

    try:
        resp = httpx.get(
            _FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": long,
                "current": (
                    "temperature_2m,relative_humidity_2m,apparent_temperature,"
                    "precipitation,weather_code,wind_speed_10m"
                ),
                "daily": (
                    "weather_code,temperature_2m_max,temperature_2m_min,"
                    "precipitation_sum"
                ),
                "timezone": "auto",
                "forecast_days": 4,
                "wind_speed_unit": "kmh",
            },
            timeout=10.0,
        )
        resp.raise_for_status()
    except httpx.HTTPError:
        return WeatherReport(available=False, location_label=label,
                             latitude=lat, longitude=long)

    data = resp.json()
    cur = data.get("current") or {}
    group, cur_label = _describe(cur.get("weather_code"))

    observed_at = None
    if cur.get("time"):
        try:
            observed_at = datetime.fromisoformat(cur["time"])
        except ValueError:
            observed_at = None

    daily = data.get("daily") or {}
    days: list[ForecastDay] = []
    for i, iso in enumerate(daily.get("time", [])):
        g, gl = _describe((daily.get("weather_code") or [None])[i]
                          if i < len(daily.get("weather_code", [])) else None)
        days.append(
            ForecastDay(
                date=iso,
                temp_max_c=_nth(daily.get("temperature_2m_max"), i),
                temp_min_c=_nth(daily.get("temperature_2m_min"), i),
                precipitation_mm=_nth(daily.get("precipitation_sum"), i),
                condition_group=g,
                condition_label=gl,
            )
        )

    return WeatherReport(
        available=True,
        location_label=label,
        latitude=lat,
        longitude=long,
        temperature_c=cur.get("temperature_2m"),
        feels_like_c=cur.get("apparent_temperature"),
        humidity_pct=(
            int(cur["relative_humidity_2m"])
            if cur.get("relative_humidity_2m") is not None
            else None
        ),
        precipitation_mm=cur.get("precipitation"),
        wind_kph=cur.get("wind_speed_10m"),
        condition_group=group,
        condition_label=cur_label,
        observed_at=observed_at,
        forecast=days,
    )


def _nth(seq: list | None, i: int) -> float | None:
    if not seq or i >= len(seq):
        return None
    return seq[i]
