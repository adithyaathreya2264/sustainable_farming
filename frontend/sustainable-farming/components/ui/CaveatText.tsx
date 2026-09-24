import React from "react";
import { Text } from "react-native";

/** Small muted text for caveats and qualifiers that must travel with a result. */
export function CaveatText({ children, className = "mb-2" }: { children: React.ReactNode; className?: string }) {
  return (
    <Text className={`text-ink-muted ${className}`} style={{ fontSize: 12 }}>
      {children}
    </Text>
  );
}
