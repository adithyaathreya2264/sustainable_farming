import React, { useEffect } from "react";
import { Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { Card } from "./ui/Card";
import { useAppState } from "../hooks/useAppState";
import { fetchAndCacheWeather } from "../services/weather";
import type { WeatherConditionGroup } from "../types/models";

/**
 * Live conditions for the farmer's location. The backend
 * (GET /api/v1/weather) geocodes their profile state/district and returns
 * current weather from Open-Meteo; this just renders the cached snapshot
 * (store `weather`, refreshed by hooks/useRefreshTriggers.ts). Falls back to a
 * mount-time fetch so opening the dashboard first thing still populates it.
 */

const CONDITION_EMOJI: Record<WeatherConditionGroup, string> = {
  clear: "☀️",
  mostly_clear: "🌤️",
  partly_cloudy: "⛅",
  cloudy: "☁️",
  fog: "🌫️",
  drizzle: "🌦️",
  rain: "🌧️",
  rain_showers: "🌦️",
  snow: "❄️",
  thunderstorm: "⛈️",
  unknown: "🌡️",
};

export function WeatherWidget() {
  const { t } = useTranslation();
  const weather = useAppState((s) => s.weather);
  const hasLocation = useAppState((s) => Boolean(s.user.state || s.user.district));

  useEffect(() => {
    fetchAndCacheWeather();
  }, []);

  // Never fetched, or no location to geocode yet.
  if (!weather || (!weather.available && !hasLocation)) {
    return (
      <Card className="mb-4">
        <Text className="text-ink-muted" style={{ fontSize: 13 }}>
          {hasLocation ? t("home.weatherLoading") : t("home.weatherSetLocation")}
        </Text>
      </Card>
    );
  }

  if (!weather.available) {
    return (
      <Card className="mb-4">
        <Text className="text-ink-muted" style={{ fontSize: 13 }}>
          {t("home.weatherUnavailable")}
        </Text>
      </Card>
    );
  }

  const emoji = CONDITION_EMOJI[weather.conditionGroup ?? "unknown"];
  const tomorrow = weather.forecast[1];

  return (
    <Card className="mb-4">
      <View className="flex-row items-center justify-between">
        <View className="flex-1 pr-2">
          <Text className="text-ink font-semibold" style={{ fontSize: 15 }}>
            {weather.locationLabel}
          </Text>
          <Text className="text-ink-muted mt-0.5" style={{ fontSize: 13 }}>
            {weather.conditionLabel}
            {weather.humidityPct != null
              ? ` · ${t("home.humidity", { pct: weather.humidityPct })}`
              : ""}
          </Text>
          {weather.windKph != null ? (
            <Text className="text-ink-muted mt-0.5" style={{ fontSize: 13 }}>
              {t("home.wind", { kph: Math.round(weather.windKph) })}
            </Text>
          ) : null}
        </View>
        <View className="items-end">
          <Text style={{ fontSize: 28 }}>{emoji}</Text>
          {weather.temperatureC != null ? (
            <Text className="text-ink font-bold" style={{ fontSize: 18 }}>
              {Math.round(weather.temperatureC)}°C
            </Text>
          ) : null}
        </View>
      </View>

      {tomorrow ? (
        <View className="mt-2 pt-2 border-t border-border flex-row items-center justify-between">
          <Text className="text-ink-muted" style={{ fontSize: 12 }}>
            {t("home.weatherTomorrow")}: {tomorrow.conditionLabel}
          </Text>
          <Text className="text-ink-muted" style={{ fontSize: 12 }}>
            {tomorrow.tempMinC != null && tomorrow.tempMaxC != null
              ? `${Math.round(tomorrow.tempMinC)}–${Math.round(tomorrow.tempMaxC)}°C`
              : ""}
            {tomorrow.precipitationMm != null && tomorrow.precipitationMm > 0
              ? ` · ${t("home.rain", { mm: tomorrow.precipitationMm })}`
              : ""}
          </Text>
        </View>
      ) : null}
    </Card>
  );
}
