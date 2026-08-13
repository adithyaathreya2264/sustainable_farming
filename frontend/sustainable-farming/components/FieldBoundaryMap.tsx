import React, { useState } from "react";
import {
  LayoutChangeEvent,
  Pressable,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from "react-native";
import Svg, { Circle, Polygon, Polyline } from "react-native-svg";
import { useTranslation } from "react-i18next";
import { Button } from "./ui/Button";
import { colors } from "../theme";
import type { Coordinates } from "../types/models";

interface FieldBoundaryMapProps {
  points: Coordinates[];
  closed: boolean;
  onAddPoint: (coords: Coordinates) => void;
  onUndo: () => void;
  onReset: () => void;
  onClose: () => void;
}

interface CanvasSize {
  width: number;
  height: number;
}

// Mysuru district centroid, used as the mock canvas origin. The real
// implementation swaps this component for `@rnmapbox/maps` (per the
// Technical Design doc) behind the same point-array contract, with offline
// tile caching for a 5km radius around the saved field.
const ORIGIN: Coordinates = { lat: 12.2958, long: 76.6394 };

/** Assumed ground distance (meters) spanned by the canvas width, for the mock projection. */
const GROUND_EXTENT_METERS = 300;
const METERS_PER_DEGREE_LAT = 111320;

function metersPerDegreeLong(latDeg: number): number {
  return METERS_PER_DEGREE_LAT * Math.cos((latDeg * Math.PI) / 180);
}

function pixelToGeo(x: number, y: number, canvas: CanvasSize): Coordinates {
  const metersPerPixel = GROUND_EXTENT_METERS / canvas.width;
  const dxMeters = (x - canvas.width / 2) * metersPerPixel;
  const dyMeters = (canvas.height / 2 - y) * metersPerPixel;
  return {
    lat: ORIGIN.lat + dyMeters / METERS_PER_DEGREE_LAT,
    long: ORIGIN.long + dxMeters / metersPerDegreeLong(ORIGIN.lat),
  };
}

function geoToPixel(coord: Coordinates, canvas: CanvasSize): { x: number; y: number } {
  const metersPerPixel = GROUND_EXTENT_METERS / canvas.width;
  const dxMeters = (coord.long - ORIGIN.long) * metersPerDegreeLong(ORIGIN.lat);
  const dyMeters = (coord.lat - ORIGIN.lat) * METERS_PER_DEGREE_LAT;
  return {
    x: canvas.width / 2 + dxMeters / metersPerPixel,
    y: canvas.height / 2 - dyMeters / metersPerPixel,
  };
}

export function FieldBoundaryMap({
  points,
  closed,
  onAddPoint,
  onUndo,
  onReset,
  onClose,
}: FieldBoundaryMapProps) {
  const { t } = useTranslation();
  const { height: windowHeight } = useWindowDimensions();
  const [canvas, setCanvas] = useState<CanvasSize | null>(null);

  const canvasHeight = Math.round(windowHeight * 0.75);

  function handleLayout(e: LayoutChangeEvent) {
    const { width, height } = e.nativeEvent.layout;
    setCanvas({ width, height });
  }

  function handlePress(e: { nativeEvent: { locationX: number; locationY: number } }) {
    if (closed || !canvas) return;
    const { locationX, locationY } = e.nativeEvent;
    onAddPoint(pixelToGeo(locationX, locationY, canvas));
  }

  const pixelPoints = canvas ? points.map((p) => geoToPixel(p, canvas)) : [];
  const pointsAttr = pixelPoints.map((p) => `${p.x},${p.y}`).join(" ");

  const statusKey =
    points.length === 0
      ? "addField.tapToStart"
      : closed
        ? "addField.boundaryClosed"
        : "addField.tapToAddNext";

  return (
    <View className="mb-4">
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={t(statusKey, { count: points.length })}
        onPress={handlePress}
        onLayout={handleLayout}
        className="rounded-2xl border border-border bg-primary/5 overflow-hidden"
        style={{ height: canvasHeight }}
      >
        <View style={StyleSheet.absoluteFill}>
          {Array.from({ length: 6 }).map((_, i) => (
            <View
              key={`h${i}`}
              style={{
                position: "absolute",
                top: `${i * 20}%`,
                left: 0,
                right: 0,
                height: 1,
                backgroundColor: colors.primary,
                opacity: 0.15,
              }}
            />
          ))}
          {Array.from({ length: 6 }).map((_, i) => (
            <View
              key={`v${i}`}
              style={{
                position: "absolute",
                left: `${i * 20}%`,
                top: 0,
                bottom: 0,
                width: 1,
                backgroundColor: colors.primary,
                opacity: 0.15,
              }}
            />
          ))}
        </View>

        {canvas && points.length > 0 && (
          <Svg style={StyleSheet.absoluteFill} width={canvas.width} height={canvas.height}>
            {closed ? (
              <Polygon
                points={pointsAttr}
                stroke={colors.primary}
                strokeWidth={3}
                fill={colors.primary}
                fillOpacity={0.25}
              />
            ) : (
              points.length >= 2 && (
                <Polyline
                  points={pointsAttr}
                  stroke={colors.primary}
                  strokeWidth={3}
                  fill="none"
                />
              )
            )}
            {pixelPoints.map((p, i) => (
              <Circle
                key={i}
                cx={p.x}
                cy={p.y}
                r={7}
                fill={i === 0 ? colors.primary : "#FFFFFF"}
                stroke={colors.primary}
                strokeWidth={2}
              />
            ))}
          </Svg>
        )}

        {points.length === 0 && (
          <View className="flex-1 items-center justify-center px-8">
            <Text style={{ fontSize: 32 }}>📍</Text>
            <Text className="text-ink-muted mt-2 text-center" style={{ fontSize: 13 }}>
              {t("addField.tapToStart")}
            </Text>
          </View>
        )}
      </Pressable>

      <Text className="text-ink-muted mt-2 mb-2 text-center" style={{ fontSize: 13 }}>
        {t(statusKey, { count: points.length })}
      </Text>

      {!closed && points.length > 0 && (
        <View className="flex-row mb-2" style={{ gap: 8 }}>
          <View style={{ flex: 1 }}>
            <Button
              label={t("addField.undo")}
              variant="outline"
              fullWidth
              onPress={onUndo}
            />
          </View>
          <View style={{ flex: 1 }}>
            <Button
              label={t("addField.reset")}
              variant="outline"
              fullWidth
              onPress={onReset}
            />
          </View>
        </View>
      )}

      {!closed && (
        <Button
          label={t("addField.closeBoundary")}
          disabled={points.length < 3}
          onPress={onClose}
        />
      )}

      {closed && (
        <Button label={t("addField.redraw")} variant="outline" onPress={onReset} />
      )}
    </View>
  );
}
