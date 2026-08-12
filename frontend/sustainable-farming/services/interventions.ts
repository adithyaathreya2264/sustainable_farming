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

  // Simulate the offline-first sync: after a short delay, mark as synced
  // ("Data synced to cloud." toast per the wireframe spec's optimistic UI).
  setTimeout(() => {
    setState({
      interventions: getState().interventions.map((i) =>
        i.id === intervention.id ? { ...i, isSynced: true } : i
      ),
    });
  }, 1500);

  return intervention;
}
