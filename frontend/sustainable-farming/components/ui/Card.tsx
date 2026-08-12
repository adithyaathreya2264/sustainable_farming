import React from "react";
import { View, type ViewProps } from "react-native";

export function Card({ className = "", style, ...props }: ViewProps & { className?: string }) {
  return (
    <View
      className={`bg-surface rounded-2xl p-4 border border-border ${className}`}
      style={[{ shadowColor: "#000", shadowOpacity: 0.04, shadowRadius: 6, shadowOffset: { width: 0, height: 2 }, elevation: 1 }, style]}
      {...props}
    />
  );
}
