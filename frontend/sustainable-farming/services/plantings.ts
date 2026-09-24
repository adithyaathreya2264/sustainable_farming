import { apiFetch } from "../lib/apiClient";
import { type BackendPlanting, plantingFromBackend } from "../lib/syncMapping";
import { getState, setState } from "../store/appStore";
import type { Planting } from "../types/models";

/**
 * Plantings (backend/src/routes/plantings.js). Same online-only pattern as
 * services/fields.ts.
 */

export async function fetchAndCachePlantings(): Promise<void> {
  if (!getState().isAuthenticated) return;
  try {
    const res = await apiFetch<{ items: BackendPlanting[] }>("/api/v1/plantings");
    setState({ plantings: res.items.map(plantingFromBackend) });
  } catch {
    // Silent — cached copy stays as-is until the next trigger.
  }
}

export async function getPlantings(): Promise<Planting[]> {
  return getState().plantings;
}

export async function getPlantingById(id: string): Promise<Planting | undefined> {
  return getState().plantings.find((p) => p.id === id);
}

export async function getPlantingsByField(fieldId: string): Promise<Planting[]> {
  return getState().plantings.filter((p) => p.fieldId === fieldId);
}

export interface AddPlantingInput {
  fieldId: string;
  cropId: string;
  varietyId: string;
  sowingDate: string;
}

/** POST /api/v1/plantings. Throws on failure — see services/fields.ts. */
export async function addPlanting(input: AddPlantingInput): Promise<Planting> {
  const row = await apiFetch<BackendPlanting>("/api/v1/plantings", {
    method: "POST",
    body: {
      field_id: input.fieldId,
      crop_id: input.cropId,
      variety_id: input.varietyId || null,
      sowing_date: input.sowingDate,
      status: "active",
    },
  });
  const planting = plantingFromBackend(row);
  setState({ plantings: [...getState().plantings, planting] });
  return planting;
}
