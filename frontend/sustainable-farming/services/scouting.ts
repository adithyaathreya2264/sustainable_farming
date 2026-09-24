import { apiFetch } from "../lib/apiClient";
import {
  type BackendScoutingObservation,
  scoutingObservationFromBackend,
} from "../lib/syncMapping";
import { getState, setState } from "../store/appStore";
import type { ScoutingObservation } from "../types/models";

/**
 * Field-scouting observations (backend/src/routes/scoutingObservations.js) —
 * a farmer-entered pest/disease count that feeds the backend rule engine.
 * Same online-only pattern as services/fields.ts.
 */

export async function fetchAndCacheScoutingObservations(): Promise<void> {
  if (!getState().isAuthenticated) return;
  try {
    const res = await apiFetch<{ items: BackendScoutingObservation[] }>(
      "/api/v1/scouting-observations"
    );
    setState({
      scoutingObservations: res.items.map(scoutingObservationFromBackend),
    });
  } catch {
    // Silent — cached copy stays as-is until the next trigger.
  }
}

export async function getScoutingObservationsByPlanting(
  plantingId: string
): Promise<ScoutingObservation[]> {
  return getState()
    .scoutingObservations.filter((o) => o.plantingId === plantingId)
    .sort((a, b) => b.observedAt.localeCompare(a.observedAt));
}

export interface AddScoutingObservationInput {
  plantingId: string;
  metricKey: string;
  metricValue: number;
  observedAt: string;
  notes?: string;
}

/**
 * POST /api/v1/scouting-observations. Throws on failure — see
 * services/fields.ts.
 */
export async function addScoutingObservation(
  input: AddScoutingObservationInput
): Promise<ScoutingObservation> {
  const row = await apiFetch<BackendScoutingObservation>(
    "/api/v1/scouting-observations",
    {
      method: "POST",
      body: {
        planting_id: input.plantingId,
        metric_key: input.metricKey,
        metric_value: input.metricValue,
        observed_at: input.observedAt,
        notes: input.notes ?? null,
      },
    }
  );
  const observation = scoutingObservationFromBackend(row);
  setState({
    scoutingObservations: [...getState().scoutingObservations, observation],
  });
  return observation;
}
