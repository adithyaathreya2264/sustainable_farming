// Rule-based prescriptive engine. Every seeded rule is confidence != "verified",
// so every generated recommendation carries an explicit unverified prefix.
import { newId } from "../db.js";
import { utcnow } from "../time.js";
import { currentGrowthStage } from "./growthStage.js";

export const UNVERIFIED_PREFIX = "[Unverified guidance] ";

export const OPERATORS = {
  ">=": (a, b) => a >= b,
  "<=": (a, b) => a <= b,
  ">": (a, b) => a > b,
  "<": (a, b) => a < b,
  "==": (a, b) => a === b,
  "!=": (a, b) => a !== b,
};

/** Python float(): numbers and numeric strings only; anything else raises. */
function toFloat(v) {
  if (typeof v === "number") return v;
  if (typeof v === "boolean") return v ? 1 : 0;
  if (typeof v === "string" && v.trim() !== "" && !Number.isNaN(Number(v))) return Number(v);
  throw new TypeError(`float() argument must be a string or a real number`);
}

/** Returns [met, observedValue]. A stage-only rule (no condition_field) is always met. */
export function conditionMet(rule, weatherSnapshot, scoutingObservations) {
  if (rule.condition_field === null || rule.condition_field === undefined) return [true, null];

  let value;
  if (Object.hasOwn(scoutingObservations, rule.condition_field)) {
    value = scoutingObservations[rule.condition_field];
  } else if (Object.hasOwn(weatherSnapshot, rule.condition_field)) {
    value = weatherSnapshot[rule.condition_field];
  } else {
    return [false, null];
  }

  const comparator = OPERATORS[rule.operator];
  if (!comparator) return [false, null];
  return [Boolean(comparator(toFloat(value), toFloat(rule.threshold_value))), value];
}

/**
 * Evaluate one planting; inserts new Recommendation rows (via tx) and returns
 * how many were created.
 */
export async function evaluatePlanting(planting, weatherSnapshot, scoutingObservations, tx) {
  const stage = await currentGrowthStage(planting, tx);

  const rules = await tx.query(
    "SELECT * FROM agronomic_rules WHERE crop_id = ? AND active = 1",
    [planting.crop_id]
  );

  const created = [];
  for (const rule of rules) {
    if (stage === null || rule.stage_name !== stage) continue;

    const [met, observedValue] = conditionMet(rule, weatherSnapshot, scoutingObservations);
    if (!met) continue;

    // Idempotency: never stack duplicates while one is still pending.
    const pending = await tx.queryOne(
      `SELECT id FROM recommendations
       WHERE planting_id = ? AND rule_code = ? AND status = 'pending' AND deleted_at IS NULL`,
      [planting.id, rule.rule_code]
    );
    if (pending) continue;

    const text = rule.confidence !== "verified" ? UNVERIFIED_PREFIX + rule.recommendation_text : rule.recommendation_text;
    const snapshot = {
      stage,
      condition_field: rule.condition_field,
      observed_value: observedValue,
      threshold_value: rule.threshold_value !== null ? Number(rule.threshold_value) : null,
    };
    created.push({
      id: newId(),
      planting_id: planting.id,
      rule_code: rule.rule_code,
      trigger_snapshot: snapshot,
      recommendation_text: text,
      severity: rule.severity,
      confidence: rule.confidence,
    });
  }

  const now = utcnow();
  for (const rec of created) {
    await tx.query(
      `INSERT INTO recommendations (id, planting_id, rule_code, trigger_snapshot,
         recommendation_text, severity, confidence, status, generated_at, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)`,
      [rec.id, rec.planting_id, rec.rule_code, JSON.stringify(rec.trigger_snapshot),
       rec.recommendation_text, rec.severity, rec.confidence, now, now, now]
    );
  }
  return created.length;
}
