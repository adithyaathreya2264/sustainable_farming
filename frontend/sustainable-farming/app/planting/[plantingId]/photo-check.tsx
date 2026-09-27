import React, { useEffect, useMemo, useState } from "react";
import { Image, Pressable, Text, View } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import { ScreenContainer } from "../../../components/ui/ScreenContainer";
import { ModalHeader } from "../../../components/ModalHeader";
import { Card } from "../../../components/ui/Card";
import { Button } from "../../../components/ui/Button";
import { EmptyState } from "../../../components/ui/EmptyState";
import { CaveatText } from "../../../components/ui/CaveatText";
import { ConfidencePill } from "../../../components/ui/ConfidencePill";
import { ModelNotice } from "../../../components/ml/ModelNotice";
import { DetectionOverlay } from "../../../components/ml/DetectionOverlay";
import { PhotoSourceButtons } from "../../../components/ml/PhotoSourceButtons";
import { useAppState } from "../../../hooks/useAppState";
import { pickPhoto, type PhotoSource, type PreparedPhoto } from "../../../lib/photo";
import { metricForPlanting } from "../../../lib/scoutingMetrics";
import {
  getCapabilities,
  isLeafPart,
  mlErrorMessage,
  PHOTO_CHECK_CAPABILITY,
  runPhotoCheck,
  type Capabilities,
  type LeafCondition,
  type PhotoCheckKind,
  type PhotoCheckResult,
} from "../../../services/ml";

const KIND_ORDER: PhotoCheckKind[] = [
  "leaf", "curd", "bulb", "fruit_grade", "insects", "wheat_heading", "wheat_kernels", "tobacco_lesions",
];

/**
 * Photo checks for one planting: leaf disease (rice, pearl millet), insect
 * pests (rice, maize, cotton), wheat heading, tobacco lesion area. Only the
 * checks /ml/capabilities offers for this crop are shown.
 */
export default function PhotoCheckScreen() {
  const { t } = useTranslation();
  const { plantingId } = useLocalSearchParams<{ plantingId: string }>();
  const planting = useAppState((s) => s.plantings.find((p) => p.id === plantingId));
  const crop = useAppState((s) => s.crops.find((c) => c.id === planting?.cropId));

  const [caps, setCaps] = useState<Capabilities | null>(null);
  const [capsError, setCapsError] = useState<string | null>(null);
  const [kind, setKind] = useState<PhotoCheckKind | null>(null);
  const [symptomConfirmed, setSymptomConfirmed] = useState(false);
  const [photo, setPhoto] = useState<PreparedPhoto | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<PhotoCheckResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dismissedAsNone, setDismissedAsNone] = useState(false);

  useEffect(() => {
    getCapabilities(plantingId)
      .then((c) => {
        setCaps(c);
        const first = KIND_ORDER.find((k) => c[PHOTO_CHECK_CAPABILITY[k]]?.available);
        setKind(first ?? null);
      })
      .catch((err) => setCapsError(mlErrorMessage(err, t)));
  }, [plantingId, t]);

  const available = useMemo(
    () => KIND_ORDER.filter((k) => caps?.[PHOTO_CHECK_CAPABILITY[k]]?.available),
    [caps]
  );
  const conditional = Boolean(kind && isLeafPart(kind) && caps?.[PHOTO_CHECK_CAPABILITY[kind]]?.conditional);
  const canPick = Boolean(kind) && (!conditional || symptomConfirmed);
  const scoutingMetric = planting ? metricForPlanting(crop, planting.sowingDate) : undefined;

  async function check(source: PhotoSource) {
    if (!kind) return;
    const picked = await pickPhoto(source);
    if (!picked) return;
    setPhoto(picked);
    setResult(null);
    setError(null);
    setDismissedAsNone(false);
    setBusy(true);
    try {
      const res = await runPhotoCheck(plantingId, kind, picked.uri, conditional ? symptomConfirmed : false);
      setResult(res.result);
    } catch (err) {
      setError(mlErrorMessage(err, t));
    } finally {
      setBusy(false);
    }
  }

  function selectKind(k: PhotoCheckKind) {
    setKind(k);
    setResult(null);
    setPhoto(null);
    setError(null);
    setSymptomConfirmed(false);
  }

  if (capsError) {
    return (
      <ScreenContainer>
        <ModalHeader title={t("photoCheck.title")} />
        <EmptyState icon="📷" title={capsError} />
      </ScreenContainer>
    );
  }
  if (caps && available.length === 0) {
    return (
      <ScreenContainer>
        <ModalHeader title={t("photoCheck.title")} />
        <EmptyState icon="📷" title={t("ml.notForThisCrop")} subtitle={crop?.name} />
      </ScreenContainer>
    );
  }

  return (
    <ScreenContainer>
      <ModalHeader title={t("photoCheck.title")} />
      {crop && (
        <Text className="text-ink-muted mb-3" style={{ fontSize: 14 }}>
          {crop.name}
        </Text>
      )}

      {available.length > 1 && (
        <View className="flex-row flex-wrap mb-3" style={{ gap: 8 }}>
          {available.map((k) => (
            <Pressable
              key={k}
              accessibilityRole="button"
              onPress={() => selectKind(k)}
              className={`rounded-full px-4 py-2 border ${kind === k ? "bg-primary border-primary" : "border-border bg-surface"}`}
            >
              <Text className={kind === k ? "text-white" : "text-ink"} style={{ fontSize: 14 }}>
                {t(`photoCheck.kind.${k}`)}
              </Text>
            </Pressable>
          ))}
        </View>
      )}

      {kind && (
        <CaveatText className="mb-3">{t(`photoCheck.hint.${kind}`)}</CaveatText>
      )}

      {conditional && (
        <Pressable
          accessibilityRole="checkbox"
          accessibilityState={{ checked: symptomConfirmed }}
          onPress={() => setSymptomConfirmed((v) => !v)}
          className="flex-row items-center mb-3"
          style={{ gap: 10, minHeight: 48 }}
        >
          <View
            className={`w-6 h-6 rounded border-2 items-center justify-center ${symptomConfirmed ? "bg-primary border-primary" : "border-ink-muted"}`}
          >
            {symptomConfirmed && <Text className="text-white">✓</Text>}
          </View>
          <Text className="text-ink flex-1" style={{ fontSize: 14 }}>
            {t("photoCheck.symptomConfirm")}
          </Text>
        </Pressable>
      )}

      <PhotoSourceButtons busy={busy} disabled={!canPick} onPick={check} />
      {conditional && !symptomConfirmed && <CaveatText>{t("photoCheck.symptomRequiredHint")}</CaveatText>}

      {error && <CaveatText className="mb-3">{error}</CaveatText>}

      {photo && result?.kind !== "insects" && (
        <Image
          source={{ uri: photo.uri }}
          style={{ width: "100%", aspectRatio: photo.width / photo.height || 1, borderRadius: 16, marginBottom: 12 }}
          resizeMode="cover"
        />
      )}

      {result && photo && (
        <ResultView
          result={result}
          photo={photo}
          plantingId={plantingId}
          canLogScouting={Boolean(scoutingMetric)}
          dismissedAsNone={dismissedAsNone}
          onNoneOfThese={() => setDismissedAsNone(true)}
        />
      )}
    </ScreenContainer>
  );
}

function ResultView({
  result,
  photo,
  plantingId,
  canLogScouting,
  dismissedAsNone,
  onNoneOfThese,
}: {
  result: PhotoCheckResult;
  photo: PreparedPhoto;
  plantingId: string;
  canLogScouting: boolean;
  dismissedAsNone: boolean;
  onNoneOfThese: () => void;
}) {
  const { t } = useTranslation();

  if (result.kind === "leaf") {
    const isGrade = result.part === "fruit_grade";
    if (!result.condition) {
      return <CaveatText>{t(`photoCheck.leafReason.${result.reason ?? "none"}`, { defaultValue: t("ml.checkFailed") })}</CaveatText>;
    }
    if (dismissedAsNone) {
      return (
        <Card className="mb-3">
          <Text className="text-ink" style={{ fontSize: 14 }}>
            {t("photoCheck.noneOfTheseChosen")}
          </Text>
          <DiseaseListLink plantingId={plantingId} />
        </Card>
      );
    }
    return (
      <Card className="mb-3">
        {isGrade && (
          <Text className="text-ink-muted mb-1" style={{ fontSize: 13 }}>
            {t("photoCheck.gradeTitle")}
          </Text>
        )}
        <LeafRow condition={result.condition} plantingId={plantingId} primary />
        {result.condition.category === "unclassified" && (
          <CaveatText className="mb-1">{t("photoCheck.causeNotIdentified")}</CaveatText>
        )}
        {result.alternatives.length > 0 && (
          <Text className="text-ink-muted mt-3 mb-1" style={{ fontSize: 13 }}>
            {t("photoCheck.otherPossibilities")}
          </Text>
        )}
        {result.alternatives.map((a) => (
          <LeafRow key={a.key} condition={a} plantingId={plantingId} />
        ))}
        {result.offerNoneOfThese && (
          <View className="mt-3">
            <Button label={t("photoCheck.noneOfThese")} variant="outline" onPress={onNoneOfThese} />
          </View>
        )}
        {result.caveats.map((c) => (
          <CaveatText key={c} className="mt-2">
            {c}
          </CaveatText>
        ))}
        <ModelNotice />
      </Card>
    );
  }

  if (result.kind === "insects") {
    const linked = result.detections.some((d) => d.relatedRules.length > 0);
    return (
      <View>
        <DetectionOverlay uri={photo.uri} aspectRatio={photo.width / photo.height} detections={result.detections} />
        <Card className="mb-3">
          {result.noDetection || result.detections.length === 0 ? (
            <Text className="text-ink" style={{ fontSize: 14 }}>
              {t("photoCheck.noInsectFound")}
            </Text>
          ) : (
            result.detections.map((d, i) => (
              <View key={`${d.key}-${i}`} className="flex-row items-center justify-between mb-2">
                <View className="flex-1 pr-2">
                  <Text className="text-ink font-semibold" style={{ fontSize: 15 }}>
                    {d.displayName}
                  </Text>
                  {!d.pestOfThisCrop && (
                    <CaveatText className="">{t("photoCheck.notPestOfThisCrop")}</CaveatText>
                  )}
                </View>
                <ConfidencePill label={d.confidenceLabel} />
              </View>
            ))
          )}
          {linked && canLogScouting && (
            <View className="mt-2">
              <Button
                label={t("photoCheck.logScoutingCheck")}
                variant="outline"
                onPress={() => router.push({ pathname: "/modals/log-scouting", params: { plantingId } })}
              />
            </View>
          )}
          {result.caveats.map((c) => (
            <CaveatText key={c} className="mt-2">
              {c}
            </CaveatText>
          ))}
          <ModelNotice />
        </Card>
      </View>
    );
  }

  if (result.kind === "wheat_kernels") {
    return (
      <Card className="mb-3">
        <View className="flex-row items-center justify-between">
          <Text className="text-ink font-semibold" style={{ fontSize: 16 }}>
            {t(`photoCheck.kernel.${result.kernelCondition}`)}
          </Text>
          <ConfidencePill label={result.confidenceLabel} />
        </View>
        {result.caveats.map((c) => (
          <CaveatText key={c} className="mt-2">
            {c}
          </CaveatText>
        ))}
        <ModelNotice />
      </Card>
    );
  }

  if (result.kind === "wheat_heading") {
    return (
      <Card className="mb-3">
        <Text className="text-ink font-semibold" style={{ fontSize: 16 }}>
          {result.headingDetected ? t("photoCheck.headingDetected") : t("photoCheck.headingNotDetected")}
        </Text>
        {result.caveats.map((c) => (
          <CaveatText key={c} className="mt-2">
            {c}
          </CaveatText>
        ))}
        <ModelNotice />
      </Card>
    );
  }

  return (
    <Card className="mb-3">
      <Text className="text-ink font-semibold" style={{ fontSize: 16 }}>
        {t("photoCheck.lesionArea", { percent: Math.round(result.lesionAreaPercent) })}
      </Text>
      <CaveatText className="mt-1">{t("photoCheck.lesionOverestimates")}</CaveatText>
      {result.caveats.map((c) => (
        <CaveatText key={c} className="mt-2">
          {c}
        </CaveatText>
      ))}
      <ModelNotice />
    </Card>
  );
}

function LeafRow({ condition, plantingId, primary = false }: { condition: LeafCondition; plantingId: string; primary?: boolean }) {
  const { t } = useTranslation();
  return (
    <View className="mb-2">
      <View className="flex-row items-center justify-between">
        <Text className={`text-ink ${primary ? "font-semibold" : ""}`} style={{ fontSize: primary ? 17 : 14 }}>
          {condition.displayName}
        </Text>
        <ConfidencePill label={condition.confidenceLabel} />
      </View>
      {condition.qaDisease && (
        <Pressable
          accessibilityRole="link"
          onPress={() =>
            router.push({
              pathname: "/planting/[plantingId]/diseases",
              params: { plantingId, disease: condition.qaDisease ?? "" },
            })
          }
        >
          <Text className="text-primary mt-1" style={{ fontSize: 13 }}>
            {t("photoCheck.seeRemedies")}
          </Text>
        </Pressable>
      )}
    </View>
  );
}

function DiseaseListLink({ plantingId }: { plantingId: string }) {
  const { t } = useTranslation();
  return (
    <Pressable
      accessibilityRole="link"
      onPress={() => router.push({ pathname: "/planting/[plantingId]/diseases", params: { plantingId } })}
    >
      <Text className="text-primary mt-2" style={{ fontSize: 13 }}>
        {t("diseases.seeAll")}
      </Text>
    </Pressable>
  );
}
