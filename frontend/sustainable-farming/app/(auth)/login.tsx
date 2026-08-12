import React, { useState } from "react";
import { Text, TextInput, View } from "react-native";
import { useTranslation } from "react-i18next";
import { router } from "expo-router";
import { ScreenContainer } from "../../components/ui/ScreenContainer";
import { Button } from "../../components/ui/Button";
import { requestOtp } from "../../services/auth";

export default function LoginScreen() {
  const { t } = useTranslation();
  const [phone, setPhone] = useState("");
  const [loading, setLoading] = useState(false);

  const isValid = phone.length === 10;

  async function handleGetOtp() {
    setLoading(true);
    await requestOtp(`+91${phone}`);
    setLoading(false);
    router.push("/(auth)/otp");
  }

  return (
    <ScreenContainer scroll={false}>
      <View className="flex-1 justify-center">
        <Text style={{ fontSize: 40 }}>🌾</Text>
        <Text className="text-ink font-bold mt-4" style={{ fontSize: 24 }}>
          {t("auth.loginTitle")}
        </Text>
        <Text className="text-ink-muted mt-1 mb-8" style={{ fontSize: 15 }}>
          {t("auth.loginSubtitle")}
        </Text>

        <Text className="text-ink-muted mb-1.5" style={{ fontSize: 14 }}>
          {t("auth.phoneLabel")}
        </Text>
        <View className="flex-row items-center rounded-xl border border-border bg-surface mb-6" style={{ minHeight: 48 }}>
          <Text className="px-4 text-ink" style={{ fontSize: 16 }}>
            +91
          </Text>
          <View className="w-px bg-border" style={{ height: 24 }} />
          <TextInput
            accessibilityLabel={t("auth.phoneLabel")}
            value={phone}
            onChangeText={(v) => setPhone(v.replace(/[^0-9]/g, "").slice(0, 10))}
            keyboardType="number-pad"
            placeholder="98765 43210"
            placeholderTextColor="#9AA39A"
            className="flex-1 px-4 text-ink"
            style={{ fontSize: 16 }}
            maxLength={10}
          />
        </View>

        <Button
          label={t("auth.getOtp")}
          onPress={handleGetOtp}
          disabled={!isValid}
          loading={loading}
        />
      </View>
    </ScreenContainer>
  );
}
