import { query } from "../db.js";
import { daysBetween, utcToday } from "../time.js";

/**
 * Current growth-stage name for a planting, or null. Stage windows are
 * half-open: start <= days_since_sowing < end. Null before the first stage,
 * after the last, in a gap, or when the crop has no stages.
 */
export async function currentGrowthStage(planting, q = { query }) {
  const days = daysBetween(utcToday(), planting.sowing_date);
  const stages = await q.query(
    "SELECT * FROM crop_growth_stages WHERE crop_id = ? ORDER BY stage_order",
    [planting.crop_id]
  );
  for (const s of stages) {
    if (s.typical_days_from_sowing_start <= days && days < s.typical_days_from_sowing_end) {
      return s.stage_name;
    }
  }
  return null;
}
