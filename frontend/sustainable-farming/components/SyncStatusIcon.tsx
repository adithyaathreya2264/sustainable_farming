import React from "react";
import { Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { useAppState } from "../hooks/useAppState";

export function SyncStatusIcon() {
  const { t } = useTranslation();
  const pending = useAppState((s) => s.interventions.some((i) => !i.isSynced));

  return (
    <View
      accessibilityLabel={pending ? t("profile.pendingSync") : t("profile.synced")}
      className="flex-row items-center"
    >
      <View
        className={`rounded-full ${pending ? "bg-amber-400" : "bg-primary"}`}
        style={{ width: 10, height: 10, marginRight: 6 }}
      />
      <Text className="text-ink-muted" style={{ fontSize: 12 }}>
        {pending ? t("profile.pendingSync") : t("profile.synced")}
      </Text>
    </View>
  );
}
