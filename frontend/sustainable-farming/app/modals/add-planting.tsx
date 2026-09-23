import React, { useEffect, useMemo, useState } from "react";
import { Text } from "react-native";
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
import {
  getCropRecommendation,
  type CropRecommendationResult,
} from "../../services/cropRecommendation";

const today = new Date().toISOString().slice(0, 10);

type CropFit = "top" | "alternative" | "unscored";

/** Best-effort name match: backend display names/keys for seeded crops are
 * exact-cased ("Sugarcane", "sugarcane") against the catalog's own
 * crops.name, per ml/prep/common.py's SEEDED_CROPS table. */
function cropFit(cropName: string, rec: CropRecommendationResult): CropFit | null {
  const lower = cropName.toLowerCase();
  if (rec.unreachableSeededCrops.some((key) => lower.startsWith(key))) return "unscored";
  if (rec.recommended.displayName === cropName) return "top";
  if (rec.alternatives.some((a) => a.displayName === cropName)) return "alternative";
  return null;
}

export default function AddPlantingModal() {
  const { t } = useTranslation();
  const { showToast } = useToast();
  const params = useLocalSearchParams<{ fieldId?: string }>();
  const fields = useAppState((s) => s.fields);
  // Server-owned reference data (backend/src/routes/reference.js), cached by
  // fetchAndCacheCatalog() — see hooks/useRefreshTriggers.ts. Reading it
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
  const [recommendation, setRecommendation] = useState<CropRecommendationResult | null>(null);
  const [recommendationUnavailable, setRecommendationUnavailable] = useState(false);

  const selectedCrop = useMemo(() => crops.find((c) => c.id === cropId), [crops, cropId]);
  const selectedField = fields.find((f) => f.id === fieldId);

  // Best-effort crop-suitability guidance for the chosen field — never
  // blocks planting, see cropFit() below. Refetched whenever the field
  // changes (it depends on that field's soil test + local weather).
  useEffect(() => {
    if (!fieldId) {
      setRecommendation(null);
      return;
    }
    let cancelled = false;
    setRecommendationUnavailable(false);
    getCropRecommendation(fieldId)
      .then((r) => {
        if (!cancelled) setRecommendation(r);
      })
      .catch(() => {
        if (!cancelled) {
          setRecommendation(null);
          setRecommendationUnavailable(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [fieldId]);

  const isValid = Boolean(fieldId && cropId && varietyId && sowingDate);

  async function handleSave() {
    setSaving(true);
    try {
      await addPlanting({ fieldId, cropId, varietyId, sowingDate });
      showToast(t("common.saved"));
      router.back();
    } catch {
      showToast(t("common.saveFailed"));
    } finally {
      setSaving(false);
    }
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
        searchable
        searchPlaceholder={t("common.search")}
      />
      {selectedCrop && recommendation && (
        <RecommendationBadge fit={cropFit(selectedCrop.name, recommendation)} />
      )}
      {selectedCrop && !recommendation && recommendationUnavailable && (
        <Text className="text-ink-muted mb-4" style={{ fontSize: 12 }}>
          {t("addPlanting.recommendationUnavailable")}
        </Text>
      )}
      {recommendation && !recommendation.usedSoilTest && (
        <Text className="text-ink-muted mb-4" style={{ fontSize: 12 }}>
          {t("addPlanting.recommendationEstimated")}
        </Text>
      )}

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
        searchable
        searchPlaceholder={t("common.search")}
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

function RecommendationBadge({ fit }: { fit: CropFit | null }) {
  const { t } = useTranslation();
  if (!fit) return null;
  const copy = {
    top: { text: t("addPlanting.recommendedFit"), className: "text-primary-dark" },
    alternative: { text: t("addPlanting.alternativeFit"), className: "text-ink-muted" },
    unscored: { text: t("addPlanting.unscoredFit"), className: "text-ink-muted" },
  }[fit];
  return (
    <Text className={`${copy.className} mb-2 font-semibold`} style={{ fontSize: 13 }}>
      {copy.text}
    </Text>
  );
}
