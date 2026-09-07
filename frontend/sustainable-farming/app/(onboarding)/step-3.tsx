import React, { useState } from "react";
import { Text } from "react-native";
import { useTranslation } from "react-i18next";
import { router } from "expo-router";
import { ScreenContainer } from "../../components/ui/ScreenContainer";
import { Button } from "../../components/ui/Button";
import { NumericField } from "../../components/ui/TextField";
import {
  BottomSheetPicker,
  PickerField,
} from "../../components/ui/BottomSheetPicker";
import { StepProgress } from "../../components/StepProgress";
import { useOnboardingDraft } from "../../context/OnboardingDraftContext";
import { STANDARDIZED_LAND_UNITS, unitLabel } from "../../utils/unitConversion";
// State (and thus any non-standardized unit's conversion factor — Bigha,
// Katha, Biswa, Kanal, Marla) isn't collected until a later onboarding step,
// so only standardized units are offered here. See docs/unit-conversions.md.

export default function OnboardingStep3() {
  const { t } = useTranslation();
  const { draft, update } = useOnboardingDraft();
  const [pickerOpen, setPickerOpen] = useState(false);

  const isValid = Number(draft.totalArea) > 0;

  return (
    <ScreenContainer>
      <StepProgress step={3} total={4} />
      <Text className="text-ink font-bold mb-6" style={{ fontSize: 22 }}>
        {t("onboarding.step2Title")}
      </Text>

      <PickerField
        label={t("onboarding.unitLabel")}
        placeholder={t("onboarding.unitLabel")}
        displayValue={unitLabel(draft.defaultUnit)}
        onPress={() => setPickerOpen(true)}
      />
      <BottomSheetPicker
        visible={pickerOpen}
        title={t("onboarding.unitLabel")}
        options={STANDARDIZED_LAND_UNITS.map((u) => ({ label: unitLabel(u), value: u }))}
        selectedValue={draft.defaultUnit}
        onSelect={(v) => update({ defaultUnit: v as typeof draft.defaultUnit })}
        onClose={() => setPickerOpen(false)}
      />

      <NumericField
        label={`${t("onboarding.areaLabel")} (${unitLabel(draft.defaultUnit)})`}
        value={draft.totalArea}
        onChangeText={(v) => update({ totalArea: v.replace(/[^0-9.]/g, "") })}
        placeholder="0"
      />

      <Button
        label={t("common.continue")}
        disabled={!isValid}
        onPress={() => router.push("/(onboarding)/step-4")}
      />
    </ScreenContainer>
  );
}
