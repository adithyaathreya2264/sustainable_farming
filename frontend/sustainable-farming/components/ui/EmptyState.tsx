import React from "react";
import { Text, View } from "react-native";

interface EmptyStateProps {
  icon?: string;
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}

export function EmptyState({ icon = "🌱", title, subtitle, action }: EmptyStateProps) {
  return (
    <View className="items-center justify-center py-16 px-6">
      <Text style={{ fontSize: 48 }}>{icon}</Text>
      <Text className="text-ink font-semibold text-center mt-3" style={{ fontSize: 18 }}>
        {title}
      </Text>
      {subtitle ? (
        <Text className="text-ink-muted text-center mt-1" style={{ fontSize: 15 }}>
          {subtitle}
        </Text>
      ) : null}
      {action ? <View className="mt-5 w-full">{action}</View> : null}
    </View>
  );
}
