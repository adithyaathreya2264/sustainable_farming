import { Router } from "express";
import { requireUser } from "../auth.js";
import { newId, query, queryOne } from "../db.js";
import { HttpError } from "../errors.js";
import { fieldOwner } from "../services/ownership.js";
import { utcnow } from "../time.js";
import { date, enumOf, str, validateBody } from "../validate.js";

export const plantingsRouter = Router();

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
