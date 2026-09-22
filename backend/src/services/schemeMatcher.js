// Government-scheme matching. v1: both matches are "provisional".
import { newId } from "../db.js";
import { utcnow } from "../time.js";

const ONE_ACRE_HECTARES = 0.4047;

// [scheme_name, predicate(user)]
const MATCHERS = [
  ["PM-KISAN (Pradhan Mantri Kisan Samman Nidhi)", (u) => Number(u.total_area_hectares) > 0],
  [
    "Krishi Bhagya Yojana",
    (u) => u.irrigation_type === "rainfed" && Number(u.total_area_hectares) >= ONE_ACRE_HECTARES,
  ],
];

/** Creates any missing matches for `user`; returns how many were created. */
export async function matchSchemes(user, tx) {
  let created = 0;
  for (const [schemeName, predicate] of MATCHERS) {
    const scheme = await tx.queryOne("SELECT * FROM govt_schemes WHERE scheme_name = ?", [schemeName]);
    if (!scheme || !scheme.active) continue;
    if (!predicate(user)) continue;

    const existing = await tx.queryOne(
      "SELECT id FROM scheme_matches WHERE user_id = ? AND scheme_id = ? AND deleted_at IS NULL",
      [user.id, scheme.id]
    );
    if (existing) continue;

    const now = utcnow();
    await tx.query(
      `INSERT INTO scheme_matches (id, user_id, scheme_id, matched_at, status,
         match_confidence, created_at, updated_at)
       VALUES (?, ?, ?, ?, 'matched', 'provisional', ?, ?)`,
      [newId(), user.id, scheme.id, now, now, now]
    );
    created += 1;
  }
  return created;
}
