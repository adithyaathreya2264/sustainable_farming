// Live weather for a farmer's location via Open-Meteo (no API key).
// Failures degrade to { available: false } instead of raising.
const GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search";
const FORECAST_URL = "https://api.open-meteo.com/v1/forecast";

// WMO weather-interpretation codes -> [group, label].
const WMO = {
  0: ["clear", "Clear sky"],
  1: ["mostly_clear", "Mainly clear"],
  2: ["partly_cloudy", "Partly cloudy"],
  3: ["cloudy", "Overcast"],
  45: ["fog", "Fog"],
  48: ["fog", "Depositing rime fog"],
  51: ["drizzle", "Light drizzle"],
  53: ["drizzle", "Moderate drizzle"],
  55: ["drizzle", "Dense drizzle"],
  56: ["drizzle", "Light freezing drizzle"],
  57: ["drizzle", "Dense freezing drizzle"],
  61: ["rain", "Slight rain"],
  63: ["rain", "Moderate rain"],
  65: ["rain", "Heavy rain"],
  66: ["rain", "Light freezing rain"],
  67: ["rain", "Heavy freezing rain"],
  71: ["snow", "Slight snowfall"],
  73: ["snow", "Moderate snowfall"],
  75: ["snow", "Heavy snowfall"],
  77: ["snow", "Snow grains"],
  80: ["rain_showers", "Slight rain showers"],
  81: ["rain_showers", "Moderate rain showers"],
  82: ["rain_showers", "Violent rain showers"],
  85: ["snow", "Slight snow showers"],
  86: ["snow", "Heavy snow showers"],
  95: ["thunderstorm", "Thunderstorm"],
  96: ["thunderstorm", "Thunderstorm with slight hail"],
  99: ["thunderstorm", "Thunderstorm with heavy hail"],
};

export function describe(code) {
  if (code === null || code === undefined) return ["unknown", "Unknown"];
  return WMO[Math.trunc(Number(code))] ?? ["unknown", "Unknown"];
}

const nth = (seq, i) => (!seq || i >= seq.length ? null : seq[i]);

async function getJson(url, params) {
  const res = await fetch(`${url}?${new URLSearchParams(params)}`, {
    signal: AbortSignal.timeout(10_000),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function geocode(state, district) {
  for (const q of [`${district}`, `${state}`]) {
    if (!q.trim()) continue;
    let data;
    try {
      data = await getJson(GEOCODE_URL, { name: q, count: 10, language: "en", format: "json" });
    } catch {
      continue;
    }
    const results = data.results || [];
    const india = results.filter((r) => r.country_code === "IN");
    const pool = india.length ? india : results;
    if (!pool.length) continue;
    let best = null;
    if (state.trim()) {
      best =
        pool.find((r) => String(r.admin1 ?? "").toLowerCase().includes(state.toLowerCase())) ?? null;
    }
    const chosen = best ?? pool[0];
    const label = [chosen.name, chosen.admin1, chosen.country].filter(Boolean).join(", ");
    return { lat: Number(chosen.latitude), long: Number(chosen.longitude), label };
  }
  return null;
}

const unavailable = (extra = {}) => ({
  available: false,
  location_label: null,
  latitude: null,
  longitude: null,
  temperature_c: null,
  feels_like_c: null,
  humidity_pct: null,
  precipitation_mm: null,
  wind_kph: null,
  condition_group: null,
  condition_label: null,
  observed_at: null,
  forecast: [],
  ...extra,
});

/** Python datetime.fromisoformat for Open-Meteo's naive local 'YYYY-MM-DDTHH:MM'. */
function naiveIso(t) {
  const m = /^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/.exec(t);
  return m ? `${m[1]}T${m[2]}:${m[3]}:${m[4] ?? "00"}` : null;
}

export async function getWeatherReport(state, district) {
  if (!(state || "").trim() && !(district || "").trim()) return unavailable();

  const geo = await geocode(state, district);
  if (geo === null) return unavailable();

  let data;
  try {
    data = await getJson(FORECAST_URL, {
      latitude: geo.lat,
      longitude: geo.long,
      current:
        "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
      daily: "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum",
      timezone: "auto",
      forecast_days: 4,
      wind_speed_unit: "kmh",
    });
  } catch {
    return unavailable({ location_label: geo.label, latitude: geo.lat, longitude: geo.long });
  }

  const cur = data.current || {};
  const [group, curLabel] = describe(cur.weather_code);
  const daily = data.daily || {};
  const forecast = (daily.time || []).map((iso, i) => {
    const [g, gl] = describe(
      i < (daily.weather_code || []).length ? (daily.weather_code || [null])[i] : null
    );
    return {
      date: iso,
      temp_max_c: nth(daily.temperature_2m_max, i),
      temp_min_c: nth(daily.temperature_2m_min, i),
      precipitation_mm: nth(daily.precipitation_sum, i),
      condition_group: g,
      condition_label: gl,
    };
  });

  return {
    available: true,
    location_label: geo.label,
    latitude: geo.lat,
    longitude: geo.long,
    temperature_c: cur.temperature_2m ?? null,
    feels_like_c: cur.apparent_temperature ?? null,
    humidity_pct:
      cur.relative_humidity_2m !== undefined && cur.relative_humidity_2m !== null
        ? Math.trunc(cur.relative_humidity_2m)
        : null,
    precipitation_mm: cur.precipitation ?? null,
    wind_kph: cur.wind_speed_10m ?? null,
    condition_group: group,
    condition_label: curLabel,
    observed_at: cur.time ? naiveIso(cur.time) : null,
    forecast,
  };
}

/** Recent daily precipitation/temperature block for the rule engine (never throws). */
export async function getWeatherSnapshot(lat, long) {
  try {
    const data = await getJson("https://api.open-meteo.com/v1/forecast", {
      latitude: lat,
      longitude: long,
      daily: "precipitation_sum,temperature_2m_max,temperature_2m_min",
      past_days: 7,
      forecast_days: 1,
    });
    return data.daily ?? {};
  } catch {
    return {};
  }
}
