// Phone + OTP auth. Login is permanently mock: verify-otp accepts the fixed
// MOCK_OTP for any phone number and still issues a real JWT.
import { Router } from "express";
import { settings } from "../config.js";
import { createAccessToken } from "../auth.js";
import { newId, query, queryOne } from "../db.js";
import { HttpError } from "../errors.js";
import { utcnow } from "../time.js";
import { str, validateBody } from "../validate.js";

const PHONE_RE = /^(?:\+91|0)?\d{10}$/;

function normalizePhone(v) {
  if (!PHONE_RE.test(v)) throw new Error("must be a valid 10-digit Indian mobile number");
  return v.slice(-10);
}

const phoneSpec = () => str("phone_number", { required: true, custom: normalizePhone });

export const authRouter = Router();

authRouter.post("/request-otp", (req, res) => {
  validateBody([phoneSpec()], req.body);
  res.json({ message: "OTP sent" });
});

authRouter.post("/verify-otp", async (req, res) => {
  const { data } = validateBody([phoneSpec(), str("otp", { required: true })], req.body);
  if (data.otp !== settings.mockOtp) {
    throw new HttpError(401, "Invalid or expired OTP.");
  }
  let user = await queryOne("SELECT * FROM users WHERE phone_number = ?", [data.phone_number]);
  if (!user) {
    const now = utcnow();
    user = {
      id: newId(),
      phone_number: data.phone_number,
    };
    await query(
      `INSERT INTO users (id, phone_number, name, language_pref, default_unit,
         total_area_hectares, irrigation_type, state, district, onboarding_complete,
         created_at, updated_at)
       VALUES (?, ?, '', 'en', 'hectare', 0, 'rainfed', '', '', 0, ?, ?)`,
      [user.id, user.phone_number, now, now]
    );
  }
  res.json({
    access_token: createAccessToken(user.id, user.phone_number),
    token_type: "bearer",
  });
});
