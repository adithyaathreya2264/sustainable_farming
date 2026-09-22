// Farmer-facing alert feed: recommendations + scheme matches, unified.
import { Router } from "express";
import { requireUser } from "../auth.js";
import { query, queryOne } from "../db.js";
import { HttpError } from "../errors.js";
import { pyCapitalize, pyRepr, pyStr } from "../pyRepr.js";
import { plantingOwner } from "../services/ownership.js";
import { toNaiveIso, utcnow } from "../time.js";
import { str, validateBody } from "../validate.js";

export const alertsRouter = Router();

const RECOMMENDATION_LABEL = { low: "unverified", medium: "unverified", verified: "verified" };
const SCHEME_LABEL = { provisional: "provisional", verified: "verified" };
const ALLOWED_STATUS = {
  recommendation: ["acknowledged", "followed", "ignored"],
  scheme_match: ["viewed", "dismissed", "claimed"],
};

const parseJson = (v) => (typeof v === "string" ? JSON.parse(v) : v);

/** eligibility_criteria JSON -> list of "Label: value" lines (Python str() formatting). */
export function flattenEligibility(criteria) {
  const lines = [];
  for (const [key, value] of Object.entries(criteria)) {
    const label = pyCapitalize(key.replaceAll("_", " "));
    if (Array.isArray(value)) {
      for (const item of value) lines.push(`${label}: ${pyStr(item)}`);
    } else {
      lines.push(`${label}: ${pyStr(value)}`);
    }
  }
  return lines;
}

function recommendationToAlert(rec) {
  return {
    id: rec.id,
    kind: "recommendation",
    severity: rec.severity,
    status: rec.status,
    headline: rec.recommendation_text,
    detail: null,
    confidence_label: RECOMMENDATION_LABEL[rec.confidence],
    application_url: null,
    authority: null,
    eligibility_summary: null,
    generated_at: toNaiveIso(rec.generated_at),
    planting_id: rec.planting_id,
  };
}

function schemeMatchToAlert(match, scheme) {
  return {
    id: match.id,
    kind: "scheme_match",
    severity: null,
    status: match.status,
    headline: scheme.scheme_name,
    detail: scheme.benefit_description,
    confidence_label: SCHEME_LABEL[match.match_confidence],
    application_url: scheme.application_url ?? null,
    authority: scheme.authority,
    eligibility_summary: flattenEligibility(parseJson(scheme.eligibility_criteria)),
    generated_at: toNaiveIso(match.matched_at),
    planting_id: null,
  };
}

alertsRouter.get("/", requireUser, async (req, res) => {
  const recommendations = await query(
    `SELECT r.* FROM recommendations r
       JOIN plantings p ON r.planting_id = p.id
       JOIN fields f ON p.field_id = f.id
     WHERE f.user_id = ? AND r.deleted_at IS NULL`,
    [req.user.id]
  );
  const matches = await query(
    "SELECT * FROM scheme_matches WHERE user_id = ? AND deleted_at IS NULL",
    [req.user.id]
  );
  const schemeIds = [...new Set(matches.map((m) => m.scheme_id))];
  const schemes = schemeIds.length
    ? await query("SELECT * FROM govt_schemes WHERE id IN (?)", [schemeIds])
    : [];
  const byId = new Map(schemes.map((s) => [s.id, s]));

  const items = [
    ...recommendations.map(recommendationToAlert),
    ...matches.filter((m) => byId.has(m.scheme_id)).map((m) => schemeMatchToAlert(m, byId.get(m.scheme_id))),
  ];
  items.sort((a, b) => (a.generated_at < b.generated_at ? 1 : a.generated_at > b.generated_at ? -1 : 0));
  res.json({ items });
});

alertsRouter.patch("/:kind/:alertId", requireUser, async (req, res) => {
  const { data } = validateBody([str("status", { required: true })], req.body);
  const { kind, alertId } = req.params;

  const allowed = ALLOWED_STATUS[kind];
  if (!allowed) throw new HttpError(404, "Unknown alert kind.");
  if (!allowed.includes(data.status)) {
    throw new HttpError(
      422,
      `Invalid status ${pyRepr(data.status)} for kind ${pyRepr(kind)}. Allowed: ${pyRepr([...allowed].sort())}.`
    );
  }

  if (kind === "recommendation") {
    const rec = await queryOne("SELECT * FROM recommendations WHERE id = ?", [alertId]);
    if (!rec || rec.deleted_at !== null) throw new HttpError(404, "Recommendation not found.");
    if ((await plantingOwner(rec.planting_id)) !== req.user.id) {
      throw new HttpError(403, "Not your data.");
    }
    const now = utcnow();
    await query(
      "UPDATE recommendations SET status = ?, responded_at = ?, updated_at = ? WHERE id = ?",
      [data.status, now, now, rec.id]
    );
    return res.json(recommendationToAlert({ ...rec, status: data.status }));
  }

  const match = await queryOne("SELECT * FROM scheme_matches WHERE id = ?", [alertId]);
  if (!match || match.deleted_at !== null) throw new HttpError(404, "Scheme match not found.");
  if (match.user_id !== req.user.id) throw new HttpError(403, "Not your data.");
  await query("UPDATE scheme_matches SET status = ?, updated_at = ? WHERE id = ?", [
    data.status,
    utcnow(),
    match.id,
  ]);
  const scheme = await queryOne("SELECT * FROM govt_schemes WHERE id = ?", [match.scheme_id]);
  return res.json(schemeMatchToAlert({ ...match, status: data.status }, scheme));
});
