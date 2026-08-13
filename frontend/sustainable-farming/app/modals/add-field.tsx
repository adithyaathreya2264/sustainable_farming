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
import { FieldBoundaryMap } from "../../components/FieldBoundaryMap";
import { useToast } from "../../context/ToastContext";
import { useAppState } from "../../hooks/useAppState";
import { addField } from "../../services/fields";
import { LAND_UNITS, toHectares, unitLabel } from "../../utils/unitConversion";
import type { Coordinates, LandUnit } from "../../types/models";

export default function AddFieldModal() {
  const { t } = useTranslation();
  const { showToast } = useToast();
  const defaultUnit = useAppState((s) => s.user.defaultUnit);

  const [points, setPoints] = useState<Coordinates[]>([]);
  const [closed, setClosed] = useState(false);
  const [name, setName] = useState("");
  const [area, setArea] = useState("");
  const [unit, setUnit] = useState<LandUnit>(defaultUnit);
  const [unitPickerOpen, setUnitPickerOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  const isValid = Boolean(closed && points.length >= 3 && name.trim() && Number(area) > 0);

  function handleReset() {
    setPoints([]);
    setClosed(false);
  }

  async function handleSave() {
    if (!closed || points.length < 3) return;
    setSaving(true);
    await addField({
      name: name.trim(),
      areaHectares: toHectares(Number(area), unit),
      boundary: points,
      soilType: "Red Sandy Loam",
    });
    setSaving(false);
    showToast(t("common.savedOffline"));
    router.back();
  }

  return (
    <ScreenContainer>
      <ModalHeader title={t("addField.title")} />

      <FieldBoundaryMap
        points={points}
        closed={closed}
        onAddPoint={(coords) => setPoints((prev) => [...prev, coords])}
        onUndo={() => setPoints((prev) => prev.slice(0, -1))}
        onReset={handleReset}
        onClose={() => setClosed(true)}
      />

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
