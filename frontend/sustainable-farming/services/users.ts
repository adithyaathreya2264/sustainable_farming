import { apiFetch } from "../lib/apiClient";
import { getState, setState } from "../store/appStore";
import type { IrrigationType, LandUnit, LanguageCode, User } from "../types/models";

/**
 * User profile round-trip (backend/api/v1/users.py). The frontend collects the
 * whole profile in onboarding and edits it on the profile screen; this is the
 * only path that persists it server-side (and, crucially, sets
 * `onboarding_complete`, which `run-scheme-matching` filters on).
 *
 * Identity is the JWT — the backend always operates on the caller's own row, so
 * there's no id in the path.
 */

interface BackendUserProfile {
  id: string;
  phone_number: string;
  unique_id: string | null;
  name: string;
  language_pref: string;
  default_unit: string;
  total_area_hectares: number;
  irrigation_type: string;
  state: string;
  district: string;
  onboarding_complete: boolean;
  photo_training_consent?: boolean;
}

export interface ProfilePatch {
  uniqueId?: string;
  name?: string;
  languagePref?: LanguageCode;
  defaultUnit?: LandUnit;
  totalAreaHectares?: number;
  irrigationType?: IrrigationType;
  state?: string;
  district?: string;
  onboardingComplete?: boolean;
  photoTrainingConsent?: boolean;
}

function userFromBackend(row: BackendUserProfile): User {
  return {
    id: row.id,
    phoneNumber: row.phone_number,
    uniqueId: row.unique_id ?? "",
    name: row.name,
    languagePref: row.language_pref as LanguageCode,
    defaultUnit: row.default_unit as LandUnit,
    totalAreaHectares: Number(row.total_area_hectares),
    irrigationType: row.irrigation_type as IrrigationType,
    state: row.state,
    district: row.district,
    onboardingComplete: row.onboarding_complete,
    photoTrainingConsent: Boolean(row.photo_training_consent),
  };
}

function patchToBackend(patch: ProfilePatch): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  if (patch.uniqueId !== undefined) out.unique_id = patch.uniqueId;
  if (patch.name !== undefined) out.name = patch.name;
  if (patch.languagePref !== undefined) out.language_pref = patch.languagePref;
  if (patch.defaultUnit !== undefined) out.default_unit = patch.defaultUnit;
  if (patch.totalAreaHectares !== undefined)
    out.total_area_hectares = patch.totalAreaHectares;
  if (patch.irrigationType !== undefined) out.irrigation_type = patch.irrigationType;
  if (patch.state !== undefined) out.state = patch.state;
  if (patch.district !== undefined) out.district = patch.district;
  if (patch.onboardingComplete !== undefined)
    out.onboarding_complete = patch.onboardingComplete;
  if (patch.photoTrainingConsent !== undefined)
    out.photo_training_consent = patch.photoTrainingConsent;
  return out;
}

/**
 * Fetches the real profile and merges it into the store. Called right after a
 * successful OTP verify so `user.id` / `user.onboardingComplete` stop being the
 * mock seed values. Returns the merged user, or null if the request failed
 * (offline / expired token) — callers fall back to local state.
 */
export async function fetchProfile(): Promise<User | null> {
  if (!getState().authToken) return null;
  try {
    const row = await apiFetch<BackendUserProfile>("/api/v1/users/me");
    const user = userFromBackend(row);
    // Keep any locally-set fields the server doesn't know yet (a fresh row has
    // empty name/state/etc.) — but always take the server's id + onboarding flag.
    const local = getState().user;
    const merged: User = {
      ...local,
      ...user,
      name: user.name || local.name,
      state: user.state || local.state,
      district: user.district || local.district,
      totalAreaHectares: user.totalAreaHectares || local.totalAreaHectares,
    };
    setState({ user: merged });
    return merged;
  } catch {
    return null;
  }
}

/**
 * PATCH /api/v1/users/me. Writes local state first (so the UI/offline flow never
 * blocks on the network), then best-effort syncs to the backend.
 */
export async function updateProfile(patch: ProfilePatch): Promise<void> {
  setState({ user: { ...getState().user, ...stripUndefined(patch) } as User });
  if (!getState().authToken) return;
  try {
    const row = await apiFetch<BackendUserProfile>("/api/v1/users/me", {
      method: "PATCH",
      body: patchToBackend(patch),
    });
    setState({ user: { ...getState().user, ...userFromBackend(row) } });
  } catch {
    // Local state already updated; the next successful updateProfile /
    // fetchProfile reconciles.
  }
}

function stripUndefined<T extends object>(obj: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(obj).filter(([, v]) => v !== undefined)
  ) as Partial<T>;
}

/**
 * PATCH /api/v1/users/me with only `unique_id`. Unlike `updateProfile`, this
 * does NOT swallow errors — the onboarding PIN step (app/(onboarding)/step-1.tsx)
 * needs to see a 409 "already exists" to show the farmer an inline error and
 * let them pick a different number, rather than silently moving on.
 */
export async function claimUniqueId(uniqueId: string): Promise<User> {
  const row = await apiFetch<BackendUserProfile>("/api/v1/users/me", {
    method: "PATCH",
    body: { unique_id: uniqueId },
  });
  const user = { ...getState().user, ...userFromBackend(row) };
  setState({ user });
  return user;
}
