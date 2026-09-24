/**
 * Static national soil-type taxonomy (standard ICAR/NBSS broad classes) shown
 * in the add-field soil-type picker. Not backend-sourced — there is no such
 * catalog server-side; `services/soilLookup.ts` only offers a single
 * best-guess suggestion per state/district (and today only for a handful of
 * Karnataka taluks, see backend/src/services/soilLookup.js). This list is
 * what farmers pick from/search when no suggestion applies or they want to
 * override it. "other" reveals a free-text field instead of this list.
 */
export const SOIL_TYPE_KEYS = [
  "alluvial",
  "black",
  "red",
  "laterite",
  "arid",
  "saline",
  "peaty",
  "forest",
  "other",
] as const;

export type SoilTypeKey = (typeof SOIL_TYPE_KEYS)[number];

export function isSoilTypeKey(value: string): value is SoilTypeKey {
  return (SOIL_TYPE_KEYS as readonly string[]).includes(value);
}

/**
 * Fields store the soil *key* (so the backend can map it to a model's soil
 * vocabulary regardless of the farmer's language) and translate it only for
 * display. Fields saved before 2026-09-24 hold a translated label or free
 * text; those are shown as stored.
 */
export function soilTypeDisplay(value: string, t: (key: string) => string): string {
  return isSoilTypeKey(value) && value !== "other" ? t(`addField.soilTypes.${value}`) : value;
}
