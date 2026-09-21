import React from "react";
import { Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { router } from "expo-router";
import { ScreenContainer } from "../../components/ui/ScreenContainer";
import { Button } from "../../components/ui/Button";
import { RadioCardGroup } from "../../components/ui/RadioCardGroup";
import { StepProgress } from "../../components/StepProgress";
import { useOnboardingDraft } from "../../context/OnboardingDraftContext";
import { LANGUAGES } from "../../context/LanguageContext";
import type { LanguageCode } from "../../types/models";

export default function OnboardingStep1() {
  const { t, i18n } = useTranslation();
  const { draft, update } = useOnboardingDraft();

  function selectLanguage(code: LanguageCode) {
    update({ languagePref: code });
    i18n.changeLanguage(code);
  }

  return (
    <ScreenContainer>
      <StepProgress step={1} total={4} />
      <Text className="text-ink font-bold mb-6" style={{ fontSize: 22 }}>
        {t("onboarding.step1Title")}
      </Text>

      <Text className="text-ink-muted mb-2" style={{ fontSize: 14 }}>
        {t("onboarding.languageLabel")}
      </Text>
      <RadioCardGroup
        options={LANGUAGES.map((l) => ({ value: l.code, label: l.label }))}
        value={draft.languagePref}
        onChange={selectLanguage}
        columns={1}
      />

      <View className="mt-4">
        <Button
          label={t("common.continue")}
          onPress={() => router.push("/(onboarding)/step-2")}
        />
      </View>
    </ScreenContainer>
  );
}
