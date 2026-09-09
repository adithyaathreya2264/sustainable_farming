import { apiFetch } from "../lib/apiClient";
import { getState } from "../store/appStore";
import fallbackData from "../data/locationsFallback.json";
import type { District } from "../types/models";

/**
 * State / district lists for the onboarding pickers.
 *
 * Source of truth is the backend (`GET /api/v1/locations`, MySQL `locations`
 * table). `data/locationsFallback.json` is a bundled offline fallback ONLY —
 * used before the first successful fetch and when the device is offline during
 * first-run onboarding (a rural farmer may have no connectivity yet). Once the
 * server responds, its data replaces the fallback for the rest of the session.
 */

const fallback = fallbackData as District[];
let cache: District[] = fallback;
let fetched = false;

interface BackendLocations {
  items: { state: string; districts: string[] }[];
}

/**
 * Best-effort refresh from the backend. Fired from hooks/useSyncTriggers.ts on
 * the same triggers as sync/catalog/weather, so by the time a freshly-logged-in
 * user taps through to the location step it's already server data.
 */
export async function fetchAndCacheLocations(): Promise<void> {
  if (!getState().isAuthenticated) return;
  try {
    const res = await apiFetch<BackendLocations>("/api/v1/locations");
    if (res.items?.length) {
      cache = res.items;
      fetched = true;
    }
  } catch {
    // Keep whatever we have (server data from earlier, or the bundled fallback).
  }
}

/** True once the backend list has replaced the bundled fallback this session. */
export function locationsAreLive(): boolean {
  return fetched;
}

export async function getStates(): Promise<string[]> {
  return cache.map((l) => l.state);
}

export async function getDistricts(state: string): Promise<string[]> {
  return cache.find((l) => l.state === state)?.districts ?? [];
}
