import React, { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { ScreenContainer } from "../components/ui/ScreenContainer";
import { ModalHeader } from "../components/ModalHeader";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { CaveatText } from "../components/ui/CaveatText";
import { ConfidencePill } from "../components/ui/ConfidencePill";
import { ModelNotice } from "../components/ml/ModelNotice";
import { formatInr } from "../utils/format";
import {
  getMarketCommodities,
  getMarketOutlook,
  mlErrorMessage,
  type MarketCommodities,
  type MarketOutlook,
  type MonthRange,
} from "../services/ml";

/**
 * Karnataka mandi prices (model 18). Two things, kept visibly apart:
 *
 * - "Historical price range" per month - past prices, 2023 to early 2026.
 *   Never labelled as an expectation: 2026 prices fell outside it 64% of
 *   the time (ml/MODEL_RESULTS.md section 18).
 * - A 13-week forecast, only for the 8 commodities that passed their bar,
 *   always with its origin date and caveats. No sell/hold advice.
 */
export default function MarketScreen() {
  const { t } = useTranslation();
  const [catalog, setCatalog] = useState<MarketCommodities | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [outlook, setOutlook] = useState<MarketOutlook | null>(null);
  const [loadingOutlook, setLoadingOutlook] = useState(false);

  useEffect(() => {
    getMarketCommodities()
      .then((c) => {
        setCatalog(c);
        const own = c.commodities.find((x) => x.cropKey && c.ownCropKeys.includes(x.cropKey));
        setSelected((own ?? c.commodities[0])?.commodity ?? null);
      })
      .catch((err) => setError(mlErrorMessage(err, t)));
  }, [t]);

  useEffect(() => {
    if (!selected || !catalog?.available) return;
    let cancelled = false;
    setLoadingOutlook(true);
    getMarketOutlook(selected)
      .then((o) => !cancelled && setOutlook(o))
      .catch(() => !cancelled && setOutlook(null))
      .finally(() => !cancelled && setLoadingOutlook(false));
    return () => {
      cancelled = true;
    };
  }, [selected, catalog?.available]);

  const ordered = useMemo(() => {
    if (!catalog) return [];
    const own = (c: { cropKey: string | null }) => Boolean(c.cropKey && catalog.ownCropKeys.includes(c.cropKey));
    return [...catalog.commodities].sort((a, b) => Number(own(b)) - Number(own(a)));
  }, [catalog]);

  if (error) {
    return (
      <ScreenContainer>
        <ModalHeader title={t("market.title")} />
        <EmptyState icon="🏷️" title={error} />
      </ScreenContainer>
    );
  }
  if (!catalog) {
    return (
      <ScreenContainer>
        <ModalHeader title={t("market.title")} />
        <ActivityIndicator color="#2E7D32" />
      </ScreenContainer>
    );
  }
  if (!catalog.available) {
    return (
      <ScreenContainer>
        <ModalHeader title={t("market.title")} />
        <EmptyState icon="🏷️" title={t("market.karnatakaOnly")} subtitle={t("market.karnatakaOnlySubtitle")} />
      </ScreenContainer>
    );
  }

  return (
    <ScreenContainer>
      <ModalHeader title={t("market.title")} />

      <View className="flex-row flex-wrap mb-4" style={{ gap: 8 }}>
        {ordered.map((c) => (
          <Pressable
            key={c.commodity}
            accessibilityRole="button"
            onPress={() => setSelected(c.commodity)}
            className={`rounded-full px-3 py-1.5 border ${selected === c.commodity ? "bg-primary border-primary" : "border-border bg-surface"}`}
          >
            <Text className={selected === c.commodity ? "text-white" : "text-ink"} style={{ fontSize: 13 }}>
              {t(`market.commodity.${c.commodity}`, { defaultValue: c.commodity })}
            </Text>
          </Pressable>
        ))}
      </View>

      {loadingOutlook && <ActivityIndicator color="#2E7D32" />}

      {!loadingOutlook && outlook && !outlook.available && (
        <CaveatText>{t("market.noHistory")}</CaveatText>
      )}

      {!loadingOutlook && outlook?.available && (
        <>
          <Text className="text-ink-muted mb-2" style={{ fontSize: 13 }}>
            {outlook.level === "district" && outlook.district
              ? t("market.scopeDistrict", { district: outlook.district })
              : t("market.scopeState")}
            {" · "}
            {t("market.unit")}
          </Text>

          {outlook.commodity === "rice" && <CaveatText>{t("market.milledRice")}</CaveatText>}
          {outlook.commodity === "paddy" && <CaveatText>{t("market.paddyNoForecast")}</CaveatText>}

          {outlook.forecast ? (
            <Card className="mb-4">
              <View className="flex-row items-center justify-between mb-2">
                <Text className="text-ink font-semibold" style={{ fontSize: 15 }}>
                  {t("market.forecastTitle")}
                </Text>
                <ConfidencePill label={outlook.forecast.confidenceLabel} />
              </View>
              <Text className="text-ink-muted" style={{ fontSize: 13 }}>
                {t("market.lastPrice", { date: outlook.forecast.originWeek })}
              </Text>
              <Text className="text-ink font-bold mb-2" style={{ fontSize: 20 }}>
                {formatInr(outlook.forecast.currentPrice)}
              </Text>
              <Text className="text-ink" style={{ fontSize: 15 }}>
                {t(`market.direction.${outlook.forecast.direction}`)}{" "}
                {t("market.byDate", { date: outlook.forecast.targetWeek })}
              </Text>
              <Text className="text-ink-muted" style={{ fontSize: 13 }}>
                {t("market.likelyRange", {
                  low: formatInr(outlook.forecast.range[0]),
                  high: formatInr(outlook.forecast.range[1]),
                })}
              </Text>
              {outlook.caveats.map((c) => (
                <CaveatText key={c} className="mt-2">
                  {c}
                </CaveatText>
              ))}
              <ModelNotice />
            </Card>
          ) : (
            <CaveatText className="mb-3">{t("market.noForecast")}</CaveatText>
          )}

          <Text className="text-ink font-semibold mb-1" style={{ fontSize: 15 }}>
            {t("market.historicalRange")}
          </Text>
          <CaveatText>{t("market.historicalRangeNote")}</CaveatText>
          <MonthlyRanges months={outlook.months} />
        </>
      )}
    </ScreenContainer>
  );
}

/** One row per month: a bar spanning the historical 25th-75th percentile, a
 * tick at the median. Scaled to the commodity's own min/max. */
function MonthlyRanges({ months }: { months: MonthRange[] }) {
  const { t } = useTranslation();
  if (months.length === 0) return null;
  const low = Math.min(...months.map((m) => m.p25));
  const high = Math.max(...months.map((m) => m.p75));
  const span = Math.max(high - low, 1);
  const pct = (v: number) => `${((v - low) / span) * 100}%` as const;

  return (
    <Card className="mb-4">
      {months.map((m) => (
        <View key={m.month} className="flex-row items-center mb-2">
          <Text className="text-ink-muted" style={{ width: 40, fontSize: 12 }}>
            {t(`market.month.${m.month}`)}
          </Text>
          <View className="flex-1 h-3 rounded-full bg-background" style={{ position: "relative" }}>
            <View
              className="h-3 rounded-full bg-primary-light"
              style={{ position: "absolute", left: pct(m.p25), width: `${((m.p75 - m.p25) / span) * 100}%` }}
            />
            <View
              className="bg-primary-dark"
              style={{ position: "absolute", left: pct(m.median), width: 2, height: 12 }}
            />
          </View>
          <Text className="text-ink" style={{ width: 72, fontSize: 12, textAlign: "right" }}>
            {formatInr(m.median)}
          </Text>
        </View>
      ))}
      <CaveatText className="mt-1">
        {t("market.scaleNote", { low: formatInr(low), high: formatInr(high) })}
      </CaveatText>
    </Card>
  );
}
