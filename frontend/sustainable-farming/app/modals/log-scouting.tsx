import React, { useMemo, useState } from "react";
import { Text } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import { ScreenContainer } from "../../components/ui/ScreenContainer";
import { ModalHeader } from "../../components/ModalHeader";
import { Button } from "../../components/ui/Button";
import { NumericField, TextField } from "../../components/ui/TextField";
import { DateField } from "../../components/ui/DateField";
import { EmptyState } from "../../components/ui/EmptyState";
import {
  BottomSheetPicker,
  PickerField,
} from "../../components/ui/BottomSheetPicker";
import { useToast } from "../../context/ToastContext";
import { useAppState } from "../../hooks/useAppState";
import { addScoutingObservation } from "../../services/scouting";
import { metricForPlanting } from "../../lib/scoutingMetrics";

const today = new Date().toISOString().slice(0, 10);

export default function LogScoutingModal() {
  const { t } = useTranslation();
  const { showToast } = useToast();
  const params = useLocalSearchParams<{ plantingId?: string }>();
  const plantings = useAppState((s) => s.plantings);
  const fields = useAppState((s) => s.fields);
  const crops = useAppState((s) => s.crops);

  const [plantingId, setPlantingId] = useState(params.plantingId ?? "");
  const [value, setValue] = useState("");
  const [observedAt, setObservedAt] = useState(today);
  const [notes, setNotes] = useState("");
  const [plantingPickerOpen, setPlantingPickerOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  const plantingOptions = useMemo(
    () =>
      plantings.map((p) => {
        const field = fields.find((f) => f.id === p.fieldId);
        return { label: field ? field.name : p.id, value: p.id };
      }),
    [plantings, fields]
  );

  const selectedPlanting = plantings.find((p) => p.id === plantingId);
  const crop = crops.find((c) => c.id === selectedPlanting?.cropId);
  const metric = selectedPlanting
    ? metricForPlanting(crop, selectedPlanting.sowingDate)
    : undefined;

  const selectedLabel = plantingOptions.find((p) => p.value === plantingId)?.label;
  const isValid = Boolean(plantingId && value && metric);

  async function handleSave() {
    if (!metric) return;
    setSaving(true);
    try {
      await addScoutingObservation({
        plantingId,
        metricKey: metric.metricKey,
        metricValue: Number(value),
        observedAt,
        notes: notes.trim() || undefined,
      });
      showToast(t("common.saved"));
      router.back();
    } catch {
      showToast(t("common.saveFailed"));
    } finally {
      setSaving(false);
    }
  }

  if (plantings.length === 0) {
    return (
      <ScreenContainer>
        <ModalHeader title={t("scouting.title")} />
        <EmptyState
          icon="🔍"
          title={t("fields.noFieldsTitle")}
          subtitle={t("fields.noFieldsSubtitle")}
        />
      </ScreenContainer>
    );
  }

  return (
    <ScreenContainer>
      <ModalHeader title={t("scouting.title")} />

      <PickerField
        label={t("scouting.plantingLabel")}
        placeholder={t("scouting.plantingLabel")}
        displayValue={selectedLabel}
        onPress={() => setPlantingPickerOpen(true)}
      />
      <BottomSheetPicker
        visible={plantingPickerOpen}
        title={t("scouting.plantingLabel")}
        options={plantingOptions}
        selectedValue={plantingId}
        onSelect={setPlantingId}
        onClose={() => setPlantingPickerOpen(false)}
      />

      {plantingId && !metric ? (
        <EmptyState
          icon="✅"
          title={t("scouting.noMetricTitle")}
          subtitle={t("scouting.noMetricSubtitle")}
        />
      ) : null}

      {metric ? (
        <>
          <NumericField
            label={`${t(metric.labelKey)} (${metric.unit})`}
            placeholder="0"
            value={value}
            onChangeText={(v) => setValue(v.replace(/[^0-9.]/g, ""))}
          />
          <DateField
            label={t("scouting.dateLabel")}
            value={observedAt}
            onChange={setObservedAt}
            maximumDate={new Date()}
          />
          <TextField
            label={t("scouting.notesLabel")}
            placeholder={t("scouting.notesLabel")}
            value={notes}
            onChangeText={setNotes}
          />
          <Button
            label={t("scouting.save")}
            disabled={!isValid}
            loading={saving}
            onPress={handleSave}
          />
        </>
      ) : null}
    </ScreenContainer>
  );
}
