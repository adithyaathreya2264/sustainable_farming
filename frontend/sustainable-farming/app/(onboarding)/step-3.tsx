import React from "react";
import { Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { router } from "expo-router";
import { ScreenContainer } from "../../components/ui/ScreenContainer";
import { Button } from "../../components/ui/Button";
import { TextField } from "../../components/ui/TextField";
import { StepProgress } from "../../components/StepProgress";
import { useOnboardingDraft } from "../../context/OnboardingDraftContext";

export default function OnboardingStep2() {
  const { t } = useTranslation();
  const { draft, update } = useOnboardingDraft();

  const isValid = draft.name.trim().length > 0;

  return (
    <ScreenContainer>
      <StepProgress step={2} total={4} />
      <Text className="text-ink font-bold mb-6" style={{ fontSize: 22 }}>
        {t("onboarding.step2NameTitle")}
      </Text>

      <TextField
        label={t("onboarding.nameLabel")}
        placeholder={t("onboarding.namePlaceholder")}
        value={draft.name}
        onChangeText={(v) => update({ name: v })}
      />

      <View className="mt-4">
        <Button
          label={t("common.continue")}
          disabled={!isValid}
          onPress={() => router.push("/(onboarding)/step-3")}
        />
      </View>
    </ScreenContainer>
  );
}
