import { apiFetch } from "../lib/apiClient";
import { getState, setState } from "../store/appStore";
import type {
  WeatherConditionGroup,
  WeatherForecastDay,
  WeatherSnapshot,
} from "../types/models";

/**
 * Dashboard weather (backend/api/v1/weather.py). The backend resolves the
 * farmer's profile `state` / `district` to coordinates and returns live
 * conditions, so this is a plain authenticated read cached into the store —
 * same pattern as services/catalog.ts / services/alerts.ts, fired from the
 * same foreground/interval triggers (hooks/useRefreshTriggers.ts).
 */

interface BackendForecastDay {
  date: string;
  temp_max_c: number | null;
  temp_min_c: number | null;
  precipitation_mm: number | null;
  condition_group: WeatherConditionGroup;
  condition_label: string;
}

interface BackendWeather {
  available: boolean;
  location_label: string | null;
  temperature_c: number | null;
  feels_like_c: number | null;
  humidity_pct: number | null;
  precipitation_mm: number | null;
  wind_kph: number | null;
  condition_group: WeatherConditionGroup | null;
  condition_label: string | null;
  observed_at: string | null;
  forecast: BackendForecastDay[];
}

function dayFromBackend(d: BackendForecastDay): WeatherForecastDay {
  return {
    date: d.date,
    tempMaxC: d.temp_max_c,
    tempMinC: d.temp_min_c,
    precipitationMm: d.precipitation_mm,
    conditionGroup: d.condition_group,
    conditionLabel: d.condition_label,
  };
}

function weatherFromBackend(row: BackendWeather): WeatherSnapshot {
  return {
    available: row.available,
    locationLabel: row.location_label,
    temperatureC: row.temperature_c,
    feelsLikeC: row.feels_like_c,
    humidityPct: row.humidity_pct,
    precipitationMm: row.precipitation_mm,
    windKph: row.wind_kph,
    conditionGroup: row.condition_group,
    conditionLabel: row.condition_label,
    observedAt: row.observed_at,
    forecast: (row.forecast ?? []).map(dayFromBackend),
    fetchedAt: Date.now(),
  };
}

/**
 * Fetches and caches the weather snapshot. Best-effort/silent on failure
 * (offline, not authenticated, no location set) — the cached copy stays until
 * the next trigger. A successful-but-`available:false` response IS cached, so
 * the widget can distinguish "no location configured" from "never fetched".
 */
export async function fetchAndCacheWeather(): Promise<void> {
  if (!getState().isAuthenticated) return;
  const { state, district } = getState().user;
  if (!state && !district) return; // nothing to geocode yet (pre-onboarding)
  try {
    const res = await apiFetch<BackendWeather>("/api/v1/weather");
    setState({ weather: weatherFromBackend(res) });
  } catch {
    // Silent — keep the last good snapshot.
  }
}

export async function getWeather(): Promise<WeatherSnapshot | null> {
  return getState().weather;
}
