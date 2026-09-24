import { apiFetch } from "../lib/apiClient";
import type { ConfidenceLabel } from "../types/models";

/**
 * Crop-suitability guidance for a field, GET /api/v1/plantings/recommend-crop
 * (backend/src/routes/plantings.js -> services/mlClient.js -> the ML sidecar,
 * ml/serving/ -> ml/algorithms/crop_recommendation.py).
 * `basis` says what drove it: the field's latest soil test (N/P/K model), else
 * its soil type (crop-from-soil-type model), else generic midpoints - always
 * with current weather for the farmer's state/district. Never blocks planting;
 * this is guidance only, surfaced as a badge in app/modals/add-planting.tsx.
 */

export type RecommendationBasis = "soil_test" | "soil_type" | "defaults";

export interface CropRecommendationEntry {
  cropKey: string | null;
  /** The app crop this entry is, or null for crops the app doesn't offer. */
  cropId: string | null;
  displayName: string;
  isSeededCrop: boolean;
  confidenceLabel: ConfidenceLabel;
}

export interface CropRecommendationResult {
  recommended: CropRecommendationEntry;
  alternatives: CropRecommendationEntry[];
  /** App crop keys (crops.ml_key) the model that ran can never recommend —
   * its training data has no examples of them. */
  unreachableSeededCrops: string[];
  usedSoilTest: boolean;
  basis: RecommendationBasis;
}

interface BackendCropRecommendationEntry {
  crop_key: string | null;
  crop_id?: string | null;
  display_name: string;
  is_seeded_crop: boolean;
  confidence_label: ConfidenceLabel;
}

interface BackendCropRecommendationResponse {
  recommended: BackendCropRecommendationEntry;
  alternatives: BackendCropRecommendationEntry[];
  unreachable_seeded_crops: string[];
  used_soil_test: boolean;
  basis?: RecommendationBasis;
}

function fromBackendEntry(e: BackendCropRecommendationEntry): CropRecommendationEntry {
  return {
    cropKey: e.crop_key,
    cropId: e.crop_id ?? null,
    displayName: e.display_name,
    isSeededCrop: e.is_seeded_crop,
    confidenceLabel: e.confidence_label,
  };
}

export type CropFit = "top" | "alternative" | "unscored";

/** How the chosen crop sits in the recommendation, matched by app crop id and
 * ML key — never by display name, which broke on "Ragi (Finger Millet)". */
export function cropFit(
  crop: { id: string; mlKey?: string | null },
  rec: CropRecommendationResult
): CropFit | null {
  if (crop.mlKey && rec.unreachableSeededCrops.includes(crop.mlKey)) return "unscored";
  const matches = (e: CropRecommendationEntry) =>
    e.cropId === crop.id || (Boolean(crop.mlKey) && e.cropKey === crop.mlKey);
  if (matches(rec.recommended)) return "top";
  if (rec.alternatives.some(matches)) return "alternative";
  return null;
}

/** Throws on failure (offline, expired session, or the ML sidecar being
 * unavailable — 503). Callers should catch and treat this as "no
 * recommendation right now" rather than blocking the crop picker. */
export async function getCropRecommendation(fieldId: string): Promise<CropRecommendationResult> {
  const res = await apiFetch<BackendCropRecommendationResponse>(
    `/api/v1/plantings/recommend-crop?field_id=${encodeURIComponent(fieldId)}`
  );
  return {
    recommended: fromBackendEntry(res.recommended),
    alternatives: res.alternatives.map(fromBackendEntry),
    unreachableSeededCrops: res.unreachable_seeded_crops,
    usedSoilTest: res.used_soil_test,
    basis: res.basis ?? (res.used_soil_test ? "soil_test" : "defaults"),
  };
}
