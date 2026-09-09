import { getState, setState } from "../store/appStore";
import type { Intervention, InterventionType } from "../types/models";

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

export async function addIntervention(
  input: AddInterventionInput
): Promise<Intervention> {
  const intervention: Intervention = {
    id: `i${Date.now()}`,
    isSynced: false,
    ...input,
  };
  setState({ interventions: [...getState().interventions, intervention] });

  // Real sync now flips isSynced — see services/sync-manager.ts, triggered
  // by hooks/useSyncTriggers.ts (connectivity, foreground, periodic fallback).

  return intervention;
}
