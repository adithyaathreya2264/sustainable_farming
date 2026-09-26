// The one definition of "a field's current soil test", shared by crop
// recommendation, the nutrient check and the soil-fertility model.
import { queryOne } from "../db.js";

export function latestSoilTest(fieldId, q = { queryOne }) {
  return q.queryOne(
    "SELECT * FROM soil_tests WHERE field_id = ? ORDER BY tested_at DESC, seq DESC LIMIT 1",
    [fieldId]
  );
}
