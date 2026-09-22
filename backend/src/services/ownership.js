// Resolves whose user_id a row ultimately belongs to. Like the Python version,
// it does not consider soft deletion.
import { queryOne } from "../db.js";

export async function fieldOwner(fieldId, q = { queryOne }) {
  const row = await q.queryOne("SELECT user_id FROM fields WHERE id = ?", [fieldId]);
  return row ? row.user_id : null;
}

export async function plantingOwner(plantingId, q = { queryOne }) {
  const row = await q.queryOne("SELECT field_id FROM plantings WHERE id = ?", [plantingId]);
  if (!row) return null;
  return fieldOwner(row.field_id, q);
}
