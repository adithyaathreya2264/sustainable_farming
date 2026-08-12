import React from "react";
import { Text, View } from "react-native";
import { Card } from "./ui/Card";

// Static mock — the real widget will read from the Weather API proxy
// (`GET /api/v1/proxy/weather` per the Technical Design doc) once the
// backend exists.
export function WeatherWidget() {
  return (
    <Card className="mb-4 flex-row items-center justify-between">
      <View>
        <Text className="text-ink font-semibold" style={{ fontSize: 15 }}>
          Mysuru, Karnataka
        </Text>
        <Text className="text-ink-muted mt-0.5" style={{ fontSize: 13 }}>
          Humidity 78% · Rain likely tomorrow
        </Text>
      </View>
      <View className="items-end">
        <Text style={{ fontSize: 28 }}>🌦️</Text>
        <Text className="text-ink font-bold" style={{ fontSize: 18 }}>
          27°C
        </Text>
      </View>
    </Card>
  );
}
