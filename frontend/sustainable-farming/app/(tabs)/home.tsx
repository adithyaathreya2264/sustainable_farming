import React, { useCallback, useState } from "react";
import { Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { router, useFocusEffect } from "expo-router";
import { ScreenContainer } from "../../components/ui/ScreenContainer";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { EmptyState } from "../../components/ui/EmptyState";
import { SkeletonCard } from "../../components/ui/SkeletonLoader";
import { AlertCard } from "../../components/AlertCard";
import { WeatherWidget } from "../../components/WeatherWidget";
import { useSession } from "../../context/SessionContext";
import { useAppState } from "../../hooks/useAppState";
import { getRecommendationAlerts } from "../../services/alerts";
import { getSeasonFinancials, type SeasonFinancials } from "../../services/ledger";
import { formatInr } from "../../utils/format";
import type { Alert } from "../../types/models";

export default function HomeScreen() {
  const { t } = useTranslation();
  const { user } = useSession();
  const fields = useAppState((s) => s.fields);
  const plantings = useAppState((s) => s.plantings);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [financials, setFinancials] = useState<SeasonFinancials | null>(null);

  useFocusEffect(
    useCallback(() => {
      getRecommendationAlerts().then(setAlerts);
      getSeasonFinancials().then(setFinancials);
    }, [])
  );

  const hasFields = fields.length > 0;

  return (
    <ScreenContainer>
      <View className="flex-row items-center justify-between mb-1">
        <Text className="text-ink font-bold" style={{ fontSize: 22 }}>
          {t("home.welcome", { name: user.name })}
        </Text>
      </View>

      {!hasFields ? (
        <EmptyState
          icon="🗺️"
          title={t("home.emptyStateTitle")}
          subtitle={t("home.emptyStateSubtitle")}
          action={
            <Button
              label={t("fields.addField")}
              onPress={() => router.push("/modals/add-field")}
            />
          }
        />
      ) : (
        <>
          <WeatherWidget />

          <Card className="mb-4">
            <Text className="text-ink font-semibold mb-1" style={{ fontSize: 15 }}>
              🏷️ {t("market.homeCardTitle")}
            </Text>
            <Text className="text-ink-muted mb-3" style={{ fontSize: 13 }}>
              {t("market.homeCardSubtitle")}
            </Text>
            <Button label={t("market.open")} variant="outline" onPress={() => router.push("/market")} />
          </Card>

          <Card className="mb-4">
            <Text className="text-ink font-semibold mb-2" style={{ fontSize: 15 }}>
              📈 {t("home.seasonFinancials")}
            </Text>
            {financials ? (
              <View className="flex-row justify-between mb-3">
                <View>
                  <Text className="text-ink-muted" style={{ fontSize: 13 }}>
                    {t("home.totalSpent")}
                  </Text>
                  <Text className="text-danger font-bold" style={{ fontSize: 18 }}>
                    {formatInr(financials.totalSpent)}
                  </Text>
                </View>
                <View>
                  <Text className="text-ink-muted" style={{ fontSize: 13 }}>
                    {t("home.totalEarned")}
                  </Text>
                  <Text className="text-primary font-bold" style={{ fontSize: 18 }}>
                    {formatInr(financials.totalEarned)}
                  </Text>
                </View>
              </View>
            ) : (
              <SkeletonCard />
            )}
            {plantings.length > 0 ? (
              <Button
                label={t("home.viewFullLedger")}
                variant="outline"
                onPress={() => router.push(`/ledger/${plantings[0].id}`)}
              />
            ) : null}
          </Card>

          <Text className="text-ink font-semibold mb-2" style={{ fontSize: 16 }}>
            {t("home.alertsTitle")}
          </Text>
          {alerts.length === 0 ? (
            <Text className="text-ink-muted mb-4" style={{ fontSize: 14 }}>
              {t("home.noAlerts")}
            </Text>
          ) : (
            alerts.map((alert) => (
              <AlertCard
                key={alert.id}
                alert={alert}
                onPress={() => router.push(`/alert/${alert.id}`)}
              />
            ))
          )}
        </>
      )}
    </ScreenContainer>
  );
}
