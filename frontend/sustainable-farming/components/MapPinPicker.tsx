import React from "react";
import { Pressable, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

export interface Coordinates {
  lat: number;
  long: number;
}

interface MapPinPickerProps {
  coordinates: Coordinates | null;
  onPinDrop: (coords: Coordinates) => void;
}

// Mysuru district centroid, used as the mock pin-drop origin. The real
// implementation swaps this component for `@rnmapbox/maps` (per the
// Technical Design doc) behind the same onPinDrop contract, with offline
// tile caching for a 5km radius around the saved field.
const ORIGIN: Coordinates = { lat: 12.2958, long: 76.6394 };

export function MapPinPicker({ coordinates, onPinDrop }: MapPinPickerProps) {
  const { t } = useTranslation();

  function handlePress() {
    const jitter = () => (Math.random() - 0.5) * 0.02;
    onPinDrop({ lat: ORIGIN.lat + jitter(), long: ORIGIN.long + jitter() });
  }

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={t("addField.mapPlaceholder")}
      onPress={handlePress}
      className="rounded-2xl border border-border bg-primary/5 items-center justify-center overflow-hidden"
      style={{ height: 200, marginBottom: 16 }}
    >
      <View
        style={{
          position: "absolute",
          width: "120%",
          height: "120%",
          opacity: 0.15,
        }}
      >
        {Array.from({ length: 6 }).map((_, i) => (
          <View
            key={`h${i}`}
            style={{ position: "absolute", top: `${i * 20}%`, left: 0, right: 0, height: 1, backgroundColor: "#2E7D32" }}
          />
        ))}
        {Array.from({ length: 6 }).map((_, i) => (
          <View
            key={`v${i}`}
            style={{ position: "absolute", left: `${i * 20}%`, top: 0, bottom: 0, width: 1, backgroundColor: "#2E7D32" }}
          />
        ))}
      </View>
      <Text style={{ fontSize: 32 }}>📍</Text>
      {coordinates ? (
        <Text className="text-ink-muted mt-2" style={{ fontSize: 13 }}>
          {coordinates.lat.toFixed(4)}, {coordinates.long.toFixed(4)}
        </Text>
      ) : (
        <Text className="text-ink-muted mt-2 text-center px-6" style={{ fontSize: 13 }}>
          {t("addField.mapPlaceholder")}
        </Text>
      )}
    </Pressable>
  );
}
