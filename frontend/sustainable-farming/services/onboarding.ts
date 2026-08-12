import { getState, setState } from "../store/appStore";
import type { IrrigationType, LandUnit, LanguageCode } from "../types/models";
import { toHectares } from "../utils/unitConversion";

export interface OnboardingInput {
  languagePref: LanguageCode;
  name: string;
  defaultUnit: LandUnit;
  totalArea: number; // in defaultUnit, converted to hectares on save
  irrigationType: IrrigationType;
  state: string;
  district: string;
}

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
}
