import { getState, setState } from "../store/appStore";
import type { IrrigationType, LandUnit, LanguageCode } from "../types/models";
import { toHectares } from "../utils/unitConversion";
import { updateProfile } from "./users";

export interface OnboardingInput {
  languagePref: LanguageCode;
  name: string;
  defaultUnit: LandUnit;
  totalArea: number; // in defaultUnit, converted to hectares on save
  irrigationType: IrrigationType;
  state: string;
  district: string;
}

/**
 * Writes the profile locally (so the flow finishes offline) and PATCHes it to
 * the backend with `onboarding_complete: true`. That flag is what
 * `POST /api/v1/internal/run-scheme-matching` filters on — without this call a
 * farmer is invisible to scheme matching.
 */
export async function completeOnboarding(input: OnboardingInput) {
  const totalAreaHectares = toHectares(input.totalArea, input.defaultUnit);
  setState({
    user: {
      ...getState().user,
      languagePref: input.languagePref,
      name: input.name,
      defaultUnit: input.defaultUnit,
      totalAreaHectares,
      irrigationType: input.irrigationType,
      state: input.state,
      district: input.district,
      onboardingComplete: true,
    },
  });

  await updateProfile({
    languagePref: input.languagePref,
    name: input.name,
    defaultUnit: input.defaultUnit,
    totalAreaHectares,
    irrigationType: input.irrigationType,
    state: input.state,
    district: input.district,
    onboardingComplete: true,
  });
}
