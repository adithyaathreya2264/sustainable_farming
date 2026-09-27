import React, { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Image,
  LayoutChangeEvent,
  Pressable,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from "react-native";
import * as Location from "expo-location";
import Svg, { Circle, Polygon, Polyline } from "react-native-svg";
import { useTranslation } from "react-i18next";
import { Button } from "./ui/Button";
import { colors } from "../theme";
import {
  MAP_TILER_AVAILABLE,
  TILE_SIZE,
  metersPerPixel,
  tilesForCanvas,
  type PlacedTile,
} from "../utils/mapTiles";
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

// Fallback when GPS/the map key is unavailable: a fixed origin (Mysuru
// district centroid) and an assumed ground extent, same as this component's
// original mock-only version. The farmer can still tap out a boundary; it
// just isn't drawn against real imagery.
const FALLBACK_ORIGIN: Coordinates = { lat: 12.2958, long: 76.6394 };
const FALLBACK_GROUND_EXTENT_METERS = 300;
const METERS_PER_DEGREE_LAT = 111320;

// Zoom 18 spans roughly 150-250m across a typical phone screen width at
// India's latitudes — enough detail to see field edges, not so tight that a
// single tap-drag overshoots the plot.
const MAP_ZOOM = 18;

function metersPerDegreeLong(latDeg: number): number {
  return METERS_PER_DEGREE_LAT * Math.cos((latDeg * Math.PI) / 180);
}

function pixelToGeo(
  x: number,
  y: number,
  canvas: CanvasSize,
  origin: Coordinates,
  groundMetersPerPixel: number
): Coordinates {
  const dxMeters = (x - canvas.width / 2) * groundMetersPerPixel;
  const dyMeters = (canvas.height / 2 - y) * groundMetersPerPixel;
  return {
    lat: origin.lat + dyMeters / METERS_PER_DEGREE_LAT,
    long: origin.long + dxMeters / metersPerDegreeLong(origin.lat),
  };
}

function geoToPixel(
  coord: Coordinates,
  canvas: CanvasSize,
  origin: Coordinates,
  groundMetersPerPixel: number
): { x: number; y: number } {
  const dxMeters = (coord.long - origin.long) * metersPerDegreeLong(origin.lat);
  const dyMeters = (coord.lat - origin.lat) * METERS_PER_DEGREE_LAT;
  return {
    x: canvas.width / 2 + dxMeters / groundMetersPerPixel,
    y: canvas.height / 2 - dyMeters / groundMetersPerPixel,
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
  const [gpsOrigin, setGpsOrigin] = useState<Coordinates | null>(null);
  const [locating, setLocating] = useState(true);
  const [locationDenied, setLocationDenied] = useState(false);

  const canvasHeight = Math.round(windowHeight * 0.75);

  // Real GPS fix, once — recentering mid-drawing would shift every point
  // already tapped, since the geo math is relative to this origin.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const perm = await Location.requestForegroundPermissionsAsync();
        if (perm.status !== "granted") {
          if (!cancelled) setLocationDenied(true);
          return;
        }
        const pos = await Location.getCurrentPositionAsync({
          accuracy: Location.Accuracy.High,
        });
        if (!cancelled) {
          setGpsOrigin({ lat: pos.coords.latitude, long: pos.coords.longitude });
        }
      } catch {
        if (!cancelled) setLocationDenied(true);
      } finally {
        if (!cancelled) setLocating(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const hasRealMap = Boolean(gpsOrigin && MAP_TILER_AVAILABLE);
  const origin = gpsOrigin ?? FALLBACK_ORIGIN;
  const groundMetersPerPixel =
    gpsOrigin && canvas
      ? metersPerPixel(gpsOrigin.lat, MAP_ZOOM)
      : FALLBACK_GROUND_EXTENT_METERS / (canvas?.width ?? 1);

  const mapTiles: PlacedTile[] = useMemo(() => {
    if (!hasRealMap || !canvas || !gpsOrigin) return [];
    return tilesForCanvas(gpsOrigin, canvas, MAP_ZOOM);
  }, [hasRealMap, canvas, gpsOrigin]);

  function handleLayout(e: LayoutChangeEvent) {
    const { width, height } = e.nativeEvent.layout;
    setCanvas({ width, height });
  }

  function handlePress(e: { nativeEvent: { locationX: number; locationY: number } }) {
    if (closed || !canvas) return;
    const { locationX, locationY } = e.nativeEvent;
    onAddPoint(pixelToGeo(locationX, locationY, canvas, origin, groundMetersPerPixel));
  }

  const pixelPoints = canvas
    ? points.map((p) => geoToPixel(p, canvas, origin, groundMetersPerPixel))
    : [];
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
        {mapTiles.length > 0 ? (
          <View style={StyleSheet.absoluteFill}>
            {mapTiles.map((tile) => (
              <Image
                key={tile.key}
                source={{ uri: tile.url }}
                style={{
                  position: "absolute",
                  left: tile.left,
                  top: tile.top,
                  width: TILE_SIZE,
                  height: TILE_SIZE,
                }}
              />
            ))}
          </View>
        ) : (
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
        )}

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

        {locating && points.length === 0 && (
          <View className="flex-1 items-center justify-center px-8">
            <ActivityIndicator color={colors.primary} />
            <Text className="text-ink-muted mt-2 text-center" style={{ fontSize: 13 }}>
              {t("addField.locatingYou")}
            </Text>
          </View>
        )}

        {!locating && points.length === 0 && (
          <View className="flex-1 items-center justify-center px-8">
            <Text style={{ fontSize: 32 }}>📍</Text>
            <Text className="text-ink-muted mt-2 text-center" style={{ fontSize: 13 }}>
              {t("addField.tapToStart")}
            </Text>
          </View>
        )}
      </Pressable>

      {!locating && locationDenied && (
        <Text className="text-ink-muted mt-2 text-center" style={{ fontSize: 12 }}>
          {t("addField.locationUnavailable")}
        </Text>
      )}

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
