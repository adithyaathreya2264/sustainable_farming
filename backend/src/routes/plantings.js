import { Router } from "express";
import { requireUser } from "../auth.js";
import { newId, query, queryOne } from "../db.js";
import { mlGet, mlPost } from "../services/mlClient.js";
import { soilTypeToModelVocab } from "../services/mlInputs.js";
import { HttpError } from "../errors.js";
import { fieldOwner } from "../services/ownership.js";
import { utcnow } from "../time.js";
import { latestSoilTest } from "../services/soilTests.js";
import { getWeatherReport } from "../services/weatherReport.js";
import { date, enumOf, str, validateBody, validateQuery } from "../validate.js";

export const plantingsRouter = Router();

// Rough, non-location-specific midpoints used when a field has no soil test
// on file, or weather is unavailable — not fabricated as measured, just a
// starting point so the recommendation still runs. See
// docs on app/modals/add-field.tsx's optional soil-test section.
const FALLBACK_INPUTS = {
  N: 50,
  P: 50,
  K: 50,
  ph: 6.5,
  temperature: 25,
  humidity: 60,
  rainfall: 100,
};

const STATUSES = ["active", "harvested"];

const toOut = (r) => ({
  id: r.id,
  field_id: r.field_id,
  crop_id: r.crop_id,
  variety_id: r.variety_id ?? null,
  sowing_date: r.sowing_date,
  status: r.status,
});

const CREATE = () => [
  str("field_id", { required: true }),
  str("crop_id", { required: true }),
  str("variety_id"),
  date("sowing_date", { required: true }),
  enumOf("status", STATUSES, { default: "active", nonNull: true }),
];
const PATCH = () => [
  str("crop_id"),
  str("variety_id"),
  date("sowing_date"),
  enumOf("status", STATUSES),
];

async function getOwnedOr404(id, userId) {
  const row = await queryOne("SELECT * FROM plantings WHERE id = ?", [id]);
  if (!row || row.deleted_at !== null) throw new HttpError(404, "Planting not found.");
  if ((await fieldOwner(row.field_id)) !== userId) throw new HttpError(403, "Not your data.");
  return row;
}

plantingsRouter.get("/", requireUser, async (req, res) => {
  const rows = await query(
    `SELECT p.* FROM plantings p JOIN fields f ON p.field_id = f.id
     WHERE f.user_id = ? AND p.deleted_at IS NULL`,
    [req.user.id]
  );
  res.json({ items: rows.map(toOut) });
});

plantingsRouter.get("/recommend-crop", requireUser, async (req, res) => {
  const q = validateQuery([{ name: "field_id", required: true }], req.query);
  const field = await queryOne("SELECT * FROM fields WHERE id = ? AND deleted_at IS NULL", [
    q.field_id,
  ]);
  if (!field) throw new HttpError(404, "Field not found.");
  if (field.user_id !== req.user.id) throw new HttpError(403, "Not your data.");

  const soilTest = await latestSoilTest(field.id);

  const user = await queryOne("SELECT state, district FROM users WHERE id = ?", [req.user.id]);
  const weather = await getWeatherReport(user?.state ?? "", user?.district ?? "");

  const weatherInputs = {
    temperature: weather.available && weather.temperature_c != null
      ? weather.temperature_c
      : FALLBACK_INPUTS.temperature,
    humidity: weather.available && weather.humidity_pct != null
      ? weather.humidity_pct
      : FALLBACK_INPUTS.humidity,
    rainfall: weather.available && weather.precipitation_mm != null
      ? weather.precipitation_mm
      : FALLBACK_INPUTS.rainfall,
  };
  const ph = soilTest?.ph != null ? Number(soilTest.ph) : FALLBACK_INPUTS.ph;

  // Best evidence first: a soil test drives the N/P/K model (1); failing that,
  // a known soil type drives the crop-from-soil-type model (2), which is also
  // the only one that can recommend sugarcane; failing both, model 1 runs on
  // generic midpoints and says so.
  const soilModelType = soilTypeToModelVocab(field.soil_type);
  let basis;
  let modelId;
  let result;
  if (soilTest) {
    basis = "soil_test";
    modelId = "crop_recommendation";
    result = await mlPost("/v1/crop-recommendation", {
      N: soilTest.nitrogen != null ? Number(soilTest.nitrogen) : FALLBACK_INPUTS.N,
      P: soilTest.phosphorus != null ? Number(soilTest.phosphorus) : FALLBACK_INPUTS.P,
      K: soilTest.potassium != null ? Number(soilTest.potassium) : FALLBACK_INPUTS.K,
      ph,
      ...weatherInputs,
    });
  } else if (soilModelType) {
    basis = "soil_type";
    modelId = "crop_soil_type";
    result = await mlPost("/v1/crop-recommendation/soil-type", {
      soil_type: soilModelType,
      ph,
      ...weatherInputs,
    });
  } else {
    basis = "defaults";
    modelId = "crop_recommendation";
    result = await mlPost("/v1/crop-recommendation", {
      N: FALLBACK_INPUTS.N,
      P: FALLBACK_INPUTS.P,
      K: FALLBACK_INPUTS.K,
      ph,
      ...weatherInputs,
    });
  }

  // Join model crop keys to app crops, and name the app crops this model can
  // never return (e.g. sugarcane for model 1) so the app can say "not scored"
  // rather than imply they were considered and ranked low.
  const appCrops = await query("SELECT id, ml_key FROM crops WHERE active = 1 AND ml_key IS NOT NULL");
  const cropIdByKey = new Map(appCrops.map((c) => [c.ml_key, c.id]));
  const reachable = new Set((await mlGet(`/v1/models/${modelId}/classes`)).crop_keys);
  const withCropId = (entry) => ({ ...entry, crop_id: cropIdByKey.get(entry.crop_key) ?? null });

  res.json({
    recommended: withCropId(result.recommended),
    alternatives: result.alternatives.map(withCropId),
    unreachable_seeded_crops: appCrops.map((c) => c.ml_key).filter((k) => !reachable.has(k)).sort(),
    used_soil_test: basis === "soil_test",
    basis,
    model: modelId,
  });
});

plantingsRouter.post("/", requireUser, async (req, res) => {
  const { data } = validateBody(CREATE(), req.body);
  if ((await fieldOwner(data.field_id)) !== req.user.id) {
    throw new HttpError(422, "field: referenced field not found.");
  }
  const now = utcnow();
  const row = {
    id: newId(),
    field_id: data.field_id,
    crop_id: data.crop_id,
    variety_id: data.variety_id ?? null,
    sowing_date: data.sowing_date,
    status: data.status,
  };
  await query(
    `INSERT INTO plantings (id, field_id, crop_id, variety_id, sowing_date, status,
       created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
    [row.id, row.field_id, row.crop_id, row.variety_id, row.sowing_date, row.status, now, now]
  );
  res.status(201).json(toOut(row));
});

plantingsRouter.patch("/:id", requireUser, async (req, res) => {
  const { data } = validateBody(PATCH(), req.body);
  const row = await getOwnedOr404(req.params.id, req.user.id);
  const cols = Object.keys(data);
  await query(
    `UPDATE plantings SET ${[...cols.map((c) => `${c} = ?`), "updated_at = ?"].join(", ")} WHERE id = ?`,
    [...cols.map((c) => data[c]), utcnow(), row.id]
  );
  res.json(toOut({ ...row, ...data }));
});

plantingsRouter.delete("/:id", requireUser, async (req, res) => {
  const row = await getOwnedOr404(req.params.id, req.user.id);
  const now = utcnow();
  await query("UPDATE plantings SET deleted_at = ?, updated_at = ? WHERE id = ?", [now, now, row.id]);
  res.status(204).end();
});
