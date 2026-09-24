import React, { useState } from "react";
import { Image, Text, View, type LayoutChangeEvent } from "react-native";
import type { InsectDetection } from "../../services/ml";

/** The checked photo with each detection's box drawn over it. Boxes arrive as
 * fractions of the image, so they scale with whatever width the photo gets. */
export function DetectionOverlay({
  uri,
  aspectRatio,
  detections,
}: {
  uri: string;
  aspectRatio: number;
  detections: InsectDetection[];
}) {
  const [width, setWidth] = useState(0);
  const height = width / (aspectRatio || 1);
  const onLayout = (e: LayoutChangeEvent) => setWidth(e.nativeEvent.layout.width);

  return (
    <View onLayout={onLayout} className="w-full rounded-2xl overflow-hidden mb-3">
      {width > 0 && (
        <View style={{ width, height }}>
          <Image source={{ uri }} style={{ width, height }} resizeMode="cover" />
          {detections.map((d, i) => (
            <View
              key={`${d.key}-${i}`}
              style={{
                position: "absolute",
                left: d.box.x1 * width,
                top: d.box.y1 * height,
                width: (d.box.x2 - d.box.x1) * width,
                height: (d.box.y2 - d.box.y1) * height,
                borderWidth: 2,
                borderColor: d.pestOfThisCrop ? "#D32F2F" : "#FFFFFF",
                borderRadius: 4,
              }}
            >
              <Text
                style={{ fontSize: 11, color: "#FFFFFF", backgroundColor: "rgba(0,0,0,0.6)", paddingHorizontal: 4, alignSelf: "flex-start" }}
                numberOfLines={1}
              >
                {d.displayName}
              </Text>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}
