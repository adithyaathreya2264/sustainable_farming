import React, { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import { ScreenContainer } from "../../../components/ui/ScreenContainer";
import { ModalHeader } from "../../../components/ModalHeader";
import { Card } from "../../../components/ui/Card";
import { Button } from "../../../components/ui/Button";
import { TextField } from "../../../components/ui/TextField";
import { EmptyState } from "../../../components/ui/EmptyState";
import { CaveatText } from "../../../components/ui/CaveatText";
import { ConfidencePill } from "../../../components/ui/ConfidencePill";
import { ModelNotice } from "../../../components/ml/ModelNotice";
import { useAppState } from "../../../hooks/useAppState";
import {
  getDiseaseDetail,
  listDiseases,
  mlErrorMessage,
  remedyFor,
  searchDiseases,
  type DiseaseDetail,
  type DiseaseListItem,
  type DiseaseMatch,
} from "../../../services/ml";

/**
 * "Look up a problem" for one planting: describe symptoms -> up to 3 matching
 * diseases from the crop-scoped Q&A corpus (model 4b).
 *
 * The full "all diseases for this crop" list stays visible below the search
 * at all times. Bar 4b (ml/MODEL_RESULTS.md section 4b) ships the shortlist
 * only on that condition: if the shortlist ever became the sole path to a
 * diagnosis, the bar would have to be raised first.
 */
export default function DiseasesScreen() {
  const { t, i18n } = useTranslation();
  const { plantingId, disease: initialDisease } = useLocalSearchParams<{ plantingId: string; disease?: string }>();
  const planting = useAppState((s) => s.plantings.find((p) => p.id === plantingId));
  const crop = useAppState((s) => s.crops.find((c) => c.id === planting?.cropId));

  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [matches, setMatches] = useState<DiseaseMatch[] | null>(null);
  const [searchNote, setSearchNote] = useState<string | null>(null);
  const [all, setAll] = useState<DiseaseListItem[] | null>(null);
  const [allReason, setAllReason] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(initialDisease ?? null);

  useEffect(() => {
    listDiseases(plantingId)
      .then((r) => {
        setAll(r.diseases);
        setAllReason(r.reason);
      })
      .catch((err) => setError(mlErrorMessage(err, t)));
  }, [plantingId, t]);

  async function search() {
    if (query.trim().length < 2) return;
    setSearching(true);
    setSearchNote(null);
    try {
      const r = await searchDiseases(plantingId, query.trim());
      setMatches(r.matches);
      if (r.reason === "no_close_match") setSearchNote(t("diseases.noCloseMatch"));
    } catch (err) {
      setSearchNote(mlErrorMessage(err, t));
    } finally {
      setSearching(false);
    }
  }

  if (error) {
    return (
      <ScreenContainer>
        <ModalHeader title={t("diseases.title")} />
        <EmptyState icon="🔎" title={error} />
      </ScreenContainer>
    );
  }
  if (allReason === "no_coverage_for_crop") {
    return (
      <ScreenContainer>
        <ModalHeader title={t("diseases.title")} />
        <EmptyState icon="🔎" title={t("diseases.noCoverage", { crop: crop?.name ?? "" })} />
      </ScreenContainer>
    );
  }

  const language = i18n.language;

  return (
    <ScreenContainer>
      <ModalHeader title={t("diseases.title")} />
      {crop && (
        <Text className="text-ink-muted mb-3" style={{ fontSize: 14 }}>
          {crop.name}
        </Text>
      )}

      <TextField
        label={t("diseases.describeLabel")}
        placeholder={t("diseases.describePlaceholder")}
        value={query}
        onChangeText={setQuery}
        onSubmitEditing={search}
        returnKeyType="search"
      />
      <Button label={t("diseases.search")} loading={searching} disabled={query.trim().length < 2} onPress={search} />
      <CaveatText className="mt-2 mb-3">{t("diseases.languageNote")}</CaveatText>
      {searchNote && <CaveatText className="mb-3">{searchNote}</CaveatText>}

      {matches?.map((m) => {
        const remedy = remedyFor(m.remedies, language);
        return (
          <Card key={m.disease} className="mb-3">
            <View className="flex-row items-center justify-between mb-1">
              <Text className="text-ink font-semibold flex-1 pr-2" style={{ fontSize: 16 }}>
                {m.disease}
              </Text>
              <ConfidencePill label={m.confidenceLabel} />
            </View>
            {(m.diseaseType || m.affectedPlantPart) && (
              <Text className="text-ink-muted" style={{ fontSize: 13 }}>
                {[m.diseaseType, m.affectedPlantPart].filter(Boolean).join(" · ")}
              </Text>
            )}
            {m.cause && (
              <Text className="text-ink-muted" style={{ fontSize: 13 }}>
                {t("diseases.cause")}: {m.cause}
              </Text>
            )}
            {m.sharedSymptom && (
              <CaveatText className="mt-1">
                {t("diseases.sharedSymptom", {
                  others: m.alsoSeenIn.map((o) => `${o.crop} / ${o.disease}`).join(", "),
                })}
              </CaveatText>
            )}
            {remedy.text ? (
              <>
                <Text className="text-ink mt-2" style={{ fontSize: 14 }}>
                  {remedy.text}
                </Text>
                {remedy.shownInEnglish && <CaveatText className="mt-1">{t("diseases.shownInEnglish")}</CaveatText>}
              </>
            ) : null}
            <ModelNotice />
          </Card>
        );
      })}

      <Text className="text-ink font-semibold mt-4 mb-2" style={{ fontSize: 15 }}>
        {t("diseases.seeAll")}
      </Text>
      {all === null ? (
        <ActivityIndicator color="#2E7D32" />
      ) : (
        all.map((d) => (
          <DiseaseRow
            key={d.disease}
            item={d}
            plantingId={plantingId}
            language={language}
            open={open === d.disease}
            onToggle={() => setOpen((cur) => (cur === d.disease ? null : d.disease))}
          />
        ))
      )}
    </ScreenContainer>
  );
}

function DiseaseRow({
  item,
  plantingId,
  language,
  open,
  onToggle,
}: {
  item: DiseaseListItem;
  plantingId: string;
  language: string;
  open: boolean;
  onToggle: () => void;
}) {
  const { t } = useTranslation();
  const [detail, setDetail] = useState<DiseaseDetail | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!open || detail) return;
    getDiseaseDetail(plantingId, item.disease)
      .then(setDetail)
      .catch(() => setFailed(true));
  }, [open, detail, plantingId, item.disease]);

  return (
    <Card className="mb-2">
      <Pressable accessibilityRole="button" onPress={onToggle} className="flex-row justify-between items-center">
        <View className="flex-1 pr-2">
          <Text className="text-ink font-medium" style={{ fontSize: 15 }}>
            {item.disease}
          </Text>
          {item.diseaseType && (
            <Text className="text-ink-muted" style={{ fontSize: 12 }}>
              {item.diseaseType}
            </Text>
          )}
        </View>
        <Text className="text-ink-muted">{open ? "▲" : "▼"}</Text>
      </Pressable>
      {open && (
        <View className="mt-2">
          {failed && <CaveatText>{t("ml.checkFailed")}</CaveatText>}
          {!detail && !failed && <ActivityIndicator color="#2E7D32" />}
          {detail && (
            <>
              {detail.cause && (
                <Text className="text-ink-muted mb-1" style={{ fontSize: 13 }}>
                  {t("diseases.cause")}: {detail.cause}
                </Text>
              )}
              {detail.affectedPlantParts.length > 0 && (
                <Text className="text-ink-muted mb-2" style={{ fontSize: 13 }}>
                  {t("diseases.affects")}: {detail.affectedPlantParts.slice(0, 5).join(", ")}
                </Text>
              )}
              <Text className="text-ink font-semibold mb-1" style={{ fontSize: 14 }}>
                {t("diseases.documentedRemedies")}
              </Text>
              {detail.remedies.map((r, i) => {
                const remedy = remedyFor(r, language);
                return (
                  <Text key={i} className="text-ink mb-1" style={{ fontSize: 14 }}>
                    • {remedy.text}
                  </Text>
                );
              })}
              {detail.remedies.some((r) => remedyFor(r, language).shownInEnglish) && (
                <CaveatText className="mt-1">{t("diseases.shownInEnglish")}</CaveatText>
              )}
              <ModelNotice />
            </>
          )}
        </View>
      )}
    </Card>
  );
}
