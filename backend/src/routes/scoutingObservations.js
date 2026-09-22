import { Router } from "express";
import { requireUser } from "../auth.js";
import { newId, query, queryOne } from "../db.js";
import { HttpError } from "../errors.js";
import { plantingOwner } from "../services/ownership.js";
import { utcnow } from "../time.js";
import { date, float, str, validateBody } from "../validate.js";

export const scoutingRouter = Router();

const toOut = (r) => ({
  id: r.id,
  planting_id: r.planting_id,
  metric_key: r.metric_key,
  metric_value: Number(r.metric_value),
  observed_at: r.observed_at,
  notes: r.notes ?? null,
});

const CREATE = () => [
  str("planting_id", { required: true }),
  str("metric_key", { required: true }),
  float("metric_value", { required: true }),
  date("observed_at", { required: true }),
  str("notes"),
];

scoutingRouter.get("/", requireUser, async (req, res) => {
  const rows = await query(
    `SELECT s.* FROM scouting_observations s
       JOIN plantings p ON s.planting_id = p.id
       JOIN fields f ON p.field_id = f.id
     WHERE f.user_id = ? AND s.deleted_at IS NULL`,
    [req.user.id]
  );
  res.json({ items: rows.map(toOut) });
});

scoutingRouter.post("/", requireUser, async (req, res) => {
  const { data } = validateBody(CREATE(), req.body);
  if ((await plantingOwner(data.planting_id)) !== req.user.id) {
    throw new HttpError(422, "planting_id: referenced planting not found.");
  }
  const now = utcnow();
  const row = {
    id: newId(),
    planting_id: data.planting_id,
    metric_key: data.metric_key,
    metric_value: data.metric_value,
    observed_at: data.observed_at,
    notes: data.notes ?? null,
  };
  await query(
    `INSERT INTO scouting_observations (id, planting_id, metric_key, metric_value,
       observed_at, notes, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
    [row.id, row.planting_id, row.metric_key, row.metric_value, row.observed_at, row.notes, now, now]
  );
  res.status(201).json(toOut(row));
});

scoutingRouter.delete("/:id", requireUser, async (req, res) => {
  const row = await queryOne("SELECT * FROM scouting_observations WHERE id = ?", [req.params.id]);
  if (!row || row.deleted_at !== null) throw new HttpError(404, "Observation not found.");
  if ((await plantingOwner(row.planting_id)) !== req.user.id) {
    throw new HttpError(403, "Not your data.");
  }
  const now = utcnow();
  await query(
    "UPDATE scouting_observations SET deleted_at = ?, updated_at = ? WHERE id = ?",
    [now, now, row.id]
  );
  res.status(204).end();
});
