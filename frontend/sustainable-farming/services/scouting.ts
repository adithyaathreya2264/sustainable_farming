import { getState, setState } from "../store/appStore";
import type { ScoutingObservation } from "../types/models";

/**
 * Field-scouting observations — a farmer-entered pest/disease count that feeds
 * the backend rule engine. Local-first + synced, exactly like
 * services/interventions.ts: `add*` writes the store with `isSynced: false`,
 * services/sync-manager.ts pushes it and flips the flag.
 */

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

export async function addScoutingObservation(
  input: AddScoutingObservationInput
): Promise<ScoutingObservation> {
  const observation: ScoutingObservation = {
    id: `so${Date.now()}`,
    isSynced: false,
    ...input,
  };
  setState({
    scoutingObservations: [...getState().scoutingObservations, observation],
  });
  return observation;
}
