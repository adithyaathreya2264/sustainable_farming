import React from "react";
import { Pressable, Text, View } from "react-native";
import { router } from "expo-router";
import { useTranslation } from "react-i18next";

export function ModalHeader({ title }: { title: string }) {
  const { t } = useTranslation();

  return (
    <View className="flex-row items-center justify-between mb-4">
      <Text className="text-ink font-bold" style={{ fontSize: 20 }}>
        {title}
      </Text>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={t("common.cancel")}
        onPress={() => router.back()}
        style={{ width: 36, height: 36, alignItems: "center", justifyContent: "center" }}
      >
        <Text className="text-ink-muted" style={{ fontSize: 20 }}>
          ✕
        </Text>
      </Pressable>
    </View>
  );
}
