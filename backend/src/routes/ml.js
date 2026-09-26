// App-facing ML endpoints. Every model call goes through services/mlClient.js
// to the Python sidecar (ml/serving/); this file owns identity, ownership,
// photo storage and the ml_inferences audit trail.
//
// Nothing here writes `recommendations` or alerts. Where a model result points
// at a rule (an insect detection's `related_rules`), the app prompts the farmer
// to log the matching scouting metric and the rule engine takes it from there.
import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { Router } from "express";
import multer from "multer";
import { requireUser } from "../auth.js";
import { BACKEND_DIR } from "../config.js";
import { newId, query, queryOne } from "../db.js";
import { HttpError } from "../errors.js";
import { mlGet, mlImage, mlPost } from "../services/mlClient.js";
import {
  appSoilKeyFromPhoto,
  seasonFromSowingDate,
  soilTestToCard,
  soilTestToSample,
} from "../services/mlInputs.js";
import { fieldOwner } from "../services/ownership.js";
import { utcnow } from "../time.js";
import { latestSoilTest } from "../services/soilTests.js";
import { validateQuery } from "../validate.js";

export const mlRouter = Router();

export const UPLOADS_DIR = path.join(BACKEND_DIR, "uploads");
const MAX_UPLOAD_BYTES = 8 * 1024 * 1024;
const IMAGE_TYPES = { "image/jpeg": "jpg", "image/png": "png" };
const KARNATAKA = "karnataka";

// --- helpers ---------------------------------------------------------------

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: MAX_UPLOAD_BYTES, files: 1 },
  fileFilter: (_req, file, cb) => cb(null, file.mimetype in IMAGE_TYPES),
});

/** multer's errors -> the same {detail, reason} shape as everything else. */
function singlePhoto(req, res, next) {
  upload.single("photo")(req, res, (err) => {
    if (err?.code === "LIMIT_FILE_SIZE") {
      return next(new HttpError(413, "Photo is larger than 8 MB.", {}, { reason: "image_too_large" }));
    }
    if (err) return next(new HttpError(422, err.message, {}, { reason: "invalid_upload" }));
    if (!req.file) {
      return next(new HttpError(422, "A JPEG or PNG photo is required in field 'photo'.", {}, {
        reason: "invalid_upload",
      }));
    }
    next();
  });
}

/** Planting + its field + its crop, 404/403 as the rest of the API does. */
async function ownedPlanting(plantingId, userId) {
  const row = await queryOne(
    `SELECT p.id, p.field_id, p.crop_id, p.sowing_date, p.status,
            f.user_id, f.soil_type, c.name AS crop_name, c.ml_key
       FROM plantings p
       JOIN fields f ON f.id = p.field_id
       JOIN crops c ON c.id = p.crop_id
      WHERE p.id = ? AND p.deleted_at IS NULL`,
    [plantingId]
  );
  if (!row) throw new HttpError(404, "Planting not found.");
  if (row.user_id !== userId) throw new HttpError(403, "Not your data.");
  if (!row.ml_key) {
    throw new HttpError(409, "No model covers this crop.", {}, { reason: "crop_not_modelled" });
  }
  return row;
}

const capabilityCache = new Map(); // crop key -> [storedAtMs, caps]
const CAPABILITY_TTL_MS = 10 * 60 * 1000;

async function capabilitiesFor(cropKey) {
  const hit = capabilityCache.get(cropKey);
  if (hit && Date.now() - hit[0] < CAPABILITY_TTL_MS) return hit[1];
  const body = await mlGet("/v1/capabilities", { crop: cropKey });
  capabilityCache.set(cropKey, [Date.now(), body.capabilities]);
  return body.capabilities;
}

async function requireCapability(cropKey, name) {
  const caps = await capabilitiesFor(cropKey);
  const entry = caps[name];
  if (!entry?.available) {
    throw new HttpError(409, "This check is not available for this crop.", {}, {
      reason: entry?.reason ?? "not_available",
    });
  }
  return entry;
}

async function storePhoto(file) {
  const now = new Date();
  const rel = path.posix.join(
    "ml",
    String(now.getUTCFullYear()),
    String(now.getUTCMonth() + 1).padStart(2, "0"),
    `${crypto.randomUUID()}.${IMAGE_TYPES[file.mimetype]}`
  );
  const abs = path.join(UPLOADS_DIR, ...rel.split("/"));
  await fs.mkdir(path.dirname(abs), { recursive: true });
  await fs.writeFile(abs, file.buffer);
  return {
    image_path: rel,
    image_sha256: crypto.createHash("sha256").update(file.buffer).digest("hex"),
  };
}

// A photo the sidecar could not even decode is not worth keeping.
const DISCARD_REASONS = new Set(["invalid_image", "image_too_large"]);

/**
 * Run an image model, then store the photo and an ml_inferences row whatever
 * the outcome, so every stored photo has an audit row. Re-throws model errors
 * after recording them.
 */
async function runImageModel({ req, sidecarPath, fields, model, cropKey, fieldId, plantingId, request }) {
  let result = null;
  let failure = null;
  try {
    result = await mlImage(sidecarPath, req.file.buffer, req.file.mimetype, fields);
  } catch (err) {
    failure = err;
  }
  const reason = failure?.extra?.reason;
  if (failure && DISCARD_REASONS.has(reason)) throw failure;

  const stored = await storePhoto(req.file);
  const id = newId();
  const outcome = !failure ? "ok" : failure.status === 409 || failure.status === 422 ? "refused" : "error";
  await query(
    `INSERT INTO ml_inferences
       (id, user_id, field_id, planting_id, model, crop_key, image_path, image_sha256,
        request_json, response_json, outcome, created_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    [
      id, req.user.id, fieldId ?? null, plantingId ?? null, model, cropKey ?? null,
      stored.image_path, stored.image_sha256,
      JSON.stringify(request ?? {}),
      JSON.stringify(result ?? { reason: reason ?? "error", detail: failure?.detail ?? null }),
      outcome, utcnow(),
    ]
  );
  if (failure) throw failure;
  return { inferenceId: id, result };
}

// --- capabilities ------------------------------------------------------------

mlRouter.get("/capabilities", requireUser, async (req, res) => {
  const q = validateQuery([{ name: "planting_id", required: true }], req.query);
  const planting = await ownedPlanting(q.planting_id, req.user.id);
  res.json({ crop_key: planting.ml_key, capabilities: await capabilitiesFor(planting.ml_key) });
});

// --- soil type from photo (model 7b) -----------------------------------------

mlRouter.post("/soil-type", requireUser, singlePhoto, async (req, res) => {
  const fieldId = req.body?.field_id || null;
  if (fieldId && (await fieldOwner(fieldId)) !== req.user.id) {
    throw new HttpError(403, "Not your data.");
  }
  const { inferenceId, result } = await runImageModel({
    req,
    sidecarPath: "/v1/soil-type",
    model: "soil_type_photo",
    fieldId,
    request: { field_id: fieldId },
  });
  res.json({
    inference_id: inferenceId,
    predicted_soil_type: result.predicted_soil_type,
    app_soil_key: appSoilKeyFromPhoto(result.predicted_soil_type),
    confidence_label: result.confidence_label,
    ranked: (result.ranked ?? []).map((r) => ({
      soil_type: r.soil_type,
      app_soil_key: appSoilKeyFromPhoto(r.soil_type),
      confidence_label: r.confidence_label,
    })),
  });
});

// --- photo checks on a planting (models 11, 12, 13, 14b, 17) -----------------

// Leaf-pipeline kinds (leaf, curd, bulb, fruit_grade) all go to /v1/leaf; the
// capability's model_key names which registry model ("cauliflower curd",
// "tomato fruit", ...), so a crop with several parts needs no code here.
const leafModelId = (modelKey) => `leaf_condition_${modelKey.replace(/\s+/g, "_")}`;
const PHOTO_CHECKS = {
  insects: { capability: "insect_detection", path: "/v1/insects", model: () => "insect_detector" },
  leaf: { capability: "leaf_diagnosis", path: "/v1/leaf", leafPipeline: true },
  curd: { capability: "curd_diagnosis", path: "/v1/leaf", leafPipeline: true },
  bulb: { capability: "bulb_diagnosis", path: "/v1/leaf", leafPipeline: true },
  fruit_grade: { capability: "fruit_grade", path: "/v1/leaf", leafPipeline: true },
  wheat_heading: { capability: "wheat_heading", path: "/v1/wheat-heading", model: () => "wheat_heading" },
  // Held in ml/serving/holds.py: requireCapability refuses it (409
  // awaiting_lighting_check) before any photo is stored.
  wheat_kernels: { capability: "wheat_kernels", path: "/v1/wheat-kernels", model: () => "wheat_kernel_damage" },
  tobacco_lesions: { capability: "tobacco_lesions", path: "/v1/tobacco-lesions", model: () => "tobacco_lesions" },
};

mlRouter.post("/plantings/:id/photo-check", requireUser, singlePhoto, async (req, res) => {
  const planting = await ownedPlanting(req.params.id, req.user.id);
  const kind = req.body?.kind;
  const check = PHOTO_CHECKS[kind];
  if (!check) {
    throw new HttpError(422, `kind must be one of: ${Object.keys(PHOTO_CHECKS).join(", ")}`, {}, {
      reason: "invalid_input",
    });
  }
  const capability = await requireCapability(planting.ml_key, check.capability);
  const symptomReported = ["true", "1", "yes"].includes(String(req.body?.symptom_reported ?? "").toLowerCase());
  if (check.leafPipeline && capability.conditional && !symptomReported) {
    // The rice/pearl-millet models have no healthy class: they would name a
    // disease for a healthy leaf. Refuse before storing anything.
    throw new HttpError(422, "Confirm that symptoms are visible before a leaf check.", {}, {
      reason: "symptom_required",
    });
  }

  const modelKey = check.leafPipeline ? capability.model_key ?? planting.ml_key : planting.ml_key;
  const fields = { crop: modelKey };
  if (check.leafPipeline) fields.symptom_reported = symptomReported;
  const { inferenceId, result } = await runImageModel({
    req,
    sidecarPath: check.path,
    fields,
    model: check.leafPipeline ? leafModelId(modelKey) : check.model(planting.ml_key),
    cropKey: planting.ml_key,
    fieldId: planting.field_id,
    plantingId: planting.id,
    request: { kind, symptom_reported: symptomReported },
  });
  res.json({ kind, inference_id: inferenceId, result });
});

// --- nutrient check (model 3) ------------------------------------------------

mlRouter.get("/plantings/:id/fertilizer", requireUser, async (req, res) => {
  const planting = await ownedPlanting(req.params.id, req.user.id);
  const soilTest = await latestSoilTest(planting.field_id);
  const sample = soilTestToSample(soilTest);

  let result;
  try {
    result = await mlPost("/v1/fertilizer", sample
      ? { crop: planting.ml_key, soil_sample: sample }
      : { crop: planting.ml_key, state: req.user.state });
  } catch (err) {
    if (err.status === 422) return res.json({ available: false, reason: "no_state_average" });
    throw err;
  }
  if (result.error) return res.json({ available: false, reason: result.error });

  // Product names come from agri_catalog, never from the model (ml/README.md rule 2).
  const products = await query(
    `SELECT id, name, unit_of_measure FROM agri_catalog
      WHERE active = 1 AND category = 'fertilizer'
        AND JSON_CONTAINS(crop_applicability, JSON_QUOTE(?))`,
    [planting.crop_name]
  );
  res.json({
    available: true,
    basis: sample ? "soil_test" : "state_average",
    soil_tested_at: sample ? soilTest.tested_at : null,
    deficits: result.deficits,
    actionable: result.actionable,
    actionable_threshold: result.actionable_threshold,
    ph: result.ph,
    confidence_label: result.confidence_label,
    products,
  });
});

// --- soil fertility class (model 5b) -----------------------------------------
// A property of the field's soil, not of a crop, so it is keyed by field.
// Needs all 12 values of a soil-test card; with fewer, the response names the
// missing ones so the app can ask for them instead of the model guessing.

mlRouter.get("/fields/:id/soil-fertility", requireUser, async (req, res) => {
  const field = await queryOne("SELECT id, user_id FROM fields WHERE id = ? AND deleted_at IS NULL", [
    req.params.id,
  ]);
  if (!field) throw new HttpError(404, "Field not found.");
  if (field.user_id !== req.user.id) throw new HttpError(403, "Not your data.");

  const soilTest = await latestSoilTest(field.id);
  if (!soilTest) return res.json({ available: false, reason: "no_soil_test", missing: [] });
  const { card, missing } = soilTestToCard(soilTest);
  if (missing.length) {
    return res.json({ available: false, reason: "incomplete_soil_test", missing, tested_at: soilTest.tested_at });
  }

  const result = await mlPost("/v1/soil-fertility", card);
  res.json({
    available: true,
    fertility_class: result.fertility_class,
    confidence_label: result.confidence_label,
    provenance_verified: result.provenance_verified,
    caveats: result.caveats ?? [],
    tested_at: soilTest.tested_at,
  });
});

// --- yield outlook (model 6) -------------------------------------------------

mlRouter.get("/plantings/:id/yield-outlook", requireUser, async (req, res) => {
  const planting = await ownedPlanting(req.params.id, req.user.id);
  const sowing = String(planting.sowing_date);
  const season = seasonFromSowingDate(sowing, planting.ml_key);
  let result;
  try {
    result = await mlPost("/v1/yield", {
      crop: planting.ml_key,
      season,
      state: req.user.state,
      year: Number(sowing.slice(0, 4)),
    });
  } catch (err) {
    if (err.status === 422) return res.json({ available: false, reason: "no_yield_history" });
    throw err;
  }
  // A band only - rule 3 of ml/README.md. The sidecar has already stripped the
  // raw model output; nothing numeric about yield is forwarded but the percentile.
  res.json({
    available: result.position !== null,
    position: result.position,
    percentile_within_crop: result.percentile_within_crop,
    comparison_scope: result.comparison_scope ?? null,
    season: result.season,
    state: result.state,
    year: result.year,
    year_in_training_range: result.year_in_training_range,
    inputs_basis: result.inputs_basis,
    unit: null,
    unit_note: result.unit_note,
    caveats: result.caveats ?? [],
  });
});

// --- disease lookup (model 4b) -----------------------------------------------

mlRouter.get("/plantings/:id/diseases", requireUser, async (req, res) => {
  const q = validateQuery([{ name: "q", required: true }], req.query);
  const planting = await ownedPlanting(req.params.id, req.user.id);
  res.json(await mlGet("/v1/disease/search", { crop: planting.ml_key, q: q.q }));
});

// The "see all diseases for this crop" path that bar 4b's shipping condition
// requires to stay visible (ml/MODEL_RESULTS.md section 4b).
mlRouter.get("/plantings/:id/diseases/all", requireUser, async (req, res) => {
  const planting = await ownedPlanting(req.params.id, req.user.id);
  res.json(await mlGet("/v1/disease/list", { crop: planting.ml_key }));
});

mlRouter.get("/plantings/:id/diseases/detail", requireUser, async (req, res) => {
  const q = validateQuery([{ name: "disease", required: true }], req.query);
  const planting = await ownedPlanting(req.params.id, req.user.id);
  res.json(await mlGet("/v1/disease/detail", { crop: planting.ml_key, disease: q.disease }));
});

// --- market (model 18) -------------------------------------------------------

const outlookCache = new Map(); // "commodity\0district" -> [storedAtMs, body]
// Forecasts are fixed until the price dataset is refreshed and the model re-run.
const OUTLOOK_TTL_MS = 6 * 60 * 60 * 1000;

function inKarnataka(user) {
  return String(user.state ?? "").trim().toLowerCase() === KARNATAKA;
}

mlRouter.get("/market/commodities", requireUser, async (req, res) => {
  const body = await mlGet("/v1/price/commodities");
  // The farmer's own crops first.
  const own = await query(
    `SELECT DISTINCT c.ml_key FROM plantings p
       JOIN fields f ON f.id = p.field_id JOIN crops c ON c.id = p.crop_id
      WHERE f.user_id = ? AND p.deleted_at IS NULL AND p.status = 'active'`,
    [req.user.id]
  );
  res.json({
    available: inKarnataka(req.user),
    reason: inKarnataka(req.user) ? undefined : "karnataka_only",
    district: req.user.district,
    own_crop_keys: own.map((r) => r.ml_key).filter(Boolean),
    commodities: body.commodities,
  });
});

mlRouter.get("/market/outlook", requireUser, async (req, res) => {
  const q = validateQuery([{ name: "commodity", required: true }, { name: "district" }], req.query);
  if (!inKarnataka(req.user)) return res.json({ available: false, reason: "karnataka_only" });
  const district = (q.district || req.user.district || "").trim();
  const key = `${q.commodity}\u0000${district.toLowerCase()}`;
  const hit = outlookCache.get(key);
  if (hit && Date.now() - hit[0] < OUTLOOK_TTL_MS) return res.json(hit[1]);
  const body = { available: true, ...(await mlGet("/v1/price/outlook", { commodity: q.commodity, district })) };
  outlookCache.set(key, [Date.now(), body]);
  res.json(body);
});

// --- the farmer's own photo history ------------------------------------------

const inferenceOut = (r) => ({
  id: r.id,
  model: r.model,
  crop_key: r.crop_key,
  field_id: r.field_id,
  planting_id: r.planting_id,
  outcome: r.outcome,
  has_image: Boolean(r.image_path),
  result: typeof r.response_json === "string" ? JSON.parse(r.response_json) : r.response_json,
  created_at: r.created_at,
});

mlRouter.get("/inferences", requireUser, async (req, res) => {
  const q = validateQuery([{ name: "planting_id" }, { name: "limit" }], req.query);
  const limit = Math.min(Math.max(Number(q.limit) || 50, 1), 200);
  const params = [req.user.id];
  let where = "user_id = ? AND deleted_at IS NULL";
  if (q.planting_id) {
    where += " AND planting_id = ?";
    params.push(q.planting_id);
  }
  const rows = await query(
    `SELECT * FROM ml_inferences WHERE ${where} ORDER BY created_at DESC LIMIT ${limit}`,
    params
  );
  res.json({ items: rows.map(inferenceOut) });
});

async function ownedInference(id, userId) {
  const row = await queryOne("SELECT * FROM ml_inferences WHERE id = ? AND deleted_at IS NULL", [id]);
  if (!row) throw new HttpError(404, "Not found.");
  if (row.user_id !== userId) throw new HttpError(403, "Not your data.");
  return row;
}

mlRouter.get("/inferences/:id/image", requireUser, async (req, res) => {
  const row = await ownedInference(req.params.id, req.user.id);
  if (!row.image_path) throw new HttpError(404, "No photo stored.");
  const abs = path.resolve(UPLOADS_DIR, ...row.image_path.split("/"));
  if (!abs.startsWith(UPLOADS_DIR + path.sep)) throw new HttpError(404, "No photo stored.");
  res.sendFile(abs, (err) => {
    if (err && !res.headersSent) res.status(404).json({ detail: "No photo stored." });
  });
});

mlRouter.delete("/inferences/:id", requireUser, async (req, res) => {
  const row = await ownedInference(req.params.id, req.user.id);
  await query("UPDATE ml_inferences SET deleted_at = ?, image_path = NULL WHERE id = ?", [utcnow(), row.id]);
  if (row.image_path) {
    await fs.rm(path.join(UPLOADS_DIR, ...row.image_path.split("/")), { force: true });
  }
  res.status(204).end();
});
