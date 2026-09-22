import { Router } from "express";
import { requireUser } from "../auth.js";
import { newId, query, queryOne } from "../db.js";
import { HttpError } from "../errors.js";
import { plantingOwner } from "../services/ownership.js";
import { utcnow } from "../time.js";
import { date, enumOf, float, str, validateBody } from "../validate.js";

export const interventionsRouter = Router();

const TYPES = ["chemical", "irrigation", "labor", "harvest"];
const num = (v) => (v === null || v === undefined ? null : Number(v));

const toOut = (r) => ({
  id: r.id,
  planting_id: r.planting_id,
  type: r.type,
  product_id: r.product_id ?? null,
  quantity_metric: num(r.quantity_metric),
  quantity_unit: r.quantity_unit ?? null,
  cost_in_inr: Number(r.cost_in_inr),
  intervention_date: r.intervention_date,
  notes: r.notes ?? null,
});

const CREATE = () => [
  str("planting_id", { required: true }),
  enumOf("type", TYPES, { required: true }),
  str("product_id"),
  float("quantity_metric"),
  str("quantity_unit"),
  float("cost_in_inr", { required: true }),
  date("intervention_date", { required: true }),
  str("notes"),
];
const PATCH = () => [
  enumOf("type", TYPES),
  str("product_id"),
  float("quantity_metric"),
  str("quantity_unit"),
  float("cost_in_inr"),
  date("intervention_date"),
  str("notes"),
];

async function getOwnedOr404(id, userId) {
  const row = await queryOne("SELECT * FROM interventions WHERE id = ?", [id]);
  if (!row || row.deleted_at !== null) throw new HttpError(404, "Intervention not found.");
  if ((await plantingOwner(row.planting_id)) !== userId) throw new HttpError(403, "Not your data.");
  return row;
}

interventionsRouter.get("/", requireUser, async (req, res) => {
  const rows = await query(
    `SELECT i.* FROM interventions i
       JOIN plantings p ON i.planting_id = p.id
       JOIN fields f ON p.field_id = f.id
     WHERE f.user_id = ? AND i.deleted_at IS NULL`,
    [req.user.id]
  );
  res.json({ items: rows.map(toOut) });
});

interventionsRouter.post("/", requireUser, async (req, res) => {
  const { data } = validateBody(CREATE(), req.body);
  if ((await plantingOwner(data.planting_id)) !== req.user.id) {
    throw new HttpError(422, "planting_id: referenced planting not found.");
  }
  const now = utcnow();
  const row = {
    id: newId(),
    planting_id: data.planting_id,
    type: data.type,
    product_id: data.product_id ?? null,
    quantity_metric: data.quantity_metric ?? null,
    quantity_unit: data.quantity_unit ?? null,
    cost_in_inr: data.cost_in_inr,
    intervention_date: data.intervention_date,
    notes: data.notes ?? null,
  };
  await query(
    `INSERT INTO interventions (id, planting_id, type, product_id, quantity_metric,
       quantity_unit, cost_in_inr, intervention_date, notes, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    [row.id, row.planting_id, row.type, row.product_id, row.quantity_metric,
     row.quantity_unit, row.cost_in_inr, row.intervention_date, row.notes, now, now]
  );
  res.status(201).json(toOut(row));
});

interventionsRouter.patch("/:id", requireUser, async (req, res) => {
  const { data } = validateBody(PATCH(), req.body);
  const row = await getOwnedOr404(req.params.id, req.user.id);
  const cols = Object.keys(data);
  await query(
    `UPDATE interventions SET ${[...cols.map((c) => `${c} = ?`), "updated_at = ?"].join(", ")} WHERE id = ?`,
    [...cols.map((c) => data[c]), utcnow(), row.id]
  );
  res.json(toOut({ ...row, ...data }));
});

interventionsRouter.delete("/:id", requireUser, async (req, res) => {
  const row = await getOwnedOr404(req.params.id, req.user.id);
  const now = utcnow();
  await query("UPDATE interventions SET deleted_at = ?, updated_at = ? WHERE id = ?", [now, now, row.id]);
  res.status(204).end();
});
