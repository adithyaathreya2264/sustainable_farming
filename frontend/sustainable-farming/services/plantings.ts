import { getState, setState } from "../store/appStore";
import type { Planting } from "../types/models";

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

export async function addPlanting(input: AddPlantingInput): Promise<Planting> {
  const planting: Planting = {
    id: `pl${Date.now()}`,
    status: "active",
    isSynced: false,
    ...input,
  };
  setState({ plantings: [...getState().plantings, planting] });
  return planting;
}
