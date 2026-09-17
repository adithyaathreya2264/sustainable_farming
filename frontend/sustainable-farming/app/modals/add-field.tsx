import React, { useEffect, useState } from "react";
import { Text } from "react-native";
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
import {
  lookupSoilType,
  type SoilLookupConfidence,
} from "../../services/soilLookup";
import {
  availableLandUnits,
  toHectares,
  unitLabel,
} from "../../utils/unitConversion";
import type { Coordinates, LandUnit } from "../../types/models";

export default function AddFieldModal() {
  const { t } = useTranslation();
  const { showToast } = useToast();
  const defaultUnit = useAppState((s) => s.user.defaultUnit);
  const state = useAppState((s) => s.user.state);
  const district = useAppState((s) => s.user.district);
  // Non-standardized units (Bigha, Katha, ...) only appear once `state` has
  // an entry in the (unverified — see docs/unit-conversions.md) lookup table.
  const units = availableLandUnits(state);

  const [points, setPoints] = useState<Coordinates[]>([]);
  const [closed, setClosed] = useState(false);
  const [name, setName] = useState("");
  const [area, setArea] = useState("");
  const [unit, setUnit] = useState<LandUnit>(defaultUnit);
  const [unitPickerOpen, setUnitPickerOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [soilType, setSoilType] = useState("");
  const [soilConfidence, setSoilConfidence] =
    useState<SoilLookupConfidence | null>(null);
  const [soilLookupFailed, setSoilLookupFailed] = useState(false);

  // Pre-fill from GET /api/v1/soil-lookup (backend/services/soil_lookup.py,
  // Task 3.1) when the farmer's location is known. Best-effort, and never
  // blocks field creation either way — but a genuine request failure
  // (offline, expired session, server error) is deliberately distinguished
  // from a legitimate "no data for this location" (confidence: "none"):
  // the latter needs no comment (blank is the correct, honest outcome), the
  // former surfaces a small inline hint below the field so "we don't know"
  // and "something went wrong, try again" don't look identical to the
  // farmer. Reuse this failed/no-data split, not a blanket silent catch, if
  // this best-effort-suggestion pattern gets used elsewhere.
  useEffect(() => {
    if (!state || !district) return;
    let cancelled = false;
    setSoilLookupFailed(false);
    lookupSoilType(state, district)
      .then((result) => {
        if (cancelled || result.confidence === "none") return;
        setSoilType(result.soilType ?? "");
        setSoilConfidence(result.confidence);
      })
      .catch(() => {
        if (!cancelled) setSoilLookupFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [state, district]);

  function soilTypeLabel(): string {
    if (soilConfidence === "taluk") {
      return `${t("addField.soilTypeLabel")} (${t("addField.soilTypeSuggested")})`;
    }
    if (soilConfidence === "district") {
      return `${t("addField.soilTypeLabel")} (${t("addField.soilTypeLikely")})`;
    }
    return t("addField.soilTypeLabel");
  }

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
      areaHectares: toHectares(Number(area), unit, state),
      boundary: points,
      soilType: soilType.trim(),
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
        options={units.map((u) => ({ label: unitLabel(u), value: u }))}
        selectedValue={unit}
        onSelect={(v) => setUnit(v as LandUnit)}
        onClose={() => setUnitPickerOpen(false)}
      />

      <TextField
        label={soilTypeLabel()}
        placeholder={t("addField.soilTypeLabel")}
        value={soilType}
        onChangeText={(v) => {
          setSoilType(v);
          setSoilConfidence(null); // farmer's own entry, not a suggestion anymore
          setSoilLookupFailed(false);
        }}
      />
      {soilLookupFailed && (
        <Text className="text-ink-muted mb-2" style={{ fontSize: 12 }}>
          {t("addField.soilTypeLookupFailed")}
        </Text>
      )}

      <Button
        label={t("addField.confirmSave")}
        disabled={!isValid}
        loading={saving}
        onPress={handleSave}
      />
    </ScreenContainer>
  );
}
