import React, { useState } from "react";
import { Alert, Pressable, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { router } from "expo-router";
import { ScreenContainer } from "../../components/ui/ScreenContainer";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { EmptyState } from "../../components/ui/EmptyState";
import { useAppState } from "../../hooks/useAppState";
import { useToast } from "../../context/ToastContext";
import { deleteField } from "../../services/fields";
import { formatArea } from "../../utils/unitConversion";
import { formatDate } from "../../utils/format";
import { soilTypeDisplay } from "../../utils/soilTypes";
import type { Crop } from "../../types/models";

function cropLabel(crops: Crop[], cropId: string, varietyId: string) {
  const crop = crops.find((c) => c.id === cropId);
  const variety = crop?.varieties.find((v) => v.id === varietyId);
  return crop ? `${crop.name}${variety ? ` (${variety.name})` : ""}` : "Unknown crop";
}

export default function FieldsScreen() {
  const { t } = useTranslation();
  const { showToast } = useToast();
  const fields = useAppState((s) => s.fields);
  const plantings = useAppState((s) => s.plantings);
  const crops = useAppState((s) => s.crops);
  const defaultUnit = useAppState((s) => s.user.defaultUnit);
  const state = useAppState((s) => s.user.state);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  function handleRemove(fieldId: string, fieldName: string, hasPlantings: boolean) {
    if (hasPlantings) {
      Alert.alert(t("fields.removeBlockedTitle"), t("fields.removeBlockedSubtitle"));
      return;
    }
    Alert.alert(
      t("fields.removeConfirmTitle"),
      t("fields.removeConfirmSubtitle", { name: fieldName }),
      [
        { text: t("common.cancel"), style: "cancel" },
        {
          text: t("fields.remove"),
          style: "destructive",
          onPress: async () => {
            setDeletingId(fieldId);
            try {
              await deleteField(fieldId);
              showToast(t("fields.removed"));
            } catch {
              showToast(t("common.saveFailed"));
            } finally {
              setDeletingId(null);
            }
          },
        },
      ]
    );
  }

  return (
    <ScreenContainer>
      <View className="flex-row items-center justify-between mb-4">
        <Text className="text-ink font-bold" style={{ fontSize: 22 }}>
          {t("fields.title")}
        </Text>
      </View>

      {fields.length === 0 ? (
        <EmptyState
          icon="🌾"
          title={t("fields.noFieldsTitle")}
          subtitle={t("fields.noFieldsSubtitle")}
          action={
            <Button
              label={t("fields.addField")}
              onPress={() => router.push("/modals/add-field")}
            />
          }
        />
      ) : (
        <>
          {fields.map((field) => {
            const fieldPlantings = plantings.filter((p) => p.fieldId === field.id);
            return (
              <Card key={field.id} className="mb-3">
                <View className="flex-row items-center justify-between mb-1">
                  <Text className="text-ink font-semibold flex-1" style={{ fontSize: 16 }}>
                    {field.name}
                  </Text>
                  <Text className="text-ink-muted mr-3" style={{ fontSize: 13 }}>
                    {formatArea(field.areaHectares, defaultUnit, state)}
                  </Text>
                  <Pressable
                    accessibilityRole="button"
                    accessibilityLabel={t("fields.remove")}
                    disabled={deletingId === field.id}
                    onPress={() =>
                      handleRemove(field.id, field.name, fieldPlantings.length > 0)
                    }
                    hitSlop={8}
                    style={{ opacity: deletingId === field.id ? 0.4 : 1 }}
                  >
                    <Text className="text-danger" style={{ fontSize: 13 }}>
                      {t("fields.remove")}
                    </Text>
                  </Pressable>
                </View>
                <Text className="text-ink-muted mb-2" style={{ fontSize: 13 }}>
                  {soilTypeDisplay(field.soilType, t)}
                </Text>

                {fieldPlantings.length === 0 ? (
                  <Button
                    label={t("fields.startPlanting")}
                    variant="outline"
                    onPress={() =>
                      router.push({
                        pathname: "/modals/add-planting",
                        params: { fieldId: field.id },
                      })
                    }
                  />
                ) : (
                  fieldPlantings.map((planting) => (
                    <Pressable
                      key={planting.id}
                      accessibilityRole="button"
                      onPress={() => router.push(`/ledger/${planting.id}`)}
                      className="rounded-xl bg-primary/5 border border-primary/20 px-3 py-2 mb-2"
                    >
                      <Text className="text-ink font-medium" style={{ fontSize: 14 }}>
                        {cropLabel(crops, planting.cropId, planting.varietyId)}
                      </Text>
                      <Text className="text-ink-muted" style={{ fontSize: 12 }}>
                        {t(
                          planting.status === "active"
                            ? "fields.activePlantings"
                            : "fields.harvested"
                        )}{" "}
                        · {formatDate(planting.sowingDate)}
                      </Text>
                    </Pressable>
                  ))
                )}
              </Card>
            );
          })}
          <Button
            label={t("fields.addField")}
            variant="outline"
            onPress={() => router.push("/modals/add-field")}
          />
        </>
      )}
    </ScreenContainer>
  );
}
