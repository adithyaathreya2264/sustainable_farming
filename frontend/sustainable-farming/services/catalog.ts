import { apiFetch } from "../lib/apiClient";
import {
  getState,
  pruneOrphanedCatalogRefs,
  setState,
} from "../store/appStore";
import type { AgriCatalogItem, Crop } from "../types/models";

/**
 * Identifies the backend catalog dataset. The current backend seeds
 * `crops` / `agri_catalog` with generated UUIDs (see
 * backend/scripts/seed_reference_data.py). Bump this string whenever the
 * backend catalog IDs change under us (re-seed with new UUIDs, a real
 * catalog source, etc.) so cached IDs and local row refs get reconciled
 * instead of silently pointing at nothing.
 */
export const CATALOG_DATASET_TAG = "seed-uuid-v1";

/**
 * Crops/varieties and agri-input reference data (backend/api/v1/catalog.py)
 * are server-owned and outside the sync protocol — plain authenticated
 * reads, cached into the store so they survive restarts and work offline
 * after the first successful fetch (see hooks/useSyncTriggers.ts, which
 * calls fetchAndCacheCatalog() on the same triggers as synchronize()).
 */

interface BackendCropVariety {
  id: string;
  name: string;
}

interface BackendGrowthStage {
  stage_name: string;
  stage_order: number;
  typical_days_from_sowing_start: number;
  typical_days_from_sowing_end: number;
}

interface BackendCrop {
  id: string;
  name: string;
  varieties: BackendCropVariety[];
  growth_stages?: BackendGrowthStage[];
}

interface BackendAgriCatalogItem {
  id: string;
  category: AgriCatalogItem["category"];
  name: string;
  unit_of_measure: string;
  crop_applicability: string[] | null;
  typical_dosage_per_hectare: number | null;
}

function cropFromBackend(row: BackendCrop): Crop {
  return {
    id: row.id,
    name: row.name,
    varieties: row.varieties,
    growthStages: (row.growth_stages ?? [])
      .slice()
      .sort((a, b) => a.stage_order - b.stage_order)
      .map((s) => ({
        stageName: s.stage_name,
        startDay: s.typical_days_from_sowing_start,
        endDay: s.typical_days_from_sowing_end,
      })),
  };
}

function agriInputFromBackend(row: BackendAgriCatalogItem): AgriCatalogItem {
  return {
    id: row.id,
    name: row.name,
    category: row.category,
    unitOfMeasure: row.unit_of_measure,
    cropApplicability: row.crop_applicability,
  };
}

/**
 * Fetches both catalogs and caches them into the store. Best-effort/silent
 * on failure (offline, not yet authenticated, etc.) — callers that need to
 * know whether real data is available should check
 * `getState().catalogFetchedAt` / the `crops`/`agriInputs` arrays directly
 * rather than awaiting this, since it's fired opportunistically from
 * connectivity/foreground triggers, not from screen mount.
 */
export async function fetchAndCacheCatalog(): Promise<void> {
  if (!getState().isAuthenticated) return;
  try {
    const [crops, agriInputs] = await Promise.all([
      apiFetch<{ items: BackendCrop[] }>("/api/v1/catalog/crops"),
      apiFetch<{ items: BackendAgriCatalogItem[] }>("/api/v1/catalog/agri-inputs"),
    ]);
    const nextCrops = crops.items.map(cropFromBackend);
    const nextInputs = agriInputs.items.map(agriInputFromBackend);

    const priorTag = getState().catalogDatasetTag;
    if (priorTag !== null && priorTag !== CATALOG_DATASET_TAG) {
      // Catalog IDs changed under us — reconcile local rows before caching.
      pruneOrphanedCatalogRefs(nextCrops, nextInputs);
    }

    setState({
      crops: nextCrops,
      agriInputs: nextInputs,
      catalogFetchedAt: Date.now(),
      catalogDatasetTag: CATALOG_DATASET_TAG,
    });
  } catch {
    // Silent — the cached copy (possibly empty, on a first-ever offline
    // launch) stays as-is until the next trigger.
  }
}

export async function getCrops(): Promise<Crop[]> {
  return getState().crops;
}

export async function getCropById(id: string): Promise<Crop | undefined> {
  return getState().crops.find((c) => c.id === id);
}

/**
 * Chemical-type interventions only — the agri_catalog table has no rows for
 * irrigation/labor/harvest at all (see AgriCatalogCategory's docstring in
 * types/models.ts). `cropName` narrows by crop_applicability when given;
 * pass undefined/null to get the full list (e.g. no planting selected yet).
 */
export async function getAgriInputsForCrop(
  cropName: string | null | undefined
): Promise<AgriCatalogItem[]> {
  const items = getState().agriInputs;
  if (!cropName) return items;
  return items.filter(
    (item) => !item.cropApplicability || item.cropApplicability.includes(cropName)
  );
}

export async function getAgriProductById(
  id: string
): Promise<AgriCatalogItem | undefined> {
  return getState().agriInputs.find((p) => p.id === id);
}
