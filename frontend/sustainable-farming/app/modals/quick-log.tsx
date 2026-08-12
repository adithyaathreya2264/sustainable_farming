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
import { getAgriProductsByType } from "../../services/catalog";
import type { AgriCatalogItem, InterventionType } from "../../types/models";

const today = new Date().toISOString().slice(0, 10);
const ACTIVITY_ICONS: Record<InterventionType, string> = {
  chemical: "🧪",
  irrigation: "💧",
  labor: "👷",
  harvest: "🌾",
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

  useEffect(() => {
    getAgriProductsByType(activityType).then(setProducts);
    setProductId((prev) => (params.activityType ? prev : ""));
  }, [activityType]);

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

  const isValid = Boolean(plantingId && productId && quantity && cost);

  async function handleSave() {
    setSaving(true);
    await addIntervention({
      plantingId,
      type: activityType,
      date,
      productId,
      quantityMetric: Number(quantity),
      quantityUnit: selectedProduct?.defaultUnit,
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

      <NumericField
        label={`${t("quickLog.quantityLabel")}${
          selectedProduct ? ` (${selectedProduct.defaultUnit})` : ""
        }`}
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
