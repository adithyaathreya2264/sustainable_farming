import React, { useEffect, useState } from "react";
import { ActivityIndicator, Text, View } from "react-native";
import { router } from "expo-router";
import { useTranslation } from "react-i18next";
import { Card } from "../ui/Card";
import { Button } from "../ui/Button";
import { CaveatText } from "../ui/CaveatText";
import { ConfidencePill } from "../ui/ConfidencePill";
import { ModelNotice } from "./ModelNotice";
import {
  getCapabilities,
  getFertilizerCheck,
  getYieldOutlook,
  PHOTO_CHECK_CAPABILITY,
  type Capabilities,
  type FertilizerCheck,
  type Nutrient,
  type YieldOutlook,
} from "../../services/ml";

/**
 * "Crop health & advice" on the ledger screen. What is offered comes from
 * GET /api/v1/ml/capabilities, so a check with no shipped model for this crop
 * (e.g. the rejected sugarcane leaf model) never appears at all.
 */
export function PlantingAdvice({ plantingId, cropName }: { plantingId: string; cropName: string }) {
  const { t } = useTranslation();
  const [caps, setCaps] = useState<Capabilities | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "unavailable">("loading");
  const [fertilizer, setFertilizer] = useState<FertilizerCheck | null>(null);
  const [yieldOutlook, setYieldOutlook] = useState<YieldOutlook | null>(null);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    getCapabilities(plantingId)
      .then(async (c) => {
        if (cancelled) return;
        setCaps(c);
        setStatus("ready");
        const [f, y] = await Promise.all([
          c.fertilizer?.available ? getFertilizerCheck(plantingId).catch(() => null) : null,
          c.yield_outlook?.available ? getYieldOutlook(plantingId).catch(() => null) : null,
        ]);
        if (!cancelled) {
          setFertilizer(f);
          setYieldOutlook(y);
        }
      })
      .catch(() => {
        if (!cancelled) setStatus("unavailable");
      });
    return () => {
      cancelled = true;
    };
  }, [plantingId]);

  if (status === "loading") {
    return (
      <View className="py-4 items-center">
        <ActivityIndicator color="#2E7D32" />
      </View>
    );
  }
  if (status === "unavailable" || !caps) {
    return <CaveatText className="mb-4">{t("ml.unavailable")}</CaveatText>;
  }

  const hasPhotoCheck = Object.values(PHOTO_CHECK_CAPABILITY).some((name) => caps[name]?.available);

  return (
    <View className="mb-4">
      <Text className="text-ink font-semibold mb-2" style={{ fontSize: 15 }}>
        {t("ml.cropHealthTitle")}
      </Text>

      <View className="flex-row mb-3" style={{ gap: 8 }}>
        {hasPhotoCheck && (
          <View className="flex-1">
            <Button
              label={t("photoCheck.open")}
              variant="outline"
              onPress={() => router.push({ pathname: "/planting/[plantingId]/photo-check", params: { plantingId } })}
            />
          </View>
        )}
        {caps.disease_info?.available && (
          <View className="flex-1">
            <Button
              label={t("diseases.open")}
              variant="outline"
              onPress={() => router.push({ pathname: "/planting/[plantingId]/diseases", params: { plantingId } })}
            />
          </View>
        )}
      </View>

      {caps.fertilizer?.available && fertilizer && <NutrientCard check={fertilizer} />}
      {caps.fertilizer && !caps.fertilizer.available && (
        <CaveatText>{t("nutrients.noTarget", { crop: cropName })}</CaveatText>
      )}
      {caps.yield_outlook?.available && yieldOutlook && <YieldCard outlook={yieldOutlook} cropName={cropName} />}
    </View>
  );
}

function NutrientCard({ check }: { check: FertilizerCheck }) {
  const { t } = useTranslation();
  if (!check.available) {
    return <CaveatText>{t(`nutrients.unavailable.${check.reason ?? "other"}`, { defaultValue: t("ml.checkFailed") })}</CaveatText>;
  }
  return (
    <Card className="mb-3">
      <View className="flex-row items-center justify-between mb-2">
        <Text className="text-ink font-semibold" style={{ fontSize: 15 }}>
          {t("nutrients.title")}
        </Text>
        {check.confidenceLabel && <ConfidencePill label={check.confidenceLabel} />}
      </View>
      {(["N", "P", "K"] as Nutrient[]).map((n) => (
        <View key={n} className="flex-row justify-between mb-1">
          <Text className="text-ink" style={{ fontSize: 14 }}>
            {t(`nutrients.name.${n}`)}
          </Text>
          <Text className={check.actionable?.[n] ? "text-danger font-semibold" : "text-primary"} style={{ fontSize: 14 }}>
            {check.actionable?.[n] ? t("nutrients.short") : t("nutrients.ok")}
          </Text>
        </View>
      ))}
      {check.ph && (
        <View className="flex-row justify-between mb-1">
          <Text className="text-ink" style={{ fontSize: 14 }}>
            {t("nutrients.ph")}
          </Text>
          <Text className={check.ph.status === "within_range" ? "text-primary" : "text-danger"} style={{ fontSize: 14 }}>
            {t(`nutrients.phStatus.${check.ph.status}`)}
          </Text>
        </View>
      )}
      {check.products && check.products.length > 0 && Object.values(check.actionable ?? {}).some(Boolean) && (
        <CaveatText className="mt-2">
          {t("nutrients.products", { products: check.products.map((p) => p.name).join(", ") })}
        </CaveatText>
      )}
      <CaveatText className="mt-1">
        {check.basis === "soil_test" ? t("nutrients.basisSoilTest") : t("nutrients.basisStateAverage")}
      </CaveatText>
      <ModelNotice />
    </Card>
  );
}

function YieldCard({ outlook, cropName }: { outlook: YieldOutlook; cropName: string }) {
  const { t } = useTranslation();
  if (!outlook.available || !outlook.position) return null;
  const tone =
    outlook.position === "above typical" || outlook.position === "around typical" ? "text-primary" : "text-danger";
  const positionKey = outlook.position.replace(/ /g, "_");
  return (
    <Card className="mb-3">
      <Text className="text-ink font-semibold mb-1" style={{ fontSize: 15 }}>
        {t("yieldOutlook.title")}
      </Text>
      {/* A band, never a number: the source data has no yield unit (ml/README.md rule 3). */}
      <Text className={`${tone} font-semibold`} style={{ fontSize: 18 }}>
        {t(`yieldOutlook.position.${positionKey}`)}
      </Text>
      <CaveatText className="mt-1">
        {t("yieldOutlook.comparedWith", {
          crop: cropName,
          scope: [outlook.scope?.state, outlook.scope?.season].filter(Boolean).join(" · ") || t("yieldOutlook.allIndia"),
          records: outlook.scope?.sampleCount ?? 0,
        })}
      </CaveatText>
      {outlook.yearInTrainingRange === false && <CaveatText>{t("yieldOutlook.outsideTrainingYears")}</CaveatText>}
      <CaveatText>{t("yieldOutlook.typicalInputs")}</CaveatText>
      <ModelNotice />
    </Card>
  );
}
