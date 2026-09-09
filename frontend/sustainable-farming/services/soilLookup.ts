import { apiFetch } from "../lib/apiClient";

export type SoilLookupConfidence = "taluk" | "district" | "none";

export interface SoilLookupResult {
  soilType: string | null;
  confidence: SoilLookupConfidence;
  source: string | null;
}

interface SoilLookupResponse {
  soil_type: string | null;
  confidence: SoilLookupConfidence;
  source: string | null;
}

/**
 * Calls GET /api/v1/soil-lookup (backend/api/v1/soil.py, Task 3.1). Degrades
 * gracefully server-side — always resolves, never throws for "no data";
 * `confidence: "none"` means no suggestion, the farmer picks manually. A
 * thrown error here means the *request itself* failed (offline, expired
 * session, server error) — callers should treat that differently from
 * `confidence: "none"` (see app/modals/add-field.tsx for the pattern: blank
 * silently on "none", a small "couldn't fetch a suggestion" hint on a
 * caught error) rather than collapsing both into one silent catch.
 *
 * `taluk` isn't collected anywhere in onboarding yet (state/district only —
 * see (onboarding)/step-4.tsx), so callers today will only ever see
 * "district" or "none" confidence in practice. The backend already supports
 * taluk-level lookups for whenever that's collected.
 */
export async function lookupSoilType(
  state: string,
  district: string,
  taluk?: string
): Promise<SoilLookupResult> {
  const params = new URLSearchParams({ state, district });
  if (taluk) params.set("taluk", taluk);

  const res = await apiFetch<SoilLookupResponse>(
    `/api/v1/soil-lookup?${params.toString()}`
  );

  return {
    soilType: res.soil_type,
    confidence: res.confidence,
    source: res.source,
  };
}
