import React, { useMemo, useState } from "react";
import { router, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import { ScreenContainer } from "../../components/ui/ScreenContainer";
import { ModalHeader } from "../../components/ModalHeader";
import { Button } from "../../components/ui/Button";
import { DateField } from "../../components/ui/DateField";
import { EmptyState } from "../../components/ui/EmptyState";
import {
  BottomSheetPicker,
  PickerField,
} from "../../components/ui/BottomSheetPicker";
import { useToast } from "../../context/ToastContext";
import { useAppState } from "../../hooks/useAppState";
import { addPlanting } from "../../services/plantings";

const today = new Date().toISOString().slice(0, 10);

export default function AddPlantingModal() {
  const { t } = useTranslation();
  const { showToast } = useToast();
  const params = useLocalSearchParams<{ fieldId?: string }>();
  const fields = useAppState((s) => s.fields);
  // Server-owned reference data (backend/api/v1/catalog.py), cached by
  // fetchAndCacheCatalog() — see hooks/useSyncTriggers.ts. Reading it
  // reactively here (rather than the old direct mock-JSON import) means the
  // picker always reflects real crop_id/variety_id FKs the backend accepts.
  const crops = useAppState((s) => s.crops);

  const [fieldId, setFieldId] = useState(params.fieldId ?? "");
  const [cropId, setCropId] = useState("");
  const [varietyId, setVarietyId] = useState("");
  const [sowingDate, setSowingDate] = useState(today);
  const [fieldPickerOpen, setFieldPickerOpen] = useState(false);
  const [cropPickerOpen, setCropPickerOpen] = useState(false);
  const [varietyPickerOpen, setVarietyPickerOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  const selectedCrop = useMemo(() => crops.find((c) => c.id === cropId), [crops, cropId]);
  const selectedField = fields.find((f) => f.id === fieldId);

  const isValid = Boolean(fieldId && cropId && varietyId && sowingDate);

  async function handleSave() {
    setSaving(true);
    await addPlanting({ fieldId, cropId, varietyId, sowingDate });
    setSaving(false);
    showToast(t("common.savedOffline"));
    router.back();
  }

  if (crops.length === 0) {
    return (
      <ScreenContainer>
        <ModalHeader title={t("addPlanting.title")} />
        <EmptyState
          icon="🌱"
          title={t("addPlanting.catalogUnavailableTitle")}
          subtitle={t("addPlanting.catalogUnavailableSubtitle")}
        />
      </ScreenContainer>
    );
  }

  return (
    <ScreenContainer>
      <ModalHeader title={t("addPlanting.title")} />

      <PickerField
        label={t("addPlanting.fieldLabel")}
        placeholder={t("addPlanting.fieldLabel")}
        displayValue={selectedField?.name}
        onPress={() => setFieldPickerOpen(true)}
      />
      <BottomSheetPicker
        visible={fieldPickerOpen}
        title={t("addPlanting.fieldLabel")}
        options={fields.map((f) => ({ label: f.name, value: f.id }))}
        selectedValue={fieldId}
        onSelect={setFieldId}
        onClose={() => setFieldPickerOpen(false)}
      />

      <PickerField
        label={t("addPlanting.cropLabel")}
        placeholder={t("addPlanting.selectCrop")}
        displayValue={selectedCrop?.name}
        onPress={() => setCropPickerOpen(true)}
      />
      <BottomSheetPicker
        visible={cropPickerOpen}
        title={t("addPlanting.selectCrop")}
        options={crops.map((c) => ({ label: c.name, value: c.id }))}
        selectedValue={cropId}
        onSelect={(v) => {
          setCropId(v);
          setVarietyId("");
        }}
        onClose={() => setCropPickerOpen(false)}
      />

      <PickerField
        label={t("addPlanting.varietyLabel")}
        placeholder={t("addPlanting.selectVariety")}
        displayValue={selectedCrop?.varieties.find((v) => v.id === varietyId)?.name}
        disabled={!selectedCrop}
        onPress={() => setVarietyPickerOpen(true)}
      />
      <BottomSheetPicker
        visible={varietyPickerOpen}
        title={t("addPlanting.selectVariety")}
        options={(selectedCrop?.varieties ?? []).map((v) => ({
          label: v.name,
          value: v.id,
        }))}
        selectedValue={varietyId}
        onSelect={setVarietyId}
        onClose={() => setVarietyPickerOpen(false)}
      />

      <DateField
        label={t("addPlanting.sowingDateLabel")}
        value={sowingDate}
        onChange={setSowingDate}
        maximumDate={new Date()}
      />

      <Button
        label={t("addPlanting.startTracking")}
        disabled={!isValid}
        loading={saving}
        onPress={handleSave}
      />
    </ScreenContainer>
  );
}
