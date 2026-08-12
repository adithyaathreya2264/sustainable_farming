import React, { createContext, useContext, useState } from "react";
import type { IrrigationType, LandUnit, LanguageCode } from "../types/models";

export interface OnboardingDraft {
  languagePref: LanguageCode;
  name: string;
  defaultUnit: LandUnit;
  totalArea: string;
  irrigationType: IrrigationType;
  state: string;
  district: string;
}

const initialDraft: OnboardingDraft = {
  languagePref: "en",
  name: "",
  defaultUnit: "acre",
  totalArea: "",
  irrigationType: "borewell",
  state: "",
  district: "",
};

interface OnboardingDraftContextValue {
  draft: OnboardingDraft;
  update: (patch: Partial<OnboardingDraft>) => void;
}

const OnboardingDraftContext = createContext<OnboardingDraftContextValue | undefined>(
  undefined
);

export function OnboardingDraftProvider({ children }: { children: React.ReactNode }) {
  const [draft, setDraft] = useState<OnboardingDraft>(initialDraft);

  function update(patch: Partial<OnboardingDraft>) {
    setDraft((prev) => ({ ...prev, ...patch }));
  }

  return (
    <OnboardingDraftContext.Provider value={{ draft, update }}>
      {children}
    </OnboardingDraftContext.Provider>
  );
}

export function useOnboardingDraft(): OnboardingDraftContextValue {
  const ctx = useContext(OnboardingDraftContext);
  if (!ctx) {
    throw new Error(
      "useOnboardingDraft must be used within an OnboardingDraftProvider"
    );
  }
  return ctx;
}
