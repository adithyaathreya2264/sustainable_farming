import React, { useEffect, useRef } from "react";
import { Animated, View, type DimensionValue } from "react-native";

interface SkeletonLoaderProps {
  width?: DimensionValue;
  height?: number;
  className?: string;
}

export function SkeletonLoader({ width = "100%", height = 16, className = "" }: SkeletonLoaderProps) {
  const opacity = useRef(new Animated.Value(0.4)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 1, duration: 600, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0.4, duration: 600, useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [opacity]);

  return (
    <Animated.View
      className={`bg-border rounded-lg ${className}`}
      style={{ width, height, opacity }}
    />
  );
}

export function SkeletonCard() {
  return (
    <View className="bg-surface rounded-2xl p-4 border border-border mb-3">
      <SkeletonLoader width="60%" height={16} className="mb-2" />
      <SkeletonLoader width="90%" height={14} className="mb-2" />
      <SkeletonLoader width="40%" height={14} />
    </View>
  );
}
