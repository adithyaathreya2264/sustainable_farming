"""Response shape for GET /api/v1/weather (dashboard weather widget)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ForecastDayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: str
    temp_max_c: float | None = None
    temp_min_c: float | None = None
    precipitation_mm: float | None = None
    condition_group: str
    condition_label: str


class WeatherOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # False when the farmer has no state/district set, geocoding failed, or the
    # weather provider was unreachable — the widget shows an "unavailable" state.
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
    forecast: list[ForecastDayOut] = []
