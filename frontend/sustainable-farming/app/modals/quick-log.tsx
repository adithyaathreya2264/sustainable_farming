import React, { useEffect, useMemo, useState } from "react";
import { router, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import { ScreenContainer } from "../../components/ui/ScreenContainer";
import { ModalHeader } from "../../components/ModalHeader";
import { Button } from "../../components/ui/Button";
import { NumericField } from "../../components/ui/TextField";
import { RadioCardGroup } from "../../components/ui/RadioCardGroup";
import { DateField } from "../../components/ui/DateField";
import {
  BottomSheetPicker,
  PickerField,
} from "../../components/ui/BottomSheetPicker";
import { EmptyState } from "../../components/ui/EmptyState";
import { useToast } from "../../context/ToastContext";
import { useAppState } from "../../hooks/useAppState";
import { addIntervention } from "../../services/interventions";
import { getAgriInputsForCrop } from "../../services/catalog";
import type { AgriCatalogItem, InterventionType } from "../../types/models";

const today = new Date().toISOString().slice(0, 10);
const ACTIVITY_ICONS: Record<InterventionType, string> = {
  chemical: "🧪",
  irrigation: "💧",
  labor: "👷",
  harvest: "🌾",
};

// agri_catalog (backend/models/agri_catalog.py) only ever holds chemical
// inputs — irrigation/labor/harvest have no catalog row at all
// (Intervention.product_id is nullable specifically for those). These are
// local, not-a-product units, not fake catalog entries pretending to have
// IDs the backend has never heard of.
const NON_CATALOG_UNITS: Record<Exclude<InterventionType, "chemical">, string> = {
  irrigation: "hour",
  labor: "person-day",
  harvest: "quintal",
};

export default function QuickLogModal() {
  const { t } = useTranslation();
  const { showToast } = useToast();
  const params = useLocalSearchParams<{
    plantingId?: string;
    activityType?: InterventionType;
    productId?: string;
  }>();
  const plantings = useAppState((s) => s.plantings);
  const fields = useAppState((s) => s.fields);
  const crops = useAppState((s) => s.crops);

  const [plantingId, setPlantingId] = useState(params.plantingId ?? "");
  const [activityType, setActivityType] = useState<InterventionType>(
    params.activityType ?? "chemical"
  );
  const [productId, setProductId] = useState(params.productId ?? "");
  const [quantity, setQuantity] = useState("");
  const [cost, setCost] = useState("");
  const [date, setDate] = useState(today);
  const [products, setProducts] = useState<AgriCatalogItem[]>([]);
  const [plantingPickerOpen, setPlantingPickerOpen] = useState(false);
  const [productPickerOpen, setProductPickerOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  const isChemical = activityType === "chemical";
  const selectedPlanting = plantings.find((p) => p.id === plantingId);
  const selectedPlantingCropName = selectedPlanting
    ? crops.find((c) => c.id === selectedPlanting.cropId)?.name
    : undefined;

  useEffect(() => {
    if (!isChemical) {
      setProducts([]);
      return;
    }
    getAgriInputsForCrop(selectedPlantingCropName).then(setProducts);
    setProductId((prev) => (params.activityType ? prev : ""));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activityType, selectedPlantingCropName]);

  const plantingOptions = useMemo(
    () =>
      plantings.map((p) => {
        const field = fields.find((f) => f.id === p.fieldId);
        return { label: field ? field.name : p.id, value: p.id };
      }),
    [plantings, fields]
  );
  const selectedProduct = products.find((p) => p.id === productId);
  const selectedPlantingLabel = plantingOptions.find((p) => p.value === plantingId)?.label;
  const quantityUnit = isChemical
    ? selectedProduct?.unitOfMeasure
    : NON_CATALOG_UNITS[activityType as Exclude<InterventionType, "chemical">];

  const isValid = Boolean(
    plantingId && quantity && cost && (!isChemical || productId)
  );

  async function handleSave() {
    setSaving(true);
    await addIntervention({
      plantingId,
      type: activityType,
      date,
      productId: isChemical ? productId : undefined,
      quantityMetric: Number(quantity),
      quantityUnit,
      costInInr: Number(cost),
    });
    setSaving(false);
    showToast(t("common.savedOffline"));
    router.back();
  }

  if (plantings.length === 0) {
    return (
      <ScreenContainer>
        <ModalHeader title={t("quickLog.title")} />
        <EmptyState
          icon="🌱"
          title={t("fields.noFieldsTitle")}
          subtitle={t("fields.noFieldsSubtitle")}
        />
      </ScreenContainer>
    );
  }

  return (
    <ScreenContainer>
      <ModalHeader title={t("quickLog.title")} />

      <PickerField
        label={t("quickLog.fieldLabel")}
        placeholder={t("quickLog.fieldLabel")}
        displayValue={selectedPlantingLabel}
        onPress={() => setPlantingPickerOpen(true)}
      />
      <BottomSheetPicker
        visible={plantingPickerOpen}
        title={t("quickLog.fieldLabel")}
        options={plantingOptions}
        selectedValue={plantingId}
        onSelect={setPlantingId}
        onClose={() => setPlantingPickerOpen(false)}
      />

      <RadioCardGroup
        options={(["chemical", "irrigation", "labor", "harvest"] as InterventionType[]).map(
          (type) => ({
            value: type,
            label: t(`quickLog.activityTypes.${type}`),
            icon: ACTIVITY_ICONS[type],
          })
        )}
        value={activityType}
        onChange={(v) => {
          setActivityType(v);
          setProductId("");
        }}
      />

      {isChemical && (
        <>
          <PickerField
            label={t("quickLog.productLabel")}
            placeholder={t("quickLog.productLabel")}
            displayValue={selectedProduct?.name}
            onPress={() => setProductPickerOpen(true)}
          />
          <BottomSheetPicker
            visible={productPickerOpen}
            title={t("quickLog.productLabel")}
            options={products.map((p) => ({ label: p.name, value: p.id }))}
            selectedValue={productId}
            onSelect={setProductId}
            onClose={() => setProductPickerOpen(false)}
          />
          {products.length === 0 && (
            <EmptyState
              icon="📡"
              title={t("quickLog.catalogUnavailableTitle")}
              subtitle={t("quickLog.catalogUnavailableSubtitle")}
            />
          )}
        </>
      )}

      <NumericField
        label={`${t("quickLog.quantityLabel")}${quantityUnit ? ` (${quantityUnit})` : ""}`}
        placeholder="0"
        value={quantity}
        onChangeText={(v) => setQuantity(v.replace(/[^0-9.]/g, ""))}
      />
      <NumericField
        label={t("quickLog.costLabel")}
        placeholder="0"
        value={cost}
        onChangeText={(v) => setCost(v.replace(/[^0-9.]/g, ""))}
      />
      <DateField
        label={t("quickLog.dateLabel")}
        value={date}
        onChange={setDate}
        maximumDate={new Date()}
      />

      <Button
        label={t("quickLog.saveActivity")}
        disabled={!isValid}
        loading={saving}
        onPress={handleSave}
      />
    </ScreenContainer>
  );
}
