import type {
  LandUnit,
  NonStandardizedLandUnit,
  StandardizedLandUnit,
} from "../types/models";

/**
 * Conversion factors to hectares (the canonical storage unit per the
 * Technical Design doc's FR5 — UI shows local units, DB stores metric).
 *
 * Canonical source: docs/unit-conversions.md + docs/unit-conversions.json
 * (Task 2.6). These constants must be kept in sync with that JSON by hand —
 * Metro doesn't resolve imports outside the Expo app root, so there's no
 * build-time link between them.
 *
 * Standardized units below are exact, government-definable constants — safe
 * to hard-code. Non-standardized units vary by state and are UNVERIFIED
 * (sourced from real-estate aggregator sites, not official state revenue
 * records — see docs/unit-conversions.md's verification-status table).
 */
const STANDARDIZED_FACTORS: Record<StandardizedLandUnit, number> = {
  hectare: 1,
  acre: 0.40468564224, // 4046.8564224 m², exact
  guntha: 0.01011714106, // 1 Acre / 40 — verified against Karnataka Land Revenue Act convention
  cent: 0.0040468564224, // 1 Acre / 100, exact
  ground: 0.0222967296, // 2,400 sq ft exactly (Tamil Nadu)
  sqft: 0.0000092903, // 1 international sq ft, exact
  sqyard: 0.0000836127, // 1 sq yard (Gaj) = 9 sq ft, exact
  killa: 0.40468564224, // colloquial Punjab/Haryana term, exactly 1 Acre
};

/**
 * State -> sqm, per non-standardized unit. UNVERIFIED — see
 * docs/unit-conversions.md. Only offer these units in UI where `state` is
 * already known (never during onboarding step 3, which collects area before
 * state) — resolving to "no factor" for an unknown state is deliberate, not
 * a gap: better to omit an ambiguous unit than silently guess.
 */
const NON_STANDARDIZED_SQM_BY_STATE: Record<
  NonStandardizedLandUnit,
  Record<string, number>
> = {
  bigha: {
    "Uttar Pradesh": 2509.051,
    "West Bengal": 1335.4626,
    Punjab: 841.7461,
    Bihar: 2529.2447,
    Assam: 1337.7998,
    "Himachal Pradesh": 809.2,
  },
  katha: {
    "Uttar Pradesh": 126.4923,
    "West Bengal": 66.7731,
    Bihar: 126.4595,
    Assam: 267.6008,
    Jharkhand: 66.89,
  },
  biswa: {
    "Uttar Pradesh": 125.4191,
    "Himachal Pradesh": 40.46,
  },
  kanal: {
    Punjab: 505.8071,
    Haryana: 505.8071,
    "Himachal Pradesh": 384.0,
  },
  marla: {
    Punjab: 25.2904,
    Haryana: 25.2904,
    "Himachal Pradesh": 19.2,
  },
};

export function isStandardizedUnit(unit: LandUnit): unit is StandardizedLandUnit {
  return unit in STANDARDIZED_FACTORS;
}

/** Units always safe to offer, regardless of whether the farmer's state is known. */
export const STANDARDIZED_LAND_UNITS: StandardizedLandUnit[] = [
  "acre",
  "hectare",
  "guntha",
  "cent",
  "ground",
  "sqft",
  "sqyard",
  "killa",
];

/** Full set, for pickers shown where `state` is already resolvable (e.g. add-field, profile). */
export const LAND_UNITS: LandUnit[] = [
  ...STANDARDIZED_LAND_UNITS,
  "bigha",
  "katha",
  "biswa",
  "kanal",
  "marla",
];

/**
 * Units available given a (possibly unknown) state — non-standardized units
 * are only included once `state` resolves to an entry in this app's own
 * states list AND that unit has data for it.
 */
export function availableLandUnits(state: string | undefined): LandUnit[] {
  if (!state) return STANDARDIZED_LAND_UNITS;
  const nonStandardized = (
    Object.keys(NON_STANDARDIZED_SQM_BY_STATE) as NonStandardizedLandUnit[]
  ).filter((unit) => state in NON_STANDARDIZED_SQM_BY_STATE[unit]);
  return [...STANDARDIZED_LAND_UNITS, ...nonStandardized];
}

function hectareFactor(unit: LandUnit, state: string | undefined): number {
  if (isStandardizedUnit(unit)) return STANDARDIZED_FACTORS[unit];
  const byState = NON_STANDARDIZED_SQM_BY_STATE[unit];
  const sqm = state ? byState[state] : undefined;
  if (sqm === undefined) {
    throw new Error(
      `No conversion factor for "${unit}"${state ? ` in "${state}"` : ""} — ` +
        "non-standardized units require a known state (see docs/unit-conversions.md)."
    );
  }
  return sqm / 10000;
}

export function toHectares(
  value: number,
  unit: LandUnit,
  state?: string
): number {
  return value * hectareFactor(unit, state);
}

export function fromHectares(
  hectares: number,
  unit: LandUnit,
  state?: string
): number {
  return hectares / hectareFactor(unit, state);
}

export function convert(
  value: number,
  from: LandUnit,
  to: LandUnit,
  state?: string
): number {
  return fromHectares(toHectares(value, from, state), to, state);
}

export function formatArea(
  hectares: number,
  unit: LandUnit,
  state?: string
): string {
  const value = fromHectares(hectares, unit, state);
  return `${roundDisplay(value)} ${unitLabel(unit)}`;
}

export function roundDisplay(value: number): number {
  return Math.round(value * 100) / 100;
}

export function unitLabel(unit: LandUnit): string {
  const labels: Record<LandUnit, string> = {
    hectare: "Hectare",
    acre: "Acre",
    guntha: "Guntha",
    cent: "Cent",
    ground: "Ground",
    sqft: "Sq. ft",
    sqyard: "Sq. yard (Gaj)",
    killa: "Killa",
    bigha: "Bigha",
    katha: "Katha",
    biswa: "Biswa",
    kanal: "Kanal",
    marla: "Marla",
  };
  return labels[unit];
}
