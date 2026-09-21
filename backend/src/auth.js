import jwt from "jsonwebtoken";
import { timingSafeEqual } from "node:crypto";
import { settings } from "./config.js";
import { queryOne } from "./db.js";
import { HttpError } from "./errors.js";

export function createAccessToken(userId, phoneNumber) {
  // PyJWT payload parity: user_id, phone_number, iat, exp (no `sub`).
  const iat = Math.floor(Date.now() / 1000);
  return jwt.sign(
    { user_id: userId, phone_number: phoneNumber, iat, exp: iat + settings.jwtExpiryMinutes * 60 },
    settings.jwtSecret,
    { algorithm: settings.jwtAlgorithm }
  );
}

const notAuthenticated = () =>
  new HttpError(401, "Not authenticated", { "WWW-Authenticate": "Bearer" });
const invalidCredentials = () =>
  new HttpError(401, "Invalid or expired credentials.", { "WWW-Authenticate": "Bearer" });

/** FastAPI HTTPBearer + get_current_user parity. Sets req.user (DB row). */
export async function requireUser(req, _res, next) {
  const header = req.headers.authorization;
  const m = header ? /^\s*(\S+)\s+(\S.*)$/.exec(header) : null;
  if (!m || m[1].toLowerCase() !== "bearer") throw notAuthenticated();
  let payload;
  try {
    payload = jwt.verify(m[2].trim(), settings.jwtSecret, {
      algorithms: [settings.jwtAlgorithm],
    });
  } catch {
    throw invalidCredentials();
  }
  if (!payload || !payload.user_id) throw invalidCredentials();
  const user = await queryOne("SELECT * FROM users WHERE id = ?", [payload.user_id]);
  if (!user) throw invalidCredentials();
  req.user = user;
  next();
}

/** X-Internal-Key guard (constant-time compare). */
export function requireInternalKey(req, _res, next) {
  const given = req.headers["x-internal-key"];
  let ok = false;
  if (typeof given === "string" && given.length > 0) {
    const a = Buffer.from(given);
    const b = Buffer.from(settings.internalApiKey);
    ok = a.length === b.length && timingSafeEqual(a, b);
  }
  if (!ok) throw new HttpError(403, "Invalid internal key.");
  next();
}
