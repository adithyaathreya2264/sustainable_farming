import { Router } from "express";
import { requireUser } from "../auth.js";
import { query, queryOne, bool } from "../db.js";
import { HttpError } from "../errors.js";
import { utcnow } from "../time.js";
import { bool as boolSpec, float, str, validateBody } from "../validate.js";

export const usersRouter = Router();

export function profileOut(u) {
  return {
    id: u.id,
    phone_number: u.phone_number,
    unique_id: u.unique_id ?? null,
    name: u.name,
    language_pref: u.language_pref,
    default_unit: u.default_unit,
    total_area_hectares: Number(u.total_area_hectares),
    irrigation_type: u.irrigation_type,
    state: u.state,
    district: u.district,
    onboarding_complete: bool(u.onboarding_complete),
  };
}

const UPDATE_FIELDS = () => [
  str("unique_id", { pattern: /^\d{4}$/, patternSource: "^\\d{4}$" }),
  str("name", { max: 120 }),
  str("language_pref", { max: 8 }),
  str("default_unit", { max: 16 }),
  float("total_area_hectares", { ge: 0 }),
  str("irrigation_type", { max: 32 }),
  str("state", { max: 80 }),
  str("district", { max: 80 }),
  boolSpec("onboarding_complete"),
];

const UNIQUE_ID_TAKEN = () => new HttpError(409, "This unique number already exists.");

// pymysql raises IntegrityError for these MySQL error numbers; the Python
// endpoint translated any IntegrityError at commit into the 409 above.
const INTEGRITY_ERRNOS = new Set([1048, 1062, 1216, 1217, 1451, 1452]);

usersRouter.get("/me", requireUser, (req, res) => {
  res.json(profileOut(req.user));
});

usersRouter.patch("/me", requireUser, async (req, res) => {
  const { data } = validateBody(UPDATE_FIELDS(), req.body);
  const user = req.user;

  if (data.unique_id !== undefined && data.unique_id !== null) {
    const conflict = await queryOne(
      "SELECT id FROM users WHERE unique_id = ? AND id <> ?",
      [data.unique_id, user.id]
    );
    if (conflict) throw UNIQUE_ID_TAKEN();
  }

  const updatedAt = utcnow();
  const cols = Object.keys(data);
  const sets = [...cols.map((c) => `${c} = ?`), "updated_at = ?"];
  const params = [
    ...cols.map((c) => (typeof data[c] === "boolean" ? (data[c] ? 1 : 0) : data[c])),
    updatedAt,
    user.id,
  ];
  try {
    await query(`UPDATE users SET ${sets.join(", ")} WHERE id = ?`, params);
  } catch (err) {
    // Race-condition backstop (and Python parity: any IntegrityError -> 409).
    if (INTEGRITY_ERRNOS.has(err.errno)) throw UNIQUE_ID_TAKEN();
    throw err;
  }
  res.json(profileOut({ ...user, ...data, updated_at: updatedAt }));
});
