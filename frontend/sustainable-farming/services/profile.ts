import { getState, setState } from "../store/appStore";
import type { LandUnit, LanguageCode } from "../types/models";

export async function updateLanguage(languagePref: LanguageCode) {
  setState({ user: { ...getState().user, languagePref } });
}

export async function updateUnitPreference(defaultUnit: LandUnit) {
  setState({ user: { ...getState().user, defaultUnit } });
}
