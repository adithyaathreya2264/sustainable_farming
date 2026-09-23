import React, { useEffect, useState } from "react";
import { Text } from "react-native";
import { useTranslation } from "react-i18next";
import { router } from "expo-router";
import { ScreenContainer } from "../../components/ui/ScreenContainer";
import { Button } from "../../components/ui/Button";
import { RadioCardGroup } from "../../components/ui/RadioCardGroup";
import {
  BottomSheetPicker,
  PickerField,
} from "../../components/ui/BottomSheetPicker";
import { StepProgress } from "../../components/StepProgress";
import { useOnboardingDraft } from "../../context/OnboardingDraftContext";
import { getDistricts, getStates } from "../../services/locations";
import { completeOnboarding } from "../../services/onboarding";
import type { IrrigationType } from "../../types/models";

const IRRIGATION_ICONS: Record<IrrigationType, string> = {
  rainfed: "🌧️",
  borewell: "🕳️",
  canal: "🚰",
  drip_sprinkler: "💧",
};

export default function OnboardingStep5() {
  const { t } = useTranslation();
  const { draft, update } = useOnboardingDraft();
  const [states, setStates] = useState<string[]>([]);
  const [districts, setDistricts] = useState<string[]>([]);
  const [statePickerOpen, setStatePickerOpen] = useState(false);
  const [districtPickerOpen, setDistrictPickerOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    getStates().then(setStates);
  }, []);

  useEffect(() => {
    if (!draft.state) {
      setDistricts([]);
      return;
    }
    getDistricts(draft.state).then(setDistricts);
  }, [draft.state]);

  const irrigationOptions = (
    ["rainfed", "borewell", "canal", "drip_sprinkler"] as IrrigationType[]
  ).map((type) => ({
    value: type,
    label: t(`onboarding.irrigation.${type}`),
    icon: IRRIGATION_ICONS[type],
  }));

  const isValid = Boolean(draft.state && draft.district);

  async function handleComplete() {
    setSubmitting(true);
    await completeOnboarding({
      languagePref: draft.languagePref,
      name: draft.name,
      defaultUnit: draft.defaultUnit,
      totalArea: Number(draft.totalArea),
      irrigationType: draft.irrigationType,
      state: draft.state,
      district: draft.district,
    });
    setSubmitting(false);
    router.replace("/(tabs)/home");
  }

  return (
    <ScreenContainer>
      <StepProgress step={5} total={5} />
      <Text className="text-ink font-bold mb-6" style={{ fontSize: 22 }}>
        {t("onboarding.step3Title")}
      </Text>

      <Text className="text-ink-muted mb-2" style={{ fontSize: 14 }}>
        {t("onboarding.irrigationLabel")}
      </Text>
      <RadioCardGroup
        options={irrigationOptions}
        value={draft.irrigationType}
        onChange={(v) => update({ irrigationType: v })}
      />

      <PickerField
        label={t("onboarding.stateLabel")}
        placeholder={t("onboarding.selectState")}
        displayValue={draft.state || undefined}
        onPress={() => setStatePickerOpen(true)}
      />
      <BottomSheetPicker
        visible={statePickerOpen}
        title={t("onboarding.selectState")}
        options={states.map((s) => ({ label: s, value: s }))}
        selectedValue={draft.state}
        onSelect={(v) => update({ state: v, district: "" })}
        onClose={() => setStatePickerOpen(false)}
      />

      <PickerField
        label={t("onboarding.districtLabel")}
        placeholder={t("onboarding.selectDistrict")}
        displayValue={draft.district || undefined}
        disabled={!draft.state}
        onPress={() => setDistrictPickerOpen(true)}
      />
      <BottomSheetPicker
        visible={districtPickerOpen}
        title={t("onboarding.selectDistrict")}
        options={districts.map((d) => ({ label: d, value: d }))}
        selectedValue={draft.district}
        onSelect={(v) => update({ district: v })}
        onClose={() => setDistrictPickerOpen(false)}
      />

      <Button
        label={t("onboarding.completeProfile")}
        disabled={!isValid}
        loading={submitting}
        onPress={handleComplete}
      />
    </ScreenContainer>
  );
}
