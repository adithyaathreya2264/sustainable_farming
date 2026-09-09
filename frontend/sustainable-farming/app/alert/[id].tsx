import React, { useEffect, useState } from "react";
import { Text, View } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import { ScreenContainer } from "../../components/ui/ScreenContainer";
import { ModalHeader } from "../../components/ModalHeader";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { SkeletonCard } from "../../components/ui/SkeletonLoader";
import { getAlertById, getNearbyVendors, respondToAlert } from "../../services/alerts";
import { formatDate } from "../../utils/format";
import type { Alert, Vendor } from "../../types/models";

export default function AlertDetailScreen() {
  const { t } = useTranslation();
  const { id } = useLocalSearchParams<{ id: string }>();
  const [alert, setAlert] = useState<Alert | null>(null);
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [responding, setResponding] = useState(false);

  useEffect(() => {
    getAlertById(id).then((a) => {
      setAlert(a ?? null);
      // Opening the detail screen IS the acknowledgment — no separate tap
      // needed for that specific transition. Best-effort: a failed PATCH
      // here shouldn't block reading the alert.
      if (a && a.status === "pending") {
        respondToAlert("recommendation", id, "acknowledged").catch(() => {});
      }
    });
    getNearbyVendors().then(setVendors);
  }, [id]);

  async function respond(status: "followed" | "ignored") {
    setResponding(true);
    try {
      await respondToAlert("recommendation", id, status);
      setAlert((prev) => (prev ? { ...prev, status } : prev));
    } finally {
      setResponding(false);
    }
  }

  if (!alert) {
    return (
      <ScreenContainer>
        <ModalHeader title={t("alertDetail.title")} />
        <SkeletonCard />
      </ScreenContainer>
    );
  }

  const responded = alert.status === "followed" || alert.status === "ignored";

  return (
    <ScreenContainer>
      <ModalHeader title={t("alertDetail.title")} />

      <Card className="mb-4 border-2 border-danger/50 bg-danger/5">
        <View className="flex-row items-center justify-between mb-2">
          <Text style={{ fontSize: 22 }}>⚠️</Text>
          <View className="bg-danger rounded-full px-3 py-1">
            <Text className="text-white" style={{ fontSize: 12 }}>
              {t(`confidence.${alert.confidenceLabel}`)}
            </Text>
          </View>
        </View>
        <Text className="text-ink-muted mb-2" style={{ fontSize: 13 }}>
          {formatDate(alert.generatedAt)}
        </Text>
        <Text className="text-ink" style={{ fontSize: 15, lineHeight: 21 }}>
          {alert.headline}
        </Text>
      </Card>

      {responded ? (
        <Card className="mb-4">
          <Text className="text-ink-muted" style={{ fontSize: 13 }}>
            {t(`alertDetail.status.${alert.status}`)}
          </Text>
        </Card>
      ) : (
        <View className="flex-row mb-4" style={{ gap: 8 }}>
          <View className="flex-1">
            <Button
              label={t("alertDetail.markFollowed")}
              loading={responding}
              onPress={() => respond("followed")}
            />
          </View>
          <View className="flex-1">
            <Button
              label={t("alertDetail.markIgnored")}
              variant="outline"
              loading={responding}
              onPress={() => respond("ignored")}
            />
          </View>
        </View>
      )}

      <Button
        label={t("alertDetail.logAction")}
        onPress={() =>
          router.push({
            pathname: "/modals/quick-log",
            params: {
              plantingId: alert.plantingId ?? "",
              activityType: "chemical",
            },
          })
        }
      />

      <Text className="text-ink font-semibold mt-6 mb-2" style={{ fontSize: 16 }}>
        {t("alertDetail.nearbyVendors")}
      </Text>
      {vendors.map((vendor) => (
        <Card key={vendor.id} className="mb-2 flex-row items-center justify-between">
          <Text className="text-ink" style={{ fontSize: 15 }}>
            {vendor.name}
          </Text>
          <Text className="text-ink-muted" style={{ fontSize: 13 }}>
            {vendor.distanceKm} km
          </Text>
        </Card>
      ))}
    </ScreenContainer>
  );
}
