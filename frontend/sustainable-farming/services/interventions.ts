import { apiFetch } from "../lib/apiClient";
import { type BackendIntervention, interventionFromBackend } from "../lib/syncMapping";
import { getState, setState } from "../store/appStore";
import type { Intervention, InterventionType } from "../types/models";

/**
 * Interventions (backend/src/routes/interventions.js). Same online-only
 * pattern as services/fields.ts.
 */

export async function fetchAndCacheInterventions(): Promise<void> {
  if (!getState().isAuthenticated) return;
  try {
    const res = await apiFetch<{ items: BackendIntervention[] }>(
      "/api/v1/interventions"
    );
    setState({ interventions: res.items.map(interventionFromBackend) });
  } catch {
    // Silent — cached copy stays as-is until the next trigger.
  }
}

export async function getInterventionsByPlanting(
  plantingId: string
): Promise<Intervention[]> {
  return getState()
    .interventions.filter((i) => i.plantingId === plantingId)
    .sort((a, b) => b.date.localeCompare(a.date));
}

export interface AddInterventionInput {
  plantingId: string;
  type: InterventionType;
  date: string;
  productId?: string;
  quantityMetric?: number;
  quantityUnit?: string;
  costInInr: number;
  notes?: string;
}

/** POST /api/v1/interventions. Throws on failure — see services/fields.ts. */
export async function addIntervention(
  input: AddInterventionInput
): Promise<Intervention> {
  const row = await apiFetch<BackendIntervention>("/api/v1/interventions", {
    method: "POST",
    body: {
      planting_id: input.plantingId,
      type: input.type,
      product_id: input.productId ?? null,
      quantity_metric: input.quantityMetric ?? null,
      quantity_unit: input.quantityUnit ?? null,
      cost_in_inr: input.costInInr,
      intervention_date: input.date,
      notes: input.notes ?? null,
    },
  });
  const intervention = interventionFromBackend(row);
  setState({ interventions: [...getState().interventions, intervention] });
  return intervention;
}
