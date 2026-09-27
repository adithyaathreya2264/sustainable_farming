import React, { useCallback, useState } from "react";
import { ActivityIndicator, Text, View } from "react-native";
import { router, useFocusEffect } from "expo-router";
import { useTranslation } from "react-i18next";
import { Card } from "../ui/Card";
import { Button } from "../ui/Button";
import { CaveatText } from "../ui/CaveatText";
import { ConfidencePill } from "../ui/ConfidencePill";
import { ModelNotice } from "./ModelNotice";
import {
  getCapabilities,
  getFertilizerCheck,
  getSoilFertility,
  getYieldOutlook,
  PHOTO_CHECK_CAPABILITY,
  type Capabilities,
  type FertilizerCheck,
  type Nutrient,
  type SoilFertility,
  type YieldOutlook,
} from "../../services/ml";

/**
 * "Crop health & advice" on the ledger screen. What is offered comes from
 * GET /api/v1/ml/capabilities, so a check with no shipped model for this crop
 * (e.g. the rejected sugarcane leaf model) never appears at all.
 */
export function PlantingAdvice({
  plantingId,
  fieldId,
  cropName,
}: {
  plantingId: string;
  fieldId: string;
  cropName: string;
}) {
  const { t } = useTranslation();
  const [caps, setCaps] = useState<Capabilities | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "unavailable">(
    "loading",
  );
  const [fertilizer, setFertilizer] = useState<FertilizerCheck | null>(null);
  const [yieldOutlook, setYieldOutlook] = useState<YieldOutlook | null>(null);

  // On focus, not mount: returning from the add-soil-test modal must refresh
  // the nutrient check, which reads the field's latest soil test.
  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      getCapabilities(plantingId)
        .then(async (c) => {
          if (cancelled) return;
          setCaps(c);
          setStatus("ready");
          const [f, y] = await Promise.all([
            c.fertilizer?.available
              ? getFertilizerCheck(plantingId).catch(() => null)
              : null,
            c.yield_outlook?.available
              ? getYieldOutlook(plantingId).catch(() => null)
              : null,
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
    }, [plantingId]),
  );

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

  const hasPhotoCheck = Object.values(PHOTO_CHECK_CAPABILITY).some(
    (name) => caps[name]?.available,
  );

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
              onPress={() =>
                router.push({
                  pathname: "/planting/[plantingId]/photo-check",
                  params: { plantingId },
                })
              }
            />
          </View>
        )}
        {caps.disease_info?.available && (
          <View className="flex-1">
            <Button
              label={t("diseases.open")}
              variant="outline"
              onPress={() =>
                router.push({
                  pathname: "/planting/[plantingId]/diseases",
                  params: { plantingId },
                })
              }
            />
          </View>
        )}
      </View>

      <SoilFertilityCard fieldId={fieldId} />
      {caps.fertilizer?.available && fertilizer && (
        <NutrientCard check={fertilizer} />
      )}
      {caps.fertilizer && !caps.fertilizer.available && (
        <CaveatText>{t("nutrients.noTarget", { crop: cropName })}</CaveatText>
      )}
      {caps.yield_outlook?.available && yieldOutlook && (
        <YieldCard outlook={yieldOutlook} cropName={cropName} />
      )}
    </View>
  );
}

function NutrientCard({ check }: { check: FertilizerCheck }) {
  const { t } = useTranslation();
  if (!check.available) {
    return (
      <CaveatText>
        {t(`nutrients.unavailable.${check.reason ?? "other"}`, {
          defaultValue: t("ml.checkFailed"),
        })}
      </CaveatText>
    );
  }
  return (
    <Card className="mb-3">
      <View className="flex-row items-center justify-between mb-2">
        <Text className="text-ink font-semibold" style={{ fontSize: 15 }}>
          {t("nutrients.title")}
        </Text>
        {check.confidenceLabel && (
          <ConfidencePill label={check.confidenceLabel} />
        )}
      </View>
      {(["N", "P", "K"] as Nutrient[]).map((n) => (
        <View key={n} className="flex-row justify-between mb-1">
          <Text className="text-ink" style={{ fontSize: 14 }}>
            {t(`nutrients.name.${n}`)}
          </Text>
          <Text
            className={
              check.actionable?.[n]
                ? "text-danger font-semibold"
                : "text-primary"
            }
            style={{ fontSize: 14 }}
          >
            {check.actionable?.[n] ? t("nutrients.short") : t("nutrients.ok")}
          </Text>
        </View>
      ))}
      {check.ph && (
        <View className="flex-row justify-between mb-1">
          <Text className="text-ink" style={{ fontSize: 14 }}>
            {t("nutrients.ph")}
          </Text>
          <Text
            className={
              check.ph.status === "within_range"
                ? "text-primary"
                : "text-danger"
            }
            style={{ fontSize: 14 }}
          >
            {t(`nutrients.phStatus.${check.ph.status}`)}
          </Text>
        </View>
      )}
      {check.products &&
        check.products.length > 0 &&
        Object.values(check.actionable ?? {}).some(Boolean) && (
          <CaveatText className="mt-2">
            {t("nutrients.products", {
              products: check.products.map((p) => p.name).join(", "),
            })}
          </CaveatText>
        )}
      <CaveatText className="mt-1">
        {check.basis === "soil_test"
          ? t("nutrients.basisSoilTest")
          : t("nutrients.basisStateAverage")}
      </CaveatText>
      <ModelNotice />
    </Card>
  );
}

function YieldCard({
  outlook,
  cropName,
}: {
  outlook: YieldOutlook;
  cropName: string;
}) {
  const { t } = useTranslation();
  if (!outlook.available || !outlook.position) return null;
  const tone =
    outlook.position === "above typical" ||
    outlook.position === "around typical"
      ? "text-primary"
      : "text-danger";
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
          scope:
            [outlook.scope?.state, outlook.scope?.season]
              .filter(Boolean)
              .join(" · ") || t("yieldOutlook.allIndia"),
          records: outlook.scope?.sampleCount ?? 0,
        })}
      </CaveatText>
      {outlook.yearInTrainingRange === false && (
        <CaveatText>{t("yieldOutlook.outsideTrainingYears")}</CaveatText>
      )}
      <CaveatText>{t("yieldOutlook.typicalInputs")}</CaveatText>
      <ModelNotice />
    </Card>
  );
}

/**
 * Soil fertility class (model 5b) for the planting's field. Needs a full
 * 12-value soil-test card; otherwise it says which values are missing and
 * offers to add them. Refetched on focus so a card entered in the modal
 * shows up on return.
 */
function SoilFertilityCard({ fieldId }: { fieldId: string }) {
  const { t } = useTranslation();
  const [result, setResult] = useState<SoilFertility | null>(null);
  const [failed, setFailed] = useState(false);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      getSoilFertility(fieldId)
        .then((r) => {
          if (!cancelled) {
            setResult(r);
            setFailed(false);
          }
        })
        .catch(() => !cancelled && setFailed(true));
      return () => {
        cancelled = true;
      };
    }, [fieldId]),
  );

  if (failed || !result) return null;

  const addCard = (
    <View className="mt-2">
      <Button
        label={t("soilFertility.addCard")}
        variant="outline"
        onPress={() =>
          router.push({
            pathname: "/modals/add-soil-test",
            params: { fieldId, expand: "1" },
          })
        }
      />
    </View>
  );

  if (!result.available) {
    return (
      <Card className="mb-3">
        <Text className="text-ink font-semibold mb-1" style={{ fontSize: 15 }}>
          {t("soilFertility.title")}
        </Text>
        <Text className="text-ink-muted" style={{ fontSize: 13 }}>
          {result.reason === "incomplete_soil_test"
            ? t("soilFertility.incomplete", {
                values: result.missing
                  .map((m) => t(`soilTest.short.${m}`))
                  .join(", "),
              })
            : t("soilFertility.noTest")}
        </Text>
        {addCard}
      </Card>
    );
  }

  const tone =
    result.fertilityClass === "high"
      ? "text-primary"
      : result.fertilityClass === "low"
        ? "text-danger"
        : "text-ink";
  return (
    <Card className="mb-3">
      <View className="flex-row items-center justify-between mb-1">
        <Text className="text-ink font-semibold" style={{ fontSize: 15 }}>
          {t("soilFertility.title")}
        </Text>
        {result.confidenceLabel && (
          <ConfidencePill label={result.confidenceLabel} />
        )}
      </View>
      <Text className={`${tone} font-semibold`} style={{ fontSize: 18 }}>
        {t(`soilFertility.class.${result.fertilityClass}`)}
      </Text>
      <CaveatText className="mt-1">{t("soilFertility.whatItMeans")}</CaveatText>
      <CaveatText>{t("soilFertility.provenance")}</CaveatText>
      <ModelNotice />
    </Card>
  );
}
