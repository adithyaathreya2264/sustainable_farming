import locationsData from "../data/mock/locations.json";
import type { District } from "../types/models";

const locations = locationsData as District[];

export async function getStates(): Promise<string[]> {
  return locations.map((l) => l.state);
}

export async function getDistricts(state: string): Promise<string[]> {
  return locations.find((l) => l.state === state)?.districts ?? [];
}
