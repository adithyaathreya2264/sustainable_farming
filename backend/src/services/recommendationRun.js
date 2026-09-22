// Batch recommendation run: evaluate every active planting.
import { query, withTransaction } from "../db.js";
import { addDays, utcToday } from "../time.js";
import { evaluatePlanting } from "./ruleEngine.js";
import { getWeatherSnapshot } from "./weatherReport.js";

// A scouting count older than this is treated as stale and not fed to the rule engine.
const SCOUTING_RECENCY_DAYS = 14;

/** Latest non-deleted value per metric_key within the recency window. */
async function scoutingForPlanting(plantingId) {
  const cutoff = addDays(utcToday(), -SCOUTING_RECENCY_DAYS);
  const rows = await query(
    `SELECT metric_key, metric_value FROM scouting_observations
     WHERE planting_id = ? AND deleted_at IS NULL AND observed_at >= ?
     ORDER BY observed_at DESC`,
    [plantingId, cutoff]
  );
  const latest = {};
  for (const row of rows) {
    if (!Object.hasOwn(latest, row.metric_key)) latest[row.metric_key] = Number(row.metric_value);
  }
  return latest;
}

export async function runRecommendations() {
  const active = await query(
    "SELECT * FROM plantings WHERE status = 'active' AND deleted_at IS NULL"
  );

  // Gather every outbound/read input before opening the write transaction.
  const inputs = [];
  for (const planting of active) {
    const [field] = await query("SELECT * FROM fields WHERE id = ?", [planting.field_id]);
    const weather = await getWeatherSnapshot(Number(field.lat), Number(field.long));
    const scouting = await scoutingForPlanting(planting.id);
    inputs.push([planting, weather, scouting]);
  }

  let created = 0;
  await withTransaction(async (tx) => {
    for (const [planting, weather, scouting] of inputs) {
      created += await evaluatePlanting(planting, weather, scouting, tx);
    }
  });

  return { plantings_evaluated: active.length, recommendations_created: created };
}
