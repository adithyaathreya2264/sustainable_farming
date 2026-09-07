import React, { useState } from "react";
import { Text, View } from "react-native";
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
import { SyncStatusIcon } from "../../components/SyncStatusIcon";
import { useSession } from "../../context/SessionContext";
import { useLanguage, LANGUAGES } from "../../context/LanguageContext";
import { useToast } from "../../context/ToastContext";
import { loadDemoData, resetDemo } from "../../store/appStore";
import { updateUnitPreference } from "../../services/profile";
import { availableLandUnits, unitLabel } from "../../utils/unitConversion";
import type { LandUnit } from "../../types/models";

export default function ProfileScreen() {
  const { t } = useTranslation();
  const { user, logout } = useSession();
  const { language, setLanguage } = useLanguage();
  const { showToast } = useToast();
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
        <Text className="text-ink font-medium mb-3" style={{ fontSize: 16 }}>
          {user.phoneNumber}
        </Text>
        <Text className="text-ink-muted mb-1" style={{ fontSize: 13 }}>
          {t("profile.syncStatus")}
        </Text>
        <SyncStatusIcon />
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

      <Text className="text-ink font-semibold mt-4 mb-2" style={{ fontSize: 15 }}>
        {t("profile.demoDataTitle")}
      </Text>
      <Card className="mb-4">
        <View className="mb-3">
          <Button
            label={t("profile.loadSampleData")}
            variant="outline"
            onPress={() => {
              loadDemoData();
              showToast(t("common.syncedToCloud"));
            }}
          />
        </View>
        <Button
          label={t("profile.resetDemo")}
          variant="outline"
          onPress={() => {
            resetDemo();
            router.replace("/(onboarding)/step-1");
          }}
        />
      </Card>

      <Button
        label={t("profile.logout")}
        variant="danger"
        onPress={() => {
          logout();
          router.replace("/(auth)/login");
        }}
      />
    </ScreenContainer>
  );
}
