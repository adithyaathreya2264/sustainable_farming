import { apiFetch } from "../lib/apiClient";
import { type BackendField, fieldFromBackend } from "../lib/syncMapping";
import { getState, setState } from "../store/appStore";
import type { Coordinates, Field } from "../types/models";

/**
 * Farmer-owned fields (backend/src/routes/fields.js). Online-only, no local
 * dirty-row queue — `fetchAndCacheFields` refetches the list on the same
 * triggers as catalog/alerts/weather (hooks/useRefreshTriggers.ts); `addField`
 * POSTs immediately and only lands in the store once the server confirms it.
 */

export async function fetchAndCacheFields(): Promise<void> {
  if (!getState().isAuthenticated) return;
  try {
    const res = await apiFetch<{ items: BackendField[] }>("/api/v1/fields");
    setState({ fields: res.items.map(fieldFromBackend) });
  } catch {
    // Silent — cached copy (possibly empty) stays as-is until the next trigger.
  }
}

export async function getFields(): Promise<Field[]> {
  return getState().fields;
}

export async function getFieldById(id: string): Promise<Field | undefined> {
  return getState().fields.find((f) => f.id === id);
}

export interface SoilTestInput {
  nitrogen: number | null;
  phosphorus: number | null;
  potassium: number | null;
  ph: number | null;
}

export interface AddFieldInput {
  name: string;
  areaHectares: number;
  boundary: Coordinates[];
  soilType: string;
  /** Optional farmer-entered soil test values, feeds the crop-recommendation
   * endpoint (services/cropRecommendation.ts). Omitted when the farmer has
   * no recent soil test — the backend substitutes generic defaults. */
  soilTest?: SoilTestInput;
}

function centroid(points: Coordinates[]): Coordinates {
  const sum = points.reduce(
    (acc, p) => ({ lat: acc.lat + p.lat, long: acc.long + p.long }),
    { lat: 0, long: 0 }
  );
  return { lat: sum.lat / points.length, long: sum.long / points.length };
}

/**
 * POST /api/v1/fields. Throws on failure (offline, validation, expired
 * session) — callers (app/modals/add-field.tsx) surface the error rather than
 * silently dropping a farmer-entered field.
 */
export async function addField(input: AddFieldInput): Promise<Field> {
  const { lat, long } = centroid(input.boundary);
  const row = await apiFetch<BackendField>("/api/v1/fields", {
    method: "POST",
    body: {
      name: input.name,
      area_size_hectares: input.areaHectares,
      lat,
      long,
      boundary: input.boundary,
      soil_type: input.soilType || null,
      soil_test: input.soilTest
        ? {
            nitrogen: input.soilTest.nitrogen,
            phosphorus: input.soilTest.phosphorus,
            potassium: input.soilTest.potassium,
            ph: input.soilTest.ph,
          }
        : null,
    },
  });
  const field = fieldFromBackend(row);
  setState({ fields: [...getState().fields, field] });
  return field;
}

/**
 * DELETE /api/v1/fields/:id (soft delete server-side). Throws on failure —
 * callers (app/(tabs)/fields.tsx) surface the error rather than silently
 * leaving a field the farmer thinks is gone. Callers are expected to block
 * this for a field that still has plantings, since the backend doesn't
 * cascade-delete those and a planting pointing at a hidden field is
 * confusing rather than actually removed.
 */
export async function deleteField(id: string): Promise<void> {
  await apiFetch<void>(`/api/v1/fields/${encodeURIComponent(id)}`, { method: "DELETE" });
  setState({ fields: getState().fields.filter((f) => f.id !== id) });
}
