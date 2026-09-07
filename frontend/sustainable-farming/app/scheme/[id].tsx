import React, { useEffect, useState } from "react";
import { Linking, Text, View } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import { ScreenContainer } from "../../components/ui/ScreenContainer";
import { ModalHeader } from "../../components/ModalHeader";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { SkeletonCard } from "../../components/ui/SkeletonLoader";
import { getAlertById, respondToAlert } from "../../services/alerts";
import type { Alert } from "../../types/models";

export default function SchemeDetailScreen() {
  const { t } = useTranslation();
  const { id } = useLocalSearchParams<{ id: string }>();
  const [scheme, setScheme] = useState<Alert | null>(null);
  const [claiming, setClaiming] = useState(false);

  useEffect(() => {
    getAlertById(id).then((s) => {
      const found = s ?? null;
      setScheme(found);
      // Opening the detail screen IS "viewed" — no separate tap needed.
      // Best-effort: a failed PATCH here shouldn't block reading the scheme.
      if (found && found.status === "matched") {
        respondToAlert("scheme_match", id, "viewed").catch(() => {});
      }
    });
  }, [id]);

  if (!scheme) {
    return (
      <ScreenContainer>
        <ModalHeader title="" />
        <SkeletonCard />
      </ScreenContainer>
    );
  }

  const claimed = scheme.status === "claimed";

  return (
    <ScreenContainer>
      <ModalHeader title={scheme.headline} />

      <View className="flex-row mb-3">
        <View className="bg-info rounded-full px-3 py-1">
          <Text className="text-white" style={{ fontSize: 12 }}>
            {t(`confidence.${scheme.confidenceLabel}`)}
          </Text>
        </View>
      </View>

      {scheme.authority ? (
        <Text className="text-ink-muted mb-4" style={{ fontSize: 13 }}>
          {scheme.authority}
        </Text>
      ) : null}

      <Text className="text-ink font-semibold mb-2" style={{ fontSize: 15 }}>
        {t("schemeDetail.benefits")}
      </Text>
      <Card className="mb-4">
        <Text className="text-ink" style={{ fontSize: 14, lineHeight: 20 }}>
          {scheme.detail}
        </Text>
      </Card>

      {scheme.eligibilitySummary && scheme.eligibilitySummary.length > 0 ? (
        <>
          <Text className="text-ink font-semibold mb-2" style={{ fontSize: 15 }}>
            {t("schemeDetail.eligibility")}
          </Text>
          <Card className="mb-4">
            {scheme.eligibilitySummary.map((line, i) => (
              <View key={i} className="flex-row mb-1.5">
                <Text className="text-primary mr-2">•</Text>
                <Text className="text-ink flex-1" style={{ fontSize: 14 }}>
                  {line}
                </Text>
              </View>
            ))}
          </Card>
        </>
      ) : null}

      {scheme.applicationUrl ? (
        <Button
          label={t("schemeDetail.visitApplicationUrl")}
          variant="outline"
          onPress={() => Linking.openURL(scheme.applicationUrl!)}
        />
      ) : null}

      <View className="mt-3">
        <Button
          label={claimed ? t("schemeDetail.markedApplying") : t("schemeDetail.markApplying")}
          variant={claimed ? "outline" : "primary"}
          disabled={claimed}
          loading={claiming}
          onPress={async () => {
            setClaiming(true);
            try {
              await respondToAlert("scheme_match", id, "claimed");
              setScheme((prev) => (prev ? { ...prev, status: "claimed" } : prev));
            } finally {
              setClaiming(false);
            }
          }}
        />
      </View>
    </ScreenContainer>
  );
}
