import { Router } from "express";
import { requireUser } from "../auth.js";
import { newId, query, queryOne } from "../db.js";
import { HttpError } from "../errors.js";
import { utcnow } from "../time.js";
import { float, listDict, str, validateBody } from "../validate.js";

export const fieldsRouter = Router();

const toOut = (r) => ({
  id: r.id,
  user_id: r.user_id,
  name: r.name,
  area_size_hectares: Number(r.area_size_hectares),
  lat: Number(r.lat),
  long: Number(r.long),
  boundary: typeof r.boundary === "string" ? JSON.parse(r.boundary) : r.boundary,
  soil_type: r.soil_type ?? null,
});

const CREATE = () => [
  str("name", { required: true }),
  float("area_size_hectares", { required: true }),
  float("lat", { required: true }),
  float("long", { required: true }),
  listDict("boundary", { required: true }),
  str("soil_type"),
];
const PATCH = () => [
  str("name"),
  float("area_size_hectares"),
  float("lat"),
  float("long"),
  listDict("boundary"),
  str("soil_type"),
];

async function getOwnedOr404(id, userId) {
  const row = await queryOne("SELECT * FROM fields WHERE id = ?", [id]);
  if (!row || row.deleted_at !== null) throw new HttpError(404, "Field not found.");
  if (row.user_id !== userId) throw new HttpError(403, "Not your data.");
  return row;
}

const dbValue = (col, v) => (col === "boundary" && v !== null ? JSON.stringify(v) : v);

fieldsRouter.get("/", requireUser, async (req, res) => {
  const rows = await query(
    "SELECT * FROM fields WHERE user_id = ? AND deleted_at IS NULL",
    [req.user.id]
  );
  res.json({ items: rows.map(toOut) });
});

// soil_test is an optional nested object of all-nullable numbers, read and
// coerced by hand (validateBody's declarative specs don't cover nested shapes).
// The first four feed crop recommendation and the nutrient check; all twelve
// (a full soil-test card) are needed by the soil-fertility model (5b).
export const SOIL_TEST_COLUMNS = [
  "nitrogen", "phosphorus", "potassium", "ph",
  "ec", "organic_carbon", "sulphur", "zinc", "iron", "copper", "manganese", "boron",
];

export function parseSoilTest(raw) {
  if (raw === null || raw === undefined) return null;
  if (typeof raw !== "object" || Array.isArray(raw)) {
    throw new HttpError(422, "soil_test must be an object.");
  }
  const num = (v) => (v === null || v === undefined || v === "" ? null : Number(v));
  const out = Object.fromEntries(SOIL_TEST_COLUMNS.map((c) => [c, num(raw[c])]));
  if (Object.values(out).some((v) => v !== null && (Number.isNaN(v) || v < 0))) {
    throw new HttpError(422, "soil_test values must be non-negative numbers.");
  }
  if (out.ph !== null && out.ph > 14) throw new HttpError(422, "soil_test.ph must be between 0 and 14.");
  if (Object.values(out).every((v) => v === null)) return null;
  return out;
}

async function insertSoilTest(fieldId, soilTest, now) {
  const id = newId();
  await query(
    `INSERT INTO soil_tests (id, field_id, ${SOIL_TEST_COLUMNS.join(", ")}, tested_at, created_at)
     VALUES (?, ?, ${SOIL_TEST_COLUMNS.map(() => "?").join(", ")}, ?, ?)`,
    [id, fieldId, ...SOIL_TEST_COLUMNS.map((c) => soilTest[c]), now, now]
  );
  return { id, field_id: fieldId, ...soilTest, tested_at: now };
}

fieldsRouter.post("/", requireUser, async (req, res) => {
  const { data } = validateBody(CREATE(), req.body);
  const soilTest = parseSoilTest(req.body.soil_test);
  const now = utcnow();
  const row = {
    id: newId(),
    user_id: req.user.id,
    name: data.name,
    area_size_hectares: data.area_size_hectares,
    lat: data.lat,
    long: data.long,
    boundary: data.boundary,
    soil_type: data.soil_type ?? null,
  };
  await query(
    `INSERT INTO fields (id, user_id, name, area_size_hectares, lat, \`long\`, boundary,
       soil_type, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    [row.id, row.user_id, row.name, row.area_size_hectares, row.lat, row.long,
     JSON.stringify(row.boundary), row.soil_type, now, now]
  );
  if (soilTest) await insertSoilTest(row.id, soilTest, now);
  res.status(201).json(toOut(row));
});

fieldsRouter.patch("/:id", requireUser, async (req, res) => {
  const { data } = validateBody(PATCH(), req.body);
  const row = await getOwnedOr404(req.params.id, req.user.id);
  const cols = Object.keys(data);
  const updatedAt = utcnow();
  await query(
    `UPDATE fields SET ${[...cols.map((c) => `\`${c}\` = ?`), "updated_at = ?"].join(", ")} WHERE id = ?`,
    [...cols.map((c) => dbValue(c, data[c])), updatedAt, row.id]
  );
  res.json(toOut({ ...row, ...data }));
});

fieldsRouter.delete("/:id", requireUser, async (req, res) => {
  const row = await getOwnedOr404(req.params.id, req.user.id);
  const now = utcnow();
  await query("UPDATE fields SET deleted_at = ?, updated_at = ? WHERE id = ?", [now, now, row.id]);
  res.status(204).end();
});

// A new soil test for an existing field (e.g. a soil health card that arrived
// after the field was created). The latest test by tested_at is what the ML
// routes read, so this supersedes older ones without deleting them.
fieldsRouter.post("/:id/soil-tests", requireUser, async (req, res) => {
  const row = await getOwnedOr404(req.params.id, req.user.id);
  const soilTest = parseSoilTest(req.body);
  if (!soilTest) throw new HttpError(422, "At least one soil-test value is required.");
  res.status(201).json(await insertSoilTest(row.id, soilTest, utcnow()));
});
