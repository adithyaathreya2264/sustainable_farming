import React, { useRef, useState } from "react";
import { Text, TextInput, View } from "react-native";
import { useTranslation } from "react-i18next";
import { router } from "expo-router";
import { ScreenContainer } from "../../components/ui/ScreenContainer";
import { Button } from "../../components/ui/Button";
import { StepProgress } from "../../components/StepProgress";
import { useOnboardingDraft } from "../../context/OnboardingDraftContext";
import { ApiError } from "../../lib/apiClient";
import { claimUniqueId } from "../../services/users";

const PIN_LENGTH = 4;

export default function OnboardingStep1() {
  const { t } = useTranslation();
  const { update } = useOnboardingDraft();
  const [digits, setDigits] = useState<string[]>(Array(PIN_LENGTH).fill(""));
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const inputs = useRef<Array<TextInput | null>>([]);

  function handleChange(text: string, index: number) {
    const clean = text.replace(/[^0-9]/g, "");
    const next = [...digits];
    next[index] = clean.slice(-1);
    setDigits(next);
    setError(null);
    if (clean && index < PIN_LENGTH - 1) {
      inputs.current[index + 1]?.focus();
    }
  }

  function handleKeyPress(e: { nativeEvent: { key: string } }, index: number) {
    if (e.nativeEvent.key === "Backspace" && !digits[index] && index > 0) {
      inputs.current[index - 1]?.focus();
    }
  }

  async function handleContinue() {
    const uniqueId = digits.join("");
    setSubmitting(true);
    try {
      await claimUniqueId(uniqueId);
      update({ uniqueId });
      router.push("/(onboarding)/step-2");
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError(t("onboarding.uniqueIdTaken"));
      } else {
        setError(t("common.saveFailed"));
      }
    } finally {
      setSubmitting(false);
    }
  }

  const isComplete = digits.every((d) => d.length === 1);

  return (
    <ScreenContainer>
      <StepProgress step={1} total={5} />
      <Text className="text-ink font-bold mb-2" style={{ fontSize: 22 }}>
        {t("onboarding.uniqueIdTitle")}
      </Text>
      <Text className="text-ink-muted mb-6" style={{ fontSize: 14 }}>
        {t("onboarding.uniqueIdSubtitle")}
      </Text>

      <View className="flex-row justify-between mb-2">
        {digits.map((digit, index) => (
          <TextInput
            key={index}
            ref={(el) => {
              inputs.current[index] = el;
            }}
            accessibilityLabel={`Unique ID digit ${index + 1}`}
            value={digit}
            onChangeText={(text) => handleChange(text, index)}
            onKeyPress={(e) => handleKeyPress(e, index)}
            keyboardType="number-pad"
            maxLength={1}
            className={`rounded-xl border-2 text-center text-ink font-semibold ${
              error ? "border-danger" : "border-border"
            }`}
            style={{ width: 56, height: 64, fontSize: 24 }}
          />
        ))}
      </View>
      {error ? (
        <Text className="text-danger mb-4" style={{ fontSize: 13 }}>
          {error}
        </Text>
      ) : (
        <View className="mb-4" />
      )}

      <Button
        label={t("common.continue")}
        onPress={handleContinue}
        disabled={!isComplete}
        loading={submitting}
      />
    </ScreenContainer>
  );
}
