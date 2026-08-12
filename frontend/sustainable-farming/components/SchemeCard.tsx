import React from "react";
import { Pressable, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import type { Scheme } from "../types/models";

export function SchemeCard({
  scheme,
  onPress,
}: {
  scheme: Scheme;
  onPress: () => void;
}) {
  const { t } = useTranslation();

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={scheme.name}
      onPress={onPress}
      className="rounded-2xl border-2 border-primary/40 bg-primary/5 p-4 mb-3"
    >
      <View className="flex-row items-center mb-1">
        <Text style={{ fontSize: 18 }}>✅</Text>
        <View className="bg-info rounded-full px-2.5 py-0.5 ml-2">
          <Text className="text-white" style={{ fontSize: 12 }}>
            {scheme.level === "central" ? t("schemes.central") : t("schemes.state")}
          </Text>
        </View>
      </View>
      <Text className="text-ink font-semibold" style={{ fontSize: 16 }}>
        {t("schemes.eligibleFor")} {scheme.name}
      </Text>
      <Text className="text-ink-muted mt-1" numberOfLines={2} style={{ fontSize: 14 }}>
        {scheme.summary}
      </Text>
    </Pressable>
  );
}
