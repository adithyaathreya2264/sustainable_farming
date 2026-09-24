import { apiErrorReason, apiFetch, apiUpload } from "../lib/apiClient";
import type { ConfidenceLabel } from "../types/models";

/**
 * Model-backed features, all under /api/v1/ml (backend/src/routes/ml.js ->
 * services/mlClient.js -> the Python sidecar in ml/serving/).
 *
 * Nothing here is cached in the store: results are advice for the screen that
 * asked, and several are photo-specific. Every call throws ApiError on
 * failure; use `apiErrorReason(err)` to tell "model service down"
 * (ml_unavailable) from "not offered for this crop" (model_did_not_ship,
 * no_model_for_crop, ...) and show the right empty state.
 *
 * Invariants the backend enforces and these types reflect: no probability or
 * score ever arrives (only a ConfidenceLabel), yield is a band never a number,
 * and product names come from agri_catalog, not from a model.
 */

// --- capabilities -----------------------------------------------------------

export type CapabilityName =
  | "leaf_diagnosis"
  | "insect_detection"
  | "wheat_heading"
  | "tobacco_lesions"
  | "disease_info"
  | "fertilizer"
  | "yield_outlook"
  | "price";

export interface Capability {
  available: boolean;
  reason?: string;
  /** leaf_diagnosis only: the model has no healthy class, so the farmer must
   * confirm visible symptoms first. */
  conditional?: boolean;
  commodities?: MarketCommodity[];
}

export type Capabilities = Partial<Record<CapabilityName, Capability>>;

export async function getCapabilities(plantingId: string): Promise<Capabilities> {
  const res = await apiFetch<{ crop_key: string; capabilities: Capabilities }>(
    `/api/v1/ml/capabilities?planting_id=${encodeURIComponent(plantingId)}`
  );
  return res.capabilities;
}

// --- soil type from photo ---------------------------------------------------

export interface SoilTypePhotoResult {
  inferenceId: string;
  predictedSoilType: string;
  /** Matching key in utils/soilTypes.ts, or null (Cinder soil has none). */
  appSoilKey: string | null;
  confidenceLabel: ConfidenceLabel;
}

export async function identifySoilFromPhoto(uri: string, fieldId?: string): Promise<SoilTypePhotoResult> {
  const res = await apiUpload<{
    inference_id: string;
    predicted_soil_type: string;
    app_soil_key: string | null;
    confidence_label: ConfidenceLabel;
  }>("/api/v1/ml/soil-type", { uri, fields: { field_id: fieldId } });
  return {
    inferenceId: res.inference_id,
    predictedSoilType: res.predicted_soil_type,
    appSoilKey: res.app_soil_key,
    confidenceLabel: res.confidence_label,
  };
}

// --- photo checks on a planting ---------------------------------------------

export type PhotoCheckKind = "insects" | "leaf" | "wheat_heading" | "tobacco_lesions";

export const PHOTO_CHECK_CAPABILITY: Record<PhotoCheckKind, CapabilityName> = {
  insects: "insect_detection",
  leaf: "leaf_diagnosis",
  wheat_heading: "wheat_heading",
  tobacco_lesions: "tobacco_lesions",
};

export interface Box {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface InsectDetection {
  key: string;
  displayName: string;
  confidenceLabel: ConfidenceLabel;
  pestOfThisCrop: boolean;
  relatedRules: string[];
  /** Fractions (0-1) of the image width/height. */
  box: Box;
}

export interface LeafCondition {
  key: string;
  displayName: string;
  category: "healthy" | "disease" | "pest_damage" | "abiotic" | "unclassified";
  /** Name to look up in the disease corpus, or null when none is linked. */
  qaDisease: string | null;
  confidenceLabel: ConfidenceLabel;
}

export type PhotoCheckResult =
  | { kind: "insects"; detections: InsectDetection[]; noDetection: boolean; caveats: string[] }
  | {
      kind: "leaf";
      condition: LeafCondition | null;
      alternatives: LeafCondition[];
      offerNoneOfThese: boolean;
      reason: string | null;
      caveats: string[];
    }
  | { kind: "wheat_heading"; headingDetected: boolean; caveats: string[] }
  | { kind: "tobacco_lesions"; lesionAreaPercent: number; caveats: string[] };

interface BackendLeafCondition {
  key: string;
  display_name: string;
  category: LeafCondition["category"];
  qa_disease: string | null;
  confidence_label: ConfidenceLabel;
}

const leafFromBackend = (c: BackendLeafCondition): LeafCondition => ({
  key: c.key,
  displayName: c.display_name,
  category: c.category,
  qaDisease: c.qa_disease,
  confidenceLabel: c.confidence_label,
});

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function photoCheckFromBackend(kind: PhotoCheckKind, r: any): PhotoCheckResult {
  const caveats: string[] = r.caveats ?? [];
  switch (kind) {
    case "insects":
      return {
        kind,
        caveats,
        noDetection: Boolean(r.no_detection),
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        detections: (r.detections ?? []).map((d: any) => ({
          key: d.key,
          displayName: d.display_name,
          confidenceLabel: d.confidence_label,
          pestOfThisCrop: Boolean(d.pest_of_this_crop),
          relatedRules: d.related_rules ?? [],
          box: d.box,
        })),
      };
    case "leaf":
      return {
        kind,
        caveats,
        condition: r.condition ? leafFromBackend(r.condition) : null,
        alternatives: (r.alternatives ?? []).map(leafFromBackend),
        offerNoneOfThese: Boolean(r.offer_none_of_these),
        reason: r.reason ?? null,
      };
    case "wheat_heading":
      return { kind, caveats, headingDetected: Boolean(r.heading_detected) };
    case "tobacco_lesions":
      return { kind, caveats, lesionAreaPercent: Number(r.lesion_area_percent) };
  }
}

export async function runPhotoCheck(
  plantingId: string,
  kind: PhotoCheckKind,
  uri: string,
  symptomReported = false
): Promise<{ inferenceId: string; result: PhotoCheckResult }> {
  const res = await apiUpload<{ inference_id: string; result: unknown }>(
    `/api/v1/ml/plantings/${encodeURIComponent(plantingId)}/photo-check`,
    { uri, fields: { kind, symptom_reported: kind === "leaf" ? symptomReported : undefined } }
  );
  return { inferenceId: res.inference_id, result: photoCheckFromBackend(kind, res.result) };
}

// --- nutrient check ----------------------------------------------------------

export type Nutrient = "N" | "P" | "K";

export interface FertilizerCheck {
  available: boolean;
  reason?: string;
  basis?: "soil_test" | "state_average";
  /** Which nutrients are short of the crop's target by more than the threshold. */
  actionable?: Record<Nutrient, boolean>;
  ph?: { value: number; targetMin: number; targetMax: number; status: "below_range" | "within_range" | "above_range" };
  confidenceLabel?: ConfidenceLabel;
  products?: { id: string; name: string }[];
}

export async function getFertilizerCheck(plantingId: string): Promise<FertilizerCheck> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const r = await apiFetch<any>(`/api/v1/ml/plantings/${encodeURIComponent(plantingId)}/fertilizer`);
  if (!r.available) return { available: false, reason: r.reason };
  return {
    available: true,
    basis: r.basis,
    actionable: r.actionable,
    ph: { value: r.ph.value, targetMin: r.ph.target_min, targetMax: r.ph.target_max, status: r.ph.status },
    confidenceLabel: r.confidence_label,
    products: (r.products ?? []).map((p: { id: string; name: string }) => ({ id: p.id, name: p.name })),
  };
}

// --- yield outlook ------------------------------------------------------------

export type YieldPosition = "above typical" | "around typical" | "below typical" | "well below typical";

export interface YieldOutlook {
  available: boolean;
  reason?: string;
  position?: YieldPosition | null;
  scope?: { scope: string; state: string | null; season: string | null; sampleCount: number } | null;
  season?: string;
  state?: string;
  yearInTrainingRange?: boolean;
  caveats?: string[];
}

export async function getYieldOutlook(plantingId: string): Promise<YieldOutlook> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const r = await apiFetch<any>(`/api/v1/ml/plantings/${encodeURIComponent(plantingId)}/yield-outlook`);
  if (!r.available) return { available: false, reason: r.reason, caveats: r.caveats ?? [] };
  return {
    available: true,
    position: r.position,
    scope: r.comparison_scope
      ? {
          scope: r.comparison_scope.scope,
          state: r.comparison_scope.state,
          season: r.comparison_scope.season,
          sampleCount: r.comparison_scope.sample_count,
        }
      : null,
    season: r.season,
    state: r.state,
    yearInTrainingRange: r.year_in_training_range,
    caveats: r.caveats ?? [],
  };
}

// --- disease lookup -------------------------------------------------------------

export interface Remedies {
  en?: string | null;
  hi?: string | null;
  mr?: string | null;
  hindiIsEnglishFallback: boolean;
}

export interface DiseaseMatch {
  disease: string;
  diseaseType: string | null;
  cause: string | null;
  affectedPlantPart: string | null;
  confidenceLabel: ConfidenceLabel;
  sharedSymptom: boolean;
  alsoSeenIn: { crop: string; disease: string }[];
  remedies: Remedies;
}

export interface DiseaseSearchResult {
  matches: DiseaseMatch[];
  reason: string | null;
}

export async function searchDiseases(plantingId: string, q: string): Promise<DiseaseSearchResult> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const r = await apiFetch<any>(
    `/api/v1/ml/plantings/${encodeURIComponent(plantingId)}/diseases?q=${encodeURIComponent(q)}`
  );
  return {
    reason: r.reason ?? null,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    matches: (r.matches ?? []).map((m: any) => ({
      disease: m.disease,
      diseaseType: m.disease_type ?? null,
      cause: m.cause ?? null,
      affectedPlantPart: m.affected_plant_part ?? null,
      confidenceLabel: m.confidence_label,
      sharedSymptom: Boolean(m.shared_symptom),
      alsoSeenIn: m.also_seen_in ?? [],
      remedies: { ...(m.remedies ?? {}), hindiIsEnglishFallback: Boolean(m.hindi_is_english_fallback) },
    })),
  };
}

export interface DiseaseListItem {
  disease: string;
  diseaseType: string | null;
  affectedPlantParts: string[];
}

export async function listDiseases(plantingId: string): Promise<{ diseases: DiseaseListItem[]; reason: string | null }> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const r = await apiFetch<any>(`/api/v1/ml/plantings/${encodeURIComponent(plantingId)}/diseases/all`);
  return {
    reason: r.reason ?? null,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    diseases: (r.diseases ?? []).map((d: any) => ({
      disease: d.disease,
      diseaseType: d.disease_type ?? null,
      affectedPlantParts: d.affected_plant_parts ?? [],
    })),
  };
}

export interface DiseaseDetail {
  disease: string;
  diseaseType: string | null;
  cause: string | null;
  affectedPlantParts: string[];
  remedies: Remedies[];
  reason: string | null;
}

export async function getDiseaseDetail(plantingId: string, disease: string): Promise<DiseaseDetail> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const r = await apiFetch<any>(
    `/api/v1/ml/plantings/${encodeURIComponent(plantingId)}/diseases/detail?disease=${encodeURIComponent(disease)}`
  );
  return {
    disease: r.disease ?? disease,
    diseaseType: r.disease_type ?? null,
    cause: r.cause ?? null,
    affectedPlantParts: r.affected_plant_parts ?? [],
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    remedies: (r.remedies ?? []).map((x: any) => ({
      en: x.en,
      hi: x.hi,
      mr: x.mr,
      hindiIsEnglishFallback: Boolean(x.hindi_is_english_fallback),
    })),
    reason: r.reason ?? null,
  };
}

/** Remedy text for the app language: Hindi only when a genuine Hindi text
 * exists (50 corpus rows hold English in the Hindi column); English otherwise.
 * The corpus has no other app language. */
export function remedyFor(remedies: Remedies, language: string): { text: string; shownInEnglish: boolean } {
  if (language === "hi" && remedies.hi && !remedies.hindiIsEnglishFallback) {
    return { text: remedies.hi, shownInEnglish: false };
  }
  return { text: remedies.en ?? "", shownInEnglish: language !== "en" };
}

// --- market ----------------------------------------------------------------------

export interface MarketCommodity {
  commodity: string;
  appCrop: string | null;
  /** Crop key of this produce, comparable with Crop.mlKey (bajra -> "pearl millet"). */
  cropKey: string | null;
  forecastShipped: boolean;
}

export interface MarketCommodities {
  available: boolean;
  reason?: string;
  district: string | null;
  ownCropKeys: string[];
  commodities: MarketCommodity[];
}

export async function getMarketCommodities(): Promise<MarketCommodities> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const r = await apiFetch<any>("/api/v1/ml/market/commodities");
  return {
    available: Boolean(r.available),
    reason: r.reason,
    district: r.district ?? null,
    ownCropKeys: r.own_crop_keys ?? [],
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    commodities: (r.commodities ?? []).map((c: any) => ({
      commodity: c.commodity,
      appCrop: c.app_crop ?? null,
      cropKey: c.crop_key ?? c.app_crop ?? null,
      forecastShipped: Boolean(c.forecast_shipped),
    })),
  };
}

export interface MonthRange {
  month: number;
  median: number;
  p25: number;
  p75: number;
}

export interface PriceForecast {
  originWeek: string;
  targetWeek: string;
  currentPrice: number;
  expectedPrice: number;
  range: [number, number];
  direction: "up" | "down" | "flat";
  confidenceLabel: ConfidenceLabel;
}

export interface MarketOutlook {
  available: boolean;
  reason?: string;
  commodity: string;
  level: "district" | "state" | null;
  district: string | null;
  unit: string;
  months: MonthRange[];
  forecast: PriceForecast | null;
  forecastReason: string | null;
  caveats: string[];
}

export async function getMarketOutlook(commodity: string): Promise<MarketOutlook> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const r = await apiFetch<any>(`/api/v1/ml/market/outlook?commodity=${encodeURIComponent(commodity)}`);
  const empty = { commodity, level: null, district: null, unit: "", months: [], forecast: null, forecastReason: null, caveats: [] };
  if (!r.available) return { ...empty, available: false, reason: r.reason };
  if (r.reason) return { ...empty, available: false, reason: r.reason };
  const f = r.forecast;
  return {
    available: true,
    commodity: r.commodity,
    level: r.level,
    district: r.district ?? null,
    unit: r.unit,
    months: Object.entries(r.seasonal_outlook ?? {})
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      .map(([m, v]: [string, any]) => ({ month: Number(m), median: v.median, p25: v.p25, p75: v.p75 }))
      .sort((a, b) => a.month - b.month),
    forecast: f
      ? {
          originWeek: f.origin_week,
          targetWeek: f.target_week,
          currentPrice: f.current_price,
          expectedPrice: f.expected_price,
          range: f.range,
          direction: f.direction,
          confidenceLabel: f.confidence_label,
        }
      : null,
    forecastReason: r.forecast_reason ?? null,
    caveats: r.caveats ?? [],
  };
}

// --- photo history -----------------------------------------------------------------

export interface InferenceRecord {
  id: string;
  model: string;
  cropKey: string | null;
  plantingId: string | null;
  outcome: "ok" | "refused" | "error";
  hasImage: boolean;
  createdAt: string;
}

export async function listInferences(): Promise<InferenceRecord[]> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const r = await apiFetch<{ items: any[] }>("/api/v1/ml/inferences");
  return r.items.map((i) => ({
    id: i.id,
    model: i.model,
    cropKey: i.crop_key,
    plantingId: i.planting_id,
    outcome: i.outcome,
    hasImage: Boolean(i.has_image),
    createdAt: i.created_at,
  }));
}

export async function deleteInference(id: string): Promise<void> {
  await apiFetch<void>(`/api/v1/ml/inferences/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export function inferenceImagePath(id: string): string {
  return `/api/v1/ml/inferences/${encodeURIComponent(id)}/image`;
}

/** One translated line for a failed model call. */
export function mlErrorMessage(err: unknown, t: (key: string) => string): string {
  const reason = apiErrorReason(err);
  if (reason === "ml_unavailable") return t("ml.unavailable");
  if (reason === "model_did_not_ship" || reason === "no_model_for_crop" || reason === "crop_not_modelled") {
    return t("ml.notForThisCrop");
  }
  if (reason === "image_too_large" || reason === "invalid_image" || reason === "invalid_upload") {
    return t("ml.badPhoto");
  }
  return t("ml.checkFailed");
}
