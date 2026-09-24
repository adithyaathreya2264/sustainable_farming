import React, { useState } from "react";
import { Alert, Switch, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { router } from "expo-router";
import { ScreenContainer } from "../../components/ui/ScreenContainer";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { RadioCardGroup } from "../../components/ui/RadioCardGroup";
import {
  BottomSheetPicker,
  PickerField,
} from "../../components/ui/BottomSheetPicker";
import { useSession } from "../../context/SessionContext";
import { useLanguage, LANGUAGES } from "../../context/LanguageContext";
import { updateUnitPreference } from "../../services/profile";
import { updateProfile } from "../../services/users";
import { resetUser } from "../../store/appStore";
import { availableLandUnits, unitLabel } from "../../utils/unitConversion";
import type { LandUnit } from "../../types/models";

export default function ProfileScreen() {
  const { t } = useTranslation();
  const { user, logout } = useSession();
  const { language, setLanguage } = useLanguage();
  const [unitPickerOpen, setUnitPickerOpen] = useState(false);

  return (
    <ScreenContainer>
      <Text className="text-ink font-bold mb-4" style={{ fontSize: 22 }}>
        {t("profile.title")}
      </Text>

      <Card className="mb-4">
        <Text className="text-ink-muted mb-0.5" style={{ fontSize: 13 }}>
          {t("profile.phoneNumber")}
        </Text>
        <Text className="text-ink font-medium" style={{ fontSize: 16 }}>
          {user.phoneNumber}
        </Text>
      </Card>

      <Text className="text-ink font-semibold mb-2" style={{ fontSize: 15 }}>
        {t("profile.language")}
      </Text>
      <View className="mb-4">
        <RadioCardGroup
          options={LANGUAGES.map((l) => ({ value: l.code, label: l.label }))}
          value={language}
          onChange={setLanguage}
        />
      </View>

      <PickerField
        label={t("profile.unitPreference")}
        placeholder={t("profile.unitPreference")}
        displayValue={unitLabel(user.defaultUnit)}
        onPress={() => setUnitPickerOpen(true)}
      />
      <BottomSheetPicker
        visible={unitPickerOpen}
        title={t("profile.unitPreference")}
        options={availableLandUnits(user.state).map((u) => ({
          label: unitLabel(u),
          value: u,
        }))}
        selectedValue={user.defaultUnit}
        onSelect={(v) => updateUnitPreference(v as LandUnit)}
        onClose={() => setUnitPickerOpen(false)}
      />

      <Text className="text-ink font-semibold mb-2" style={{ fontSize: 15 }}>
        {t("photoHistory.sectionTitle")}
      </Text>
      <Card className="mb-4">
        <View className="flex-row items-center justify-between">
          <Text className="text-ink flex-1 pr-3" style={{ fontSize: 14 }}>
            {t("photoHistory.trainingConsent")}
          </Text>
          <Switch
            accessibilityLabel={t("photoHistory.trainingConsent")}
            value={Boolean(user.photoTrainingConsent)}
            onValueChange={(v) => updateProfile({ photoTrainingConsent: v })}
            trackColor={{ true: "#66BB6A", false: "#E0E0E0" }}
            thumbColor={user.photoTrainingConsent ? "#2E7D32" : "#FFFFFF"}
          />
        </View>
        <Text className="text-ink-muted mt-1" style={{ fontSize: 12 }}>
          {t("photoHistory.trainingConsentHint")}
        </Text>
      </Card>
      <View className="mb-4">
        <Button label={t("photoHistory.open")} variant="outline" onPress={() => router.push("/photo-history")} />
      </View>

      <Button
        label={t("profile.logout")}
        variant="danger"
        onPress={() => {
          logout();
          router.replace("/(auth)/login");
        }}
      />

      {__DEV__ && (
        <View className="mt-4">
          <Text className="text-ink-muted mb-2" style={{ fontSize: 12 }}>
            Development only
          </Text>
          <Button
            label="Reset User (Dev Only)"
            variant="outline"
            onPress={() => {
              Alert.alert(
                "Reset user?",
                "Clears all local app data (auth, profile, fields, plantings...) and returns to the login screen. The account and its data on the server are not affected.",
                [
                  { text: t("common.cancel"), style: "cancel" },
                  {
                    text: "Reset",
                    style: "destructive",
                    onPress: () => {
                      resetUser();
                      router.replace("/(auth)/login");
                    },
                  },
                ]
              );
            }}
          />
        </View>
      )}
    </ScreenContainer>
  );
}
