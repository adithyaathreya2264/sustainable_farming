/**
 * Data shapes mirror the MySQL entities in the Technical Design doc
 * (users, fields, plantings, interventions, agri_catalog, govt_schemes) so the
 * eventual FastAPI/WatermelonDB layer is a drop-in swap for these services.
 * All geospatial/area values are stored canonically in hectares.
 */

export type LandUnit = "hectare" | "acre" | "guntha" | "bigha" | "cent" | "killa";

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
}

export type PlantingStatus = "active" | "harvested";

export interface Planting {
  id: string;
  fieldId: string;
  cropId: string;
  varietyId: string;
  sowingDate: string; // ISO date
  status: PlantingStatus;
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

export type AlertSeverity = "high" | "medium" | "low";

export interface Recommendation {
  id: string;
  plantingId: string;
  title: string;
  description: string;
  severity: AlertSeverity;
  confidencePct: number;
  recommendedProductId?: string;
  createdAt: string;
}

export interface Vendor {
  id: string;
  name: string;
  distanceKm: number;
  lat: number;
  long: number;
}

export type SchemeLevel = "central" | "state";

export interface Scheme {
  id: string;
  name: string;
  level: SchemeLevel;
  summary: string;
  eligibilityCriteria: string[];
  benefits: string;
  howToApply: string;
  contactOffice: string;
  contactPhone: string;
}

export interface Crop {
  id: string;
  name: string;
  varieties: { id: string; name: string }[];
}

export interface AgriCatalogItem {
  id: string;
  name: string;
  category: InterventionType;
  defaultUnit: string;
}

export interface District {
  state: string;
  districts: string[];
}
