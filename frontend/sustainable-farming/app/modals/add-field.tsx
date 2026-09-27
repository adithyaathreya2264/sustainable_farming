import React, { useEffect, useState } from "react";
import { Text, View } from "react-native";
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
import {
  hasAnySoilValue,
  SoilTestFields,
  toSoilTestInput,
  type SoilTestValues,
} from "../../components/SoilTestFields";
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
import { SOIL_TYPE_KEYS, soilTypeDisplay, type SoilTypeKey } from "../../utils/soilTypes";
import type { PhotoSource } from "../../lib/photo";
import { pickPhoto } from "../../lib/photo";
import { identifySoilFromPhoto, mlErrorMessage, type SoilTypePhotoResult } from "../../services/ml";
import { ConfidencePill } from "../../components/ui/ConfidencePill";
import { CaveatText } from "../../components/ui/CaveatText";
import { PhotoSourceButtons } from "../../components/ml/PhotoSourceButtons";
import type { Coordinates, LandUnit } from "../../types/models";

export default function AddFieldModal() {
  const { t } = useTranslation();
  const { showToast } = useToast();
  const defaultUnit = useAppState((s) => s.user.defaultUnit);
  const state = useAppState((s) => s.user.state);
  const district = useAppState((s) => s.user.district);
  const existingFields = useAppState((s) => s.fields);
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
  const [soilTypePickerOpen, setSoilTypePickerOpen] = useState(false);
  const [soilTypeMode, setSoilTypeMode] = useState<SoilTypeKey | null>(null);
  const [soilValues, setSoilValues] = useState<SoilTestValues>({});
  const [soilPhoto, setSoilPhoto] = useState<SoilTypePhotoResult | null>(null);
  const [soilPhotoBusy, setSoilPhotoBusy] = useState(false);
  const [soilPhotoError, setSoilPhotoError] = useState<string | null>(null);

  // Model 7b (soil type from photo). Prefills the picker; the farmer still
  // confirms by saving, and can override it like any suggestion.
  async function identifySoil(source: PhotoSource) {
    const photo = await pickPhoto(source);
    if (!photo) return;
    setSoilPhotoBusy(true);
    setSoilPhotoError(null);
    try {
      const result = await identifySoilFromPhoto(photo.uri);
      setSoilPhoto(result);
      setSoilConfidence(null);
      setSoilLookupFailed(false);
      if (result.appSoilKey) {
        setSoilType(result.appSoilKey);
        setSoilTypeMode(result.appSoilKey as SoilTypeKey);
      }
    } catch (err) {
      setSoilPhoto(null);
      setSoilPhotoError(mlErrorMessage(err, t));
    } finally {
      setSoilPhotoBusy(false);
    }
  }

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

  const isDuplicateName = existingFields.some(
    (f) => f.name.trim().toLowerCase() === name.trim().toLowerCase()
  );

  const isValid = Boolean(
    closed && points.length >= 3 && name.trim() && !isDuplicateName && Number(area) > 0
  );

  function handleReset() {
    setPoints([]);
    setClosed(false);
  }

  async function handleSave() {
    if (!closed || points.length < 3) return;
    setSaving(true);
    try {
      await addField({
        name: name.trim(),
        areaHectares: toHectares(Number(area), unit, state),
        boundary: points,
        soilType: soilType.trim(),
        soilTest: hasAnySoilValue(soilValues) ? toSoilTestInput(soilValues) : undefined,
      });
      showToast(t("common.saved"));
      router.back();
    } catch {
      showToast(t("common.saveFailed"));
    } finally {
      setSaving(false);
    }
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
      {isDuplicateName && (
        <Text className="text-danger mb-2" style={{ fontSize: 12 }}>
          {t("addField.fieldNameDuplicate")}
        </Text>
      )}

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

      <PickerField
        label={soilTypeLabel()}
        placeholder={t("addField.soilTypeLabel")}
        displayValue={soilType ? soilTypeDisplay(soilType, t) : undefined}
        onPress={() => setSoilTypePickerOpen(true)}
      />
      <BottomSheetPicker
        visible={soilTypePickerOpen}
        title={t("addField.soilTypeLabel")}
        options={SOIL_TYPE_KEYS.map((key) => ({
          label: t(`addField.soilTypes.${key}`),
          value: key,
        }))}
        selectedValue={soilTypeMode ?? undefined}
        onSelect={(key) => {
          const soilKey = key as SoilTypeKey;
          setSoilTypeMode(soilKey);
          setSoilConfidence(null); // farmer's own choice, not a suggestion anymore
          setSoilLookupFailed(false);
          setSoilPhoto(null);
          // Store the key, not the translated label: the backend maps keys to
          // the crop-from-soil-type model's vocabulary in any app language.
          if (soilKey !== "other") setSoilType(soilKey);
        }}
        onClose={() => setSoilTypePickerOpen(false)}
        searchable
        searchPlaceholder={t("common.search")}
      />
      <PhotoSourceButtons
        label={t("ml.identifySoilFromPhoto")}
        busy={soilPhotoBusy}
        onPick={identifySoil}
      />
      {soilPhoto && (
        <View className="flex-row items-center mb-2" style={{ gap: 8 }}>
          <Text className="text-ink" style={{ fontSize: 13 }}>
            {soilPhoto.appSoilKey
              ? t("ml.soilPhotoSuggests", { soil: soilTypeDisplay(soilPhoto.appSoilKey, t) })
              : t("ml.soilPhotoNotInList", { soil: soilPhoto.predictedSoilType })}
          </Text>
          <ConfidencePill label={soilPhoto.confidenceLabel} />
        </View>
      )}
      {soilPhoto && <CaveatText>{t("ml.modelNotice")}</CaveatText>}
      {soilPhotoError && <CaveatText>{soilPhotoError}</CaveatText>}
      {soilLookupFailed && (
        <Text className="text-ink-muted mb-2" style={{ fontSize: 12 }}>
          {t("addField.soilTypeLookupFailed")}
        </Text>
      )}
      {soilTypeMode === "other" && (
        <TextField
          label={t("addField.soilTypeOtherLabel")}
          placeholder={t("addField.soilTypeLabel")}
          value={soilType}
          onChangeText={setSoilType}
        />
      )}

      <Text className="text-ink font-semibold mt-2 mb-1" style={{ fontSize: 15 }}>
        {t("addField.soilTestSectionTitle")}
      </Text>
      <Text className="text-ink-muted mb-3" style={{ fontSize: 13 }}>
        {t("addField.soilTestHint")}
      </Text>
      <SoilTestFields values={soilValues} onChange={setSoilValues} />

      <Button
        label={t("addField.confirmSave")}
        disabled={!isValid}
        loading={saving}
        onPress={handleSave}
      />
    </ScreenContainer>
  );
}
