import React, { useState } from "react";
import { router } from "expo-router";
import { useTranslation } from "react-i18next";
import { ScreenContainer } from "../../components/ui/ScreenContainer";
import { ModalHeader } from "../../components/ModalHeader";
import { TextField, NumericField } from "../../components/ui/TextField";
import { Button } from "../../components/ui/Button";
import {
  BottomSheetPicker,
  PickerField,
} from "../../components/ui/BottomSheetPicker";
import { MapPinPicker, type Coordinates } from "../../components/MapPinPicker";
import { useToast } from "../../context/ToastContext";
import { useAppState } from "../../hooks/useAppState";
import { addField } from "../../services/fields";
import { LAND_UNITS, toHectares, unitLabel } from "../../utils/unitConversion";
import type { LandUnit } from "../../types/models";

export default function AddFieldModal() {
  const { t } = useTranslation();
  const { showToast } = useToast();
  const defaultUnit = useAppState((s) => s.user.defaultUnit);

  const [coordinates, setCoordinates] = useState<Coordinates | null>(null);
  const [name, setName] = useState("");
  const [area, setArea] = useState("");
  const [unit, setUnit] = useState<LandUnit>(defaultUnit);
  const [unitPickerOpen, setUnitPickerOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  const isValid = Boolean(coordinates && name.trim() && Number(area) > 0);

  async function handleSave() {
    if (!coordinates) return;
    setSaving(true);
    await addField({
      name: name.trim(),
      areaHectares: toHectares(Number(area), unit),
      lat: coordinates.lat,
      long: coordinates.long,
      soilType: "Red Sandy Loam",
    });
    setSaving(false);
    showToast(t("common.savedOffline"));
    router.back();
  }

  return (
    <ScreenContainer>
      <ModalHeader title={t("addField.title")} />

      <MapPinPicker coordinates={coordinates} onPinDrop={setCoordinates} />

      <TextField
        label={t("addField.fieldNameLabel")}
        placeholder={t("addField.fieldNamePlaceholder")}
        value={name}
        onChangeText={setName}
      />

      <NumericField
        label={`${t("addField.areaSizeLabel")} (${unitLabel(unit)})`}
        placeholder="0"
        value={area}
        onChangeText={(v) => setArea(v.replace(/[^0-9.]/g, ""))}
      />
      <PickerField
        label={t("onboarding.unitLabel")}
        placeholder={t("onboarding.unitLabel")}
        displayValue={unitLabel(unit)}
        onPress={() => setUnitPickerOpen(true)}
      />
      <BottomSheetPicker
        visible={unitPickerOpen}
        title={t("onboarding.unitLabel")}
        options={LAND_UNITS.map((u) => ({ label: unitLabel(u), value: u }))}
        selectedValue={unit}
        onSelect={(v) => setUnit(v as LandUnit)}
        onClose={() => setUnitPickerOpen(false)}
      />

      <Button
        label={t("addField.confirmSave")}
        disabled={!isValid}
        loading={saving}
        onPress={handleSave}
      />
    </ScreenContainer>
  );
}
