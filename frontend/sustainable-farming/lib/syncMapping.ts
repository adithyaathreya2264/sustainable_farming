import type {
  Coordinates,
  Field,
  Intervention,
  Planting,
  ScoutingObservation,
} from "../types/models";

/**
 * Field-name mapping from the real backend's snake_case columns
 * (verified against backend/models/field.py, planting.py, intervention.py)
 * to the frontend's camelCase models. Pure renaming, no unit/shape
 * conversion — `boundary` is already `{lat, long}[]` on both sides.
 */

export interface BackendField {
  id: string;
  user_id: string;
  name: string;
  area_size_hectares: number;
  lat: number;
  long: number;
  boundary: Coordinates[];
  soil_type: string | null;
}

export function fieldFromBackend(row: BackendField): Field {
  return {
    id: row.id,
    userId: row.user_id,
    name: row.name,
    areaHectares: row.area_size_hectares,
    lat: row.lat,
    long: row.long,
    boundary: row.boundary,
    soilType: row.soil_type ?? "",
  };
}

export interface BackendPlanting {
  id: string;
  field_id: string;
  crop_id: string;
  variety_id: string | null;
  sowing_date: string;
  status: Planting["status"];
}

export function plantingFromBackend(row: BackendPlanting): Planting {
  return {
    id: row.id,
    fieldId: row.field_id,
    cropId: row.crop_id,
    varietyId: row.variety_id ?? "",
    sowingDate: row.sowing_date,
    status: row.status,
  };
}

export interface BackendIntervention {
  id: string;
  planting_id: string;
  type: Intervention["type"];
  product_id: string | null;
  quantity_metric: number | null;
  quantity_unit: string | null;
  cost_in_inr: number;
  intervention_date: string;
  notes: string | null;
}

export function interventionFromBackend(row: BackendIntervention): Intervention {
  return {
    id: row.id,
    plantingId: row.planting_id,
    type: row.type,
    date: row.intervention_date,
    productId: row.product_id ?? undefined,
    quantityMetric: row.quantity_metric ?? undefined,
    quantityUnit: row.quantity_unit ?? undefined,
    costInInr: row.cost_in_inr,
    notes: row.notes ?? undefined,
  };
}

export interface BackendScoutingObservation {
  id: string;
  planting_id: string;
  metric_key: string;
  metric_value: number;
  observed_at: string;
  notes: string | null;
}

export function scoutingObservationFromBackend(
  row: BackendScoutingObservation
): ScoutingObservation {
  return {
    id: row.id,
    plantingId: row.planting_id,
    metricKey: row.metric_key,
    metricValue: Number(row.metric_value),
    observedAt: row.observed_at,
    notes: row.notes ?? undefined,
  };
}
