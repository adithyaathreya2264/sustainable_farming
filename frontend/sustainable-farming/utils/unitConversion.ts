import type { LandUnit } from "../types/models";

/**
 * Conversion factors to hectares (the canonical storage unit per the
 * Technical Design doc's FR5 — UI shows local units, DB stores metric).
 * Bigha varies significantly by state in real revenue records; this uses
 * the commonly cited North Indian standard (1 Bigha ≈ 0.1618 ha) as a
 * reasonable default pending a per-state lookup table.
 */
const HECTARE_FACTORS: Record<LandUnit, number> = {
  hectare: 1,
  acre: 0.404686,
  guntha: 0.0101171, // 1 Acre = 40 Guntha
  bigha: 0.1618,
  cent: 0.00404686, // 1 Cent = 1/100 Acre
  killa: 0.404686, // Killa is regionally equivalent to 1 Acre
};

export const LAND_UNITS: LandUnit[] = [
  "acre",
  "hectare",
  "guntha",
  "bigha",
  "cent",
  "killa",
];

export function toHectares(value: number, unit: LandUnit): number {
  return value * HECTARE_FACTORS[unit];
}

export function fromHectares(hectares: number, unit: LandUnit): number {
  return hectares / HECTARE_FACTORS[unit];
}

export function convert(value: number, from: LandUnit, to: LandUnit): number {
  return fromHectares(toHectares(value, from), to);
}

export function formatArea(hectares: number, unit: LandUnit): string {
  const value = fromHectares(hectares, unit);
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
    bigha: "Bigha",
    cent: "Cent",
    killa: "Killa",
  };
  return labels[unit];
}
