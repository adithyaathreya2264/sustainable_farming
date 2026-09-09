import type { LandUnit, LanguageCode } from "../types/models";
import { updateProfile } from "./users";

/**
 * Profile-screen preference edits. `updateProfile` writes local state
 * immediately and best-effort PATCHes /api/v1/users/me — see services/users.ts.
 */

export async function updateLanguage(languagePref: LanguageCode) {
  await updateProfile({ languagePref });
}

export async function updateUnitPreference(defaultUnit: LandUnit) {
  await updateProfile({ defaultUnit });
}
