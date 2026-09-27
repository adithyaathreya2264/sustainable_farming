import React, { useEffect, useState } from "react";
import { Text, View } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import { ScreenContainer } from "../../components/ui/ScreenContainer";
import { ModalHeader } from "../../components/ModalHeader";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { SkeletonCard } from "../../components/ui/SkeletonLoader";
import { getPlantingLedger, type Ledger } from "../../services/ledger";
import { getAgriProductById } from "../../services/catalog";
import { useAppState } from "../../hooks/useAppState";
import { metricForPlanting } from "../../lib/scoutingMetrics";
import { formatInr, formatDate } from "../../utils/format";
import { roundDisplay } from "../../utils/unitConversion";
import { PlantingAdvice } from "../../components/ml/PlantingAdvice";

const BREAKDOWN_ICONS: Record<string, string> = {
  chemical: "🧪",
  labor: "👷",
  irrigation: "💧",
};

export default function LedgerScreen() {
  const { t } = useTranslation();
  const { plantingId } = useLocalSearchParams<{ plantingId: string }>();
  const [ledger, setLedger] = useState<Ledger | null>(null);
  const [productNames, setProductNames] = useState<Record<string, string>>({});

  const planting = useAppState((s) => s.plantings.find((p) => p.id === plantingId));
  const crop = useAppState((s) =>
    s.crops.find((c) => c.id === planting?.cropId)
  );
  const scoutingMetric = planting
    ? metricForPlanting(crop, planting.sowingDate)
    : undefined;

  useEffect(() => {
    getPlantingLedger(plantingId).then(async (l) => {
      setLedger(l);
      const entries = await Promise.all(
        l.transactions
          .filter((tx): tx is typeof tx & { productId: string } => Boolean(tx.productId))
          .map(async (tx) => {
            const product = await getAgriProductById(tx.productId);
            return [tx.productId, product?.name ?? tx.productId] as [string, string];
          })
      );
      setProductNames(Object.fromEntries(entries));
    });
  }, [plantingId]);

  if (!ledger) {
    return (
      <ScreenContainer>
        <ModalHeader title={t("ledger.title")} />
        <SkeletonCard />
      </ScreenContainer>
    );
  }

  const profitColor = ledger.netProfit >= 0 ? "text-primary" : "text-danger";

  return (
    <ScreenContainer>
      <ModalHeader title={t("ledger.title")} />

      {scoutingMetric ? (
        <View className="mb-4">
          <Button
            label={t("ledger.logScouting")}
            variant="outline"
            onPress={() =>
              router.push({
                pathname: "/modals/log-scouting",
                params: { plantingId },
              })
            }
          />
        </View>
      ) : null}

      {crop && planting && (
        <PlantingAdvice plantingId={plantingId} fieldId={planting.fieldId} cropName={crop.name} />
      )}

      <Card className="mb-4 items-center py-6">
        <Text className="text-ink-muted" style={{ fontSize: 13 }}>
          {ledger.isPreHarvest
            ? t("ledger.currentCostOfCultivation")
            : t("ledger.netProfit")}
        </Text>
        <Text className={`font-bold mt-1 ${profitColor}`} style={{ fontSize: 30 }}>
          {formatInr(Math.abs(ledger.netProfit))}
        </Text>
        {ledger.marginPct !== null && (
          <Text className="text-ink-muted mt-1" style={{ fontSize: 13 }}>
            {t("ledger.profitMargin")}: {roundDisplay(ledger.marginPct)}%
          </Text>
        )}
      </Card>

      <Text className="text-ink font-semibold mb-2" style={{ fontSize: 15 }}>
        {t("ledger.expenseBreakdown")}
      </Text>
      <Card className="mb-4">
        {ledger.breakdown.map((item) => (
          <View
            key={item.type}
            className="flex-row items-center justify-between mb-2 last:mb-0"
          >
            <Text className="text-ink" style={{ fontSize: 14 }}>
              {BREAKDOWN_ICONS[item.type]} {item.label}
            </Text>
            <Text className="text-ink font-medium" style={{ fontSize: 14 }}>
              {formatInr(item.total)}
            </Text>
          </View>
        ))}
      </Card>

      <Text className="text-ink font-semibold mb-2" style={{ fontSize: 15 }}>
        {t("ledger.recentTransactions")}
      </Text>
      {ledger.transactions.length === 0 ? (
        <Text className="text-ink-muted" style={{ fontSize: 14 }}>
          {t("ledger.noTransactions")}
        </Text>
      ) : (
        ledger.transactions.map((tx) => (
          <Card key={tx.id} className="mb-2 flex-row items-center justify-between">
            <View className="flex-1 pr-2">
              <Text className="text-ink font-medium" style={{ fontSize: 14 }}>
                {tx.productId ? productNames[tx.productId] ?? tx.type : tx.type}
              </Text>
              <Text className="text-ink-muted" style={{ fontSize: 12 }}>
                {formatDate(tx.date)}
              </Text>
            </View>
            <Text
              className={tx.type === "harvest" ? "text-primary font-semibold" : "text-ink font-semibold"}
              style={{ fontSize: 14 }}
            >
              {tx.type === "harvest" ? "+" : "-"}
              {formatInr(tx.costInInr)}
            </Text>
          </Card>
        ))
      )}
    </ScreenContainer>
  );
}
