import schemesData from "../data/mock/schemes.json";
import { getState } from "../store/appStore";
import type { Scheme } from "../types/models";

const allSchemes = schemesData as Scheme[];

/**
 * Stand-in for the backend's rules-engine scheme matcher (Technical Design
 * doc FR6): central schemes always match, state schemes match the farmer's
 * registered state. Karnataka Krishi Bhagya additionally only matches
 * rainfed/borewell farmers, mirroring the doc's irrigation-based targeting.
 */
function isEligible(scheme: Scheme, state: string, irrigationType: string): boolean {
  if (scheme.level === "central") return true;
  if (scheme.id === "s3") {
    return state === "Karnataka" && irrigationType !== "canal";
  }
  return state === "Karnataka";
}

export async function getMatchedSchemes(): Promise<Scheme[]> {
  const { user } = getState();
  if (!user.state) return [];
  return allSchemes.filter((s) => isEligible(s, user.state, user.irrigationType));
}

export async function getSchemeById(id: string): Promise<Scheme | undefined> {
  return allSchemes.find((s) => s.id === id);
}
