import React, { useEffect, useState } from "react";
import { Text, View } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import { ScreenContainer } from "../../components/ui/ScreenContainer";
import { ModalHeader } from "../../components/ModalHeader";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { SkeletonCard } from "../../components/ui/SkeletonLoader";
import { getAlertById, getNearbyVendors } from "../../services/alerts";
import { getAgriProductById } from "../../services/catalog";
import { formatDate } from "../../utils/format";
import type { AgriCatalogItem, Recommendation, Vendor } from "../../types/models";

export default function AlertDetailScreen() {
  const { t } = useTranslation();
  const { id } = useLocalSearchParams<{ id: string }>();
  const [alert, setAlert] = useState<Recommendation | null>(null);
  const [product, setProduct] = useState<AgriCatalogItem | null>(null);
  const [vendors, setVendors] = useState<Vendor[]>([]);

  useEffect(() => {
    getAlertById(id).then((a) => {
      setAlert(a ?? null);
      if (a?.recommendedProductId) {
        getAgriProductById(a.recommendedProductId).then((p) => setProduct(p ?? null));
      }
    });
    getNearbyVendors().then(setVendors);
  }, [id]);

  if (!alert) {
    return (
      <ScreenContainer>
        <ModalHeader title={t("alertDetail.title")} />
        <SkeletonCard />
      </ScreenContainer>
    );
  }

  return (
    <ScreenContainer>
      <ModalHeader title={t("alertDetail.title")} />

      <Card className="mb-4 border-2 border-danger/50 bg-danger/5">
        <View className="flex-row items-center justify-between mb-2">
          <Text style={{ fontSize: 22 }}>⚠️</Text>
          <View className="bg-danger rounded-full px-3 py-1">
            <Text className="text-white" style={{ fontSize: 12 }}>
              {t("alertDetail.confidence", { pct: alert.confidencePct })}
            </Text>
          </View>
        </View>
        <Text className="text-ink font-bold mb-1" style={{ fontSize: 18 }}>
          {alert.title}
        </Text>
        <Text className="text-ink-muted mb-2" style={{ fontSize: 13 }}>
          {formatDate(alert.createdAt)}
        </Text>
        <Text className="text-ink" style={{ fontSize: 15, lineHeight: 21 }}>
          {alert.description}
        </Text>
      </Card>

      {product ? (
        <Card className="mb-4">
          <Text className="text-ink-muted mb-1" style={{ fontSize: 13 }}>
            {t("alertDetail.recommendation")}
          </Text>
          <Text className="text-ink font-semibold" style={{ fontSize: 16 }}>
            {product.name}
          </Text>
        </Card>
      ) : null}

      <Button
        label={t("alertDetail.logAction")}
        onPress={() =>
          router.push({
            pathname: "/modals/quick-log",
            params: {
              plantingId: alert.plantingId,
              activityType: "chemical",
              productId: alert.recommendedProductId ?? "",
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
