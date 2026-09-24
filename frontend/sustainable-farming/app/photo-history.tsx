import React, { useCallback, useState } from "react";
import { ActivityIndicator, Image, Pressable, Text, View } from "react-native";
import { useFocusEffect } from "expo-router";
import { useTranslation } from "react-i18next";
import { ScreenContainer } from "../components/ui/ScreenContainer";
import { ModalHeader } from "../components/ModalHeader";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { CaveatText } from "../components/ui/CaveatText";
import { useToast } from "../context/ToastContext";
import { useAppState } from "../hooks/useAppState";
import { API_BASE_URL } from "../lib/apiClient";
import { formatDate } from "../utils/format";
import {
  deleteInference,
  inferenceImagePath,
  listInferences,
  mlErrorMessage,
  type InferenceRecord,
} from "../services/ml";

/**
 * Every photo the farmer has sent for a model check. Photos are stored on the
 * server for this history; deleting one here removes the file, not just the
 * row.
 */
export default function PhotoHistoryScreen() {
  const { t } = useTranslation();
  const { showToast } = useToast();
  const token = useAppState((s) => s.authToken);
  const [items, setItems] = useState<InferenceRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useFocusEffect(
    useCallback(() => {
      listInferences()
        .then((rows) => setItems(rows.filter((r) => r.hasImage)))
        .catch((err) => setError(mlErrorMessage(err, t)));
    }, [t])
  );

  async function remove(id: string) {
    try {
      await deleteInference(id);
      setItems((cur) => (cur ?? []).filter((i) => i.id !== id));
      showToast(t("photoHistory.deleted"));
    } catch {
      showToast(t("common.saveFailed"));
    }
  }

  return (
    <ScreenContainer>
      <ModalHeader title={t("photoHistory.title")} />
      <CaveatText className="mb-3">{t("photoHistory.storedNote")}</CaveatText>
      {error && <EmptyState icon="📷" title={error} />}
      {!error && items === null && <ActivityIndicator color="#2E7D32" />}
      {!error && items?.length === 0 && <EmptyState icon="📷" title={t("photoHistory.empty")} />}
      {items?.map((item) => (
        <Card key={item.id} className="mb-2 flex-row items-center">
          <Image
            source={{
              uri: `${API_BASE_URL}${inferenceImagePath(item.id)}`,
              headers: token ? { Authorization: `Bearer ${token}` } : undefined,
            }}
            style={{ width: 56, height: 56, borderRadius: 8, marginRight: 12, backgroundColor: "#F5F5F5" }}
          />
          <View className="flex-1">
            <Text className="text-ink font-medium" style={{ fontSize: 14 }}>
              {t(`photoHistory.model.${item.model}`, {
                defaultValue: t(`photoHistory.model.${item.model.replace(/^leaf_condition_.*/, "leaf_condition")}`),
              })}
            </Text>
            <Text className="text-ink-muted" style={{ fontSize: 12 }}>
              {formatDate(item.createdAt)}
              {item.outcome !== "ok" ? ` · ${t("photoHistory.notChecked")}` : ""}
            </Text>
          </View>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t("photoHistory.delete")}
            onPress={() => remove(item.id)}
            className="px-3 py-2"
            style={{ minHeight: 48, justifyContent: "center" }}
          >
            <Text className="text-danger" style={{ fontSize: 14 }}>
              {t("photoHistory.delete")}
            </Text>
          </Pressable>
        </Card>
      ))}
    </ScreenContainer>
  );
}
