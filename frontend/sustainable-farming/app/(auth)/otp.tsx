import React, { useEffect, useRef, useState } from "react";
import { Text, TextInput, View } from "react-native";
import { useTranslation } from "react-i18next";
import { router } from "expo-router";
import { ScreenContainer } from "../../components/ui/ScreenContainer";
import { Button } from "../../components/ui/Button";
import { useAppState } from "../../hooks/useAppState";
import { MOCK_OTP, requestOtp, verifyOtp } from "../../services/auth";

const OTP_LENGTH = 6;
const RESEND_SECONDS = 59;

export default function OtpScreen() {
  const { t } = useTranslation();
  const phone = useAppState((s) => s.user.phoneNumber);
  const [digits, setDigits] = useState<string[]>(Array(OTP_LENGTH).fill(""));
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [seconds, setSeconds] = useState(RESEND_SECONDS);
  const inputs = useRef<Array<TextInput | null>>([]);

  useEffect(() => {
    if (seconds <= 0) return;
    const id = setTimeout(() => setSeconds((s) => s - 1), 1000);
    return () => clearTimeout(id);
  }, [seconds]);

  function handleChange(text: string, index: number) {
    const clean = text.replace(/[^0-9]/g, "");
    const next = [...digits];
    next[index] = clean.slice(-1);
    setDigits(next);
    setError(null);
    if (clean && index < OTP_LENGTH - 1) {
      inputs.current[index + 1]?.focus();
    }
  }

  function handleKeyPress(e: { nativeEvent: { key: string } }, index: number) {
    if (e.nativeEvent.key === "Backspace" && !digits[index] && index > 0) {
      inputs.current[index - 1]?.focus();
    }
  }

  async function handleVerify() {
    setLoading(true);
    const result = await verifyOtp(digits.join(""));
    setLoading(false);
    if (!result.success) {
      setError(t("auth.invalidOtp"));
      return;
    }
    router.replace(result.isNewUser ? "/(onboarding)/step-1" : "/(tabs)/home");
  }

  async function handleResend() {
    setSeconds(RESEND_SECONDS);
    setDigits(Array(OTP_LENGTH).fill(""));
    await requestOtp(phone);
  }

  const isComplete = digits.every((d) => d.length === 1);

  return (
    <ScreenContainer scroll={false}>
      <View className="flex-1 justify-center">
        <Text className="text-ink font-bold" style={{ fontSize: 24 }}>
          {t("auth.otpTitle")}
        </Text>
        <Text className="text-ink-muted mt-1" style={{ fontSize: 15 }}>
          {t("auth.otpSubtitle", { phone })}
        </Text>
        <Text className="text-info mt-1 mb-8" style={{ fontSize: 13 }}>
          {t("auth.hintOtp", { otp: MOCK_OTP })}
        </Text>

        <View className="flex-row justify-between mb-2">
          {digits.map((digit, index) => (
            <TextInput
              key={index}
              ref={(el) => {
                inputs.current[index] = el;
              }}
              accessibilityLabel={`OTP digit ${index + 1}`}
              value={digit}
              onChangeText={(text) => handleChange(text, index)}
              onKeyPress={(e) => handleKeyPress(e, index)}
              keyboardType="number-pad"
              maxLength={1}
              className={`rounded-xl border-2 text-center text-ink font-semibold ${
                error ? "border-danger" : "border-border"
              }`}
              style={{ width: 48, height: 56, fontSize: 22 }}
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
          label={t("auth.verify")}
          onPress={handleVerify}
          disabled={!isComplete}
          loading={loading}
        />

        <View className="items-center mt-5">
          {seconds > 0 ? (
            <Text className="text-ink-muted" style={{ fontSize: 14 }}>
              {t("auth.resendIn", { seconds })}
            </Text>
          ) : (
            <Text
              accessibilityRole="button"
              onPress={handleResend}
              className="text-primary font-semibold"
              style={{ fontSize: 14 }}
            >
              {t("auth.resend")}
            </Text>
          )}
        </View>
      </View>
    </ScreenContainer>
  );
}
