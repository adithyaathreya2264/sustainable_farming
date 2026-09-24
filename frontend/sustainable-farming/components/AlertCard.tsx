import React from "react";
import { Pressable, Text, View } from "react-native";
import type { Alert } from "../types/models";
import { ConfidencePill } from "./ui/ConfidencePill";

const SEVERITY_STYLE = {
  critical: { border: "border-danger", bg: "bg-danger/10", badge: "bg-danger" },
  advisory: { border: "border-danger/60", bg: "bg-danger/5", badge: "bg-danger/70" },
  info: { border: "border-border", bg: "bg-surface", badge: "bg-ink-muted" },
} as const;

export function AlertCard({ alert, onPress }: { alert: Alert; onPress: () => void }) {
  const style = SEVERITY_STYLE[alert.severity ?? "info"];

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={alert.headline}
      onPress={onPress}
      className={`rounded-2xl border-2 ${style.border} ${style.bg} p-4 mb-3`}
    >
      <View className="flex-row items-center justify-between mb-1">
        <Text style={{ fontSize: 20 }}>⚠️</Text>
        <ConfidencePill label={alert.confidenceLabel} className={style.badge} />
      </View>
      <Text className="text-ink font-semibold" numberOfLines={3} style={{ fontSize: 16 }}>
        {alert.headline}
      </Text>
    </Pressable>
  );
}
