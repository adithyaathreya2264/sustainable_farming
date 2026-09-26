// Pure mappings from app data to ML model inputs. No I/O; unit-tested in
// test/ml.test.js.

// App soil keys (frontend utils/soilTypes.ts) -> the crop-from-soil-type
// model's vocabulary (ml/algorithms/crop_recommendation.py known_soil_types()).
// Only exact semantic matches: saline, peaty and forest have no equivalent in
// that vocabulary, and guessing one would feed the model a soil the farmer
// does not have.
const SOIL_KEY_TO_MODEL = {
  alluvial: "Alluvial",
  black: "Black",
  red: "Red",
  laterite: "Laterite",
  arid: "Arid and Desert",
};

// Fields saved before the soil picker stored keys hold the English label
// ("Black / Regur"). Other-language legacy labels are not recoverable here and
// fall through to null, which only means the soil-type model is skipped.
const LEGACY_LABEL_PREFIX = [
  ["alluvial", "alluvial"],
  ["black", "black"],
  ["red", "red"],
  ["laterite", "laterite"],
  ["arid", "arid"],
  ["desert", "arid"],
];

export function soilKeyFromField(fieldSoilType) {
  if (!fieldSoilType) return null;
  const value = String(fieldSoilType).trim().toLowerCase();
  if (value in SOIL_KEY_TO_MODEL) return value;
  for (const [prefix, key] of LEGACY_LABEL_PREFIX) {
    if (value.startsWith(prefix)) return key;
  }
  return null;
}

export function soilTypeToModelVocab(fieldSoilType) {
  const key = soilKeyFromField(fieldSoilType);
  return key ? SOIL_KEY_TO_MODEL[key] : null;
}

// Soil-photo classes (model 7b) -> app soil keys. Cinder soil has no app
// equivalent; the farmer chooses manually.
const PHOTO_SOIL_TO_KEY = {
  "Alluvial Soil": "alluvial",
  "Black Soil": "black",
  "Red Soil": "red",
};

export function appSoilKeyFromPhoto(predictedSoilType) {
  return PHOTO_SOIL_TO_KEY[predictedSoilType] ?? null;
}

// Season names as the yield model and its benchmarks spell them.
const WHOLE_YEAR_CROPS = new Set(["sugarcane"]);

export function seasonFromSowingDate(sowingDate, cropKey) {
  if (WHOLE_YEAR_CROPS.has(cropKey)) return "Whole Year";
  const month = Number(String(sowingDate).slice(5, 7));
  if (!month) return null;
  if (month >= 6 && month <= 9) return "Kharif";
  if (month >= 10 || month === 1) return "Rabi";
  return "Summer";
}

/** soil_tests row -> {N, P, K, pH}, or null unless all four were measured. */
export function soilTestToSample(row) {
  if (!row) return null;
  const sample = {
    N: row.nitrogen,
    P: row.phosphorus,
    K: row.potassium,
    pH: row.ph,
  };
  if (Object.values(sample).some((v) => v === null || v === undefined)) return null;
  return Object.fromEntries(Object.entries(sample).map(([k, v]) => [k, Number(v)]));
}

// soil_tests column -> the soil-fertility model's (5b) feature name.
export const SOIL_CARD_FEATURES = {
  nitrogen: "N",
  phosphorus: "P",
  potassium: "K",
  ph: "pH",
  ec: "EC",
  organic_carbon: "OC",
  sulphur: "S",
  zinc: "Zn",
  iron: "Fe",
  copper: "Cu",
  manganese: "Mn",
  boron: "B",
};

/** soil_tests row -> {card, missing}: the model's 12 inputs, and the app
 * column names of any that were not measured (the model is never fed a guess). */
export function soilTestToCard(row) {
  const card = {};
  const missing = [];
  for (const [column, feature] of Object.entries(SOIL_CARD_FEATURES)) {
    const value = row?.[column];
    if (value === null || value === undefined) missing.push(column);
    else card[feature] = Number(value);
  }
  return { card, missing };
}
