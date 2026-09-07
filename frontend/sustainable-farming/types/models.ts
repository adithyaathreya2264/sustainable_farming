/**
 * Data shapes mirror the MySQL entities in the Technical Design doc
 * (users, fields, plantings, interventions, agri_catalog, govt_schemes) so the
 * eventual FastAPI/WatermelonDB layer is a drop-in swap for these services.
 * All geospatial/area values are stored canonically in hectares.
 */

// Standardized units are exact constants, safe anywhere. Non-standardized
// units vary by state and require a resolvable `state` to convert — see
// docs/unit-conversions.md (Task 2.6) for sourcing/verification status.
export type StandardizedLandUnit =
  | "hectare"
  | "acre"
  | "guntha"
  | "cent"
  | "ground"
  | "sqft"
  | "sqyard"
  | "killa";
export type NonStandardizedLandUnit =
  | "bigha"
  | "katha"
  | "biswa"
  | "kanal"
  | "marla";
export type LandUnit = StandardizedLandUnit | NonStandardizedLandUnit;

export type IrrigationType = "rainfed" | "borewell" | "canal" | "drip_sprinkler";

export type LanguageCode =
  | "en"
  | "kn"
  | "hi"
  | "ta"
  | "te"
  | "ml"
  | "pa"
  | "bn"
  | "gu"
  | "mni";

export interface User {
  id: string;
  phoneNumber: string;
  name: string;
  languagePref: LanguageCode;
  defaultUnit: LandUnit;
  totalAreaHectares: number;
  irrigationType: IrrigationType;
  state: string;
  district: string;
  onboardingComplete: boolean;
}

export interface Coordinates {
  lat: number;
  long: number;
}

export interface Field {
  id: string;
  userId: string;
  name: string;
  areaHectares: number;
  lat: number; // centroid of `boundary`
  long: number;
  boundary: Coordinates[]; // polygon vertices, >= 3, in the order drawn
  soilType: string;
  isSynced: boolean;
}

export type PlantingStatus = "active" | "harvested";

export interface Planting {
  id: string;
  fieldId: string;
  cropId: string;
  varietyId: string;
  sowingDate: string; // ISO date
  status: PlantingStatus;
  isSynced: boolean;
}

/**
 * A field-scouting count a farmer records (dead hearts %, pheromone-trap moths,
 * whorl damage %, …). Synced like an intervention; feeds the backend rule
 * engine's pest/ETL rules. `metricKey` matches the backend
 * `AgronomicRule.condition_field` string exactly — see lib/scoutingMetrics.ts.
 */
export interface ScoutingObservation {
  id: string;
  plantingId: string;
  metricKey: string;
  metricValue: number;
  observedAt: string; // ISO date
  notes?: string;
  isSynced: boolean;
}

export type InterventionType = "chemical" | "irrigation" | "labor" | "harvest";

export interface Intervention {
  id: string;
  plantingId: string;
  type: InterventionType;
  date: string; // ISO date
  productId?: string;
  quantityMetric?: number;
  quantityUnit?: string;
  costInInr: number;
  notes?: string;
  isSynced: boolean;
}

// Matches backend RecommendationSeverity exactly (models/recommendation.py) —
// no frontend-invented high/medium/low vocabulary.
export type AlertSeverity = "info" | "advisory" | "critical";

export type AlertKind = "recommendation" | "scheme_match";

/**
 * "unverified" | "provisional" | "verified" — replaces the fictional
 * confidencePct. Two different backend confidence *scales* (AgronomicRule's
 * low/medium/verified data-sourcing quality; SchemeMatch's
 * verified/provisional eligibility-check completeness) collapse into this
 * one label server-side (backend/api/v1/alerts.py) — the frontend never
 * needs to know about the underlying scales, just this label.
 */
export type ConfidenceLabel = "unverified" | "provisional" | "verified";

/**
 * Unifies what were separate mock `Recommendation`/`Scheme` concepts —
 * backend/api/v1/alerts.py's GET /api/v1/alerts is the single source for
 * both kinds now. Fields not applicable to a given `kind` are null, not
 * omitted, so consumers don't need a discriminated-union type guard for
 * every read.
 */
export interface Alert {
  id: string;
  kind: AlertKind;
  severity: AlertSeverity | null; // recommendations only
  status: string;
  headline: string;
  detail: string | null; // scheme matches: benefit_description
  confidenceLabel: ConfidenceLabel;
  applicationUrl: string | null; // scheme matches only
  authority: string | null; // scheme matches only
  eligibilitySummary: string[] | null; // scheme matches only
  generatedAt: string;
  plantingId: string | null; // recommendations only
}

/**
 * Live weather for the dashboard widget — GET /api/v1/weather
 * (backend/api/v1/weather.py). The backend geocodes the farmer's
 * state/district and pulls current conditions + a short forecast from
 * Open-Meteo. `available` is false when no location is set or the provider
 * was unreachable; the widget shows an "unavailable" state then.
 */
export type WeatherConditionGroup =
  | "clear"
  | "mostly_clear"
  | "partly_cloudy"
  | "cloudy"
  | "fog"
  | "drizzle"
  | "rain"
  | "rain_showers"
  | "snow"
  | "thunderstorm"
  | "unknown";

export interface WeatherForecastDay {
  date: string;
  tempMaxC: number | null;
  tempMinC: number | null;
  precipitationMm: number | null;
  conditionGroup: WeatherConditionGroup;
  conditionLabel: string;
}

export interface WeatherSnapshot {
  available: boolean;
  locationLabel: string | null;
  temperatureC: number | null;
  feelsLikeC: number | null;
  humidityPct: number | null;
  precipitationMm: number | null;
  windKph: number | null;
  conditionGroup: WeatherConditionGroup | null;
  conditionLabel: string | null;
  observedAt: string | null;
  forecast: WeatherForecastDay[];
  /** Client-set: when this snapshot was fetched (for "last updated" display). */
  fetchedAt: number;
}

export interface Vendor {
  id: string;
  name: string;
  distanceKm: number;
  lat: number;
  long: number;
}

export interface CropGrowthStage {
  stageName: string;
  startDay: number; // typical days from sowing, inclusive
  endDay: number; // typical days from sowing, exclusive
}

export interface Crop {
  id: string;
  name: string;
  varieties: { id: string; name: string }[];
  /** Growth-stage windows from GET /api/v1/catalog/crops; used to compute a
   * planting's current stage client-side. Empty for older cached payloads. */
  growthStages: CropGrowthStage[];
}

/**
 * Matches backend/models/agri_catalog.py's AgriCatalogCategory exactly —
 * NOT InterventionType. This table only ever holds chemical-type inputs
 * (fertilizer/pesticide/herbicide/fungicide/biocontrol/seed); irrigation,
 * labor, and harvest interventions have no catalog row at all
 * (Intervention.product_id is nullable specifically for those, per the
 * backend model's own comment) — see services/catalog.ts and
 * app/modals/quick-log.tsx for how the product picker is scoped to
 * "chemical" only as a result.
 */
export type AgriCatalogCategory =
  | "seed"
  | "fertilizer"
  | "pesticide"
  | "herbicide"
  | "fungicide"
  | "biocontrol";

export interface AgriCatalogItem {
  id: string;
  name: string;
  category: AgriCatalogCategory;
  unitOfMeasure: string;
  /** Crop names this input applies to; null/undefined = universal. */
  cropApplicability: string[] | null;
}

export interface District {
  state: string;
  districts: string[];
}
