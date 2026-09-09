import type { Crop } from "../types/models";

/**
 * The field-scouting metrics a farmer can log, one per (crop, growth stage).
 * `metricKey` MUST match the backend `AgronomicRule.condition_field` string
 * exactly — that's the join the rule engine uses. Currently 4 rules
 * (backend/scripts/seed_reference_data.py):
 *   - RICE_STEM_BORER_SCOUT       Rice   / Vegetative (Tillering)
 *   - COTTON_PBW_ETL              Cotton / Boll Development
 *   - SUGARCANE_EARLY_SHOOT_BORER Sugarcane / Germination-Tillering (0-120 DAS)
 *   - MAIZE_FAW_ETL               Maize  / Early Whorl (V2-V6)
 */
export interface ScoutingMetric {
  cropName: string;
  stageName: string;
  metricKey: string;
  /** i18n key under `scouting.metrics.*` for the farmer-facing label. */
  labelKey: string;
  unit: string;
}

export const SCOUTING_METRICS: ScoutingMetric[] = [
  {
    cropName: "Rice",
    stageName: "Vegetative (Tillering)",
    metricKey: "dead_hearts_percent",
    labelKey: "scouting.metrics.dead_hearts_percent",
    unit: "%",
  },
  {
    cropName: "Cotton",
    stageName: "Boll Development",
    metricKey: "pheromone_trap_moths_per_night_3day_avg",
    labelKey: "scouting.metrics.pheromone_trap_moths_per_night_3day_avg",
    unit: "moths/night",
  },
  {
    cropName: "Sugarcane",
    stageName: "Germination-Tillering (0-120 DAS)",
    metricKey: "deadheart_percent",
    labelKey: "scouting.metrics.deadheart_percent",
    unit: "%",
  },
  {
    cropName: "Maize",
    stageName: "Early Whorl (V2-V6)",
    metricKey: "percent_plants_with_whorl_damage",
    labelKey: "scouting.metrics.percent_plants_with_whorl_damage",
    unit: "%",
  },
];

/** Days between an ISO date and today (UTC-ish, local midnight is fine here). */
function daysSince(isoDate: string): number {
  const then = new Date(isoDate + "T00:00:00").getTime();
  const now = Date.now();
  return Math.floor((now - then) / 86_400_000);
}

/** The crop's current growth-stage name from its sowing date, or null. */
export function currentStage(crop: Crop | undefined, sowingDate: string): string | null {
  if (!crop || crop.growthStages.length === 0) return null;
  const d = daysSince(sowingDate);
  for (const s of crop.growthStages) {
    if (d >= s.startDay && d < s.endDay) return s.stageName;
  }
  return null;
}

/**
 * The one scouting metric relevant to a planting right now — its crop has a
 * scouting rule AND the planting is currently in that rule's stage. Otherwise
 * undefined (the modal shows "nothing to scout right now").
 */
export function metricForPlanting(
  crop: Crop | undefined,
  sowingDate: string
): ScoutingMetric | undefined {
  const stage = currentStage(crop, sowingDate);
  if (!crop || !stage) return undefined;
  return SCOUTING_METRICS.find(
    (m) => m.cropName === crop.name && m.stageName === stage
  );
}
