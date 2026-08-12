import React, { useEffect, useState } from "react";
import { Linking, Text, View } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import { ScreenContainer } from "../../components/ui/ScreenContainer";
import { ModalHeader } from "../../components/ModalHeader";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { SkeletonCard } from "../../components/ui/SkeletonLoader";
import { useToast } from "../../context/ToastContext";
import { getSchemeById } from "../../services/schemes";
import type { Scheme } from "../../types/models";

export default function SchemeDetailScreen() {
  const { t } = useTranslation();
  const { showToast } = useToast();
  const { id } = useLocalSearchParams<{ id: string }>();
  const [scheme, setScheme] = useState<Scheme | null>(null);
  const [applying, setApplying] = useState(false);

  useEffect(() => {
    getSchemeById(id).then((s) => setScheme(s ?? null));
  }, [id]);

  if (!scheme) {
    return (
      <ScreenContainer>
        <ModalHeader title="" />
        <SkeletonCard />
      </ScreenContainer>
    );
  }

  return (
    <ScreenContainer>
      <ModalHeader title={scheme.name} />

      <Card className="mb-4 bg-primary/5 border-primary/30">
        <Text className="text-ink" style={{ fontSize: 15, lineHeight: 21 }}>
          {scheme.summary}
        </Text>
      </Card>

      <Text className="text-ink font-semibold mb-2" style={{ fontSize: 15 }}>
        {t("schemeDetail.eligibility")}
      </Text>
      <Card className="mb-4">
        {scheme.eligibilityCriteria.map((c, i) => (
          <View key={i} className="flex-row mb-1.5">
            <Text className="text-primary mr-2">•</Text>
            <Text className="text-ink flex-1" style={{ fontSize: 14 }}>
              {c}
            </Text>
          </View>
        ))}
      </Card>

      <Text className="text-ink font-semibold mb-2" style={{ fontSize: 15 }}>
        {t("schemeDetail.benefits")}
      </Text>
      <Card className="mb-4">
        <Text className="text-ink" style={{ fontSize: 14, lineHeight: 20 }}>
          {scheme.benefits}
        </Text>
      </Card>

      <Text className="text-ink font-semibold mb-2" style={{ fontSize: 15 }}>
        {t("schemeDetail.howToApply")}
      </Text>
      <Card className="mb-4">
        <Text className="text-ink mb-3" style={{ fontSize: 14, lineHeight: 20 }}>
          {scheme.howToApply}
        </Text>
        <Text className="text-ink-muted mb-0.5" style={{ fontSize: 13 }}>
          {t("schemeDetail.contact")}
        </Text>
        <Text className="text-ink font-medium mb-0.5" style={{ fontSize: 14 }}>
          {scheme.contactOffice}
        </Text>
        <Text
          accessibilityRole="link"
          onPress={() => Linking.openURL(`tel:${scheme.contactPhone}`)}
          className="text-info font-medium"
          style={{ fontSize: 14 }}
        >
          {scheme.contactPhone}
        </Text>
      </Card>

      <Button
        label={
          applying ? t("schemeDetail.markedApplying") : t("schemeDetail.markApplying")
        }
        variant={applying ? "outline" : "primary"}
        disabled={applying}
        onPress={() => {
          setApplying(true);
          showToast(t("schemeDetail.markedApplying"));
        }}
      />
    </ScreenContainer>
  );
}
