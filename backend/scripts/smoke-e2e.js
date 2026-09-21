// End-to-end smoke test: frontend-shaped calls -> API -> DB -> response.
//
// Run from backend/:  npm run smoke
// By default starts the app in-process on an ephemeral port; set
// SMOKE_BASE_URL=http://localhost:8000 to hit an already-running server.
// Uses the real dev MySQL. Test users (phones 9123456780 / 9999999999) and all
// their rows are deleted on the way in and out. Login is mock (see MOCK_OTP).
import { createApp } from "../src/app.js";
import { settings } from "../src/config.js";
import { pool, query } from "../src/db.js";
import { addDays, utcToday } from "../src/time.js";

const PHONE = "9123456780";
const OTHER_PHONE = "9999999999";
const OTP = settings.mockOtp;

let server = null;
let BASE = process.env.SMOKE_BASE_URL;
if (!BASE) {
  server = await new Promise((resolve) => {
    const s = createApp().listen(0, "127.0.0.1", () => resolve(s));
  });
  BASE = `http://127.0.0.1:${server.address().port}`;
}

const results = [];
function check(name, cond, extra = "") {
  results.push([name, Boolean(cond), extra]);
  console.log(`${cond ? "PASS " : "FAIL "}${name}${extra ? `  ${extra}` : ""}`);
}

async function call(method, path, { headers = {}, json, params } = {}) {
  const url = new URL(path, BASE);
  if (params) for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
  const res = await fetch(url, {
    method,
    headers: { ...(json !== undefined ? { "content-type": "application/json" } : {}), ...headers },
    body: json !== undefined ? JSON.stringify(json) : undefined,
  });
  const text = await res.text();
  let body;
  try {
    body = text ? JSON.parse(text) : undefined;
  } catch {
    body = undefined;
  }
  return { status: res.status, body, text };
}

async function deleteUserRows(uid) {
  const sub = "(SELECT p.id FROM plantings p JOIN fields f ON p.field_id = f.id WHERE f.user_id = ?)";
  await query("DELETE FROM scheme_matches WHERE user_id = ?", [uid]);
  await query(`DELETE FROM recommendations WHERE planting_id IN ${sub}`, [uid]);
  await query(`DELETE FROM scouting_observations WHERE planting_id IN ${sub}`, [uid]);
  await query(`DELETE FROM interventions WHERE planting_id IN ${sub}`, [uid]);
  await query("DELETE FROM plantings WHERE field_id IN (SELECT id FROM fields WHERE user_id = ?)", [uid]);
  await query("DELETE FROM fields WHERE user_id = ?", [uid]);
  await query("DELETE FROM users WHERE id = ?", [uid]);
}

async function cleanupPhone(phone) {
  const rows = await query("SELECT id FROM users WHERE phone_number = ?", [phone]);
  for (const r of rows) await deleteUserRows(r.id);
}

try {
  // --- cleanup any prior run ---
  await cleanupPhone(PHONE);
  await cleanupPhone(OTHER_PHONE);

  // --- 1. auth ---
  let r = await call("POST", "/api/v1/auth/request-otp", { json: { phone_number: PHONE } });
  check("request-otp 200", r.status === 200, String(r.status));

  r = await call("POST", "/api/v1/auth/verify-otp", { json: { phone_number: PHONE, otp: OTP } });
  check("verify-otp 200", r.status === 200, String(r.status));
  const token = r.body?.access_token;
  check("verify-otp returns JWT", Boolean(token));
  const H = { Authorization: `Bearer ${token}` };

  // --- 2. GET /users/me ---
  r = await call("GET", "/api/v1/users/me", { headers: H });
  check("GET /users/me 200", r.status === 200, String(r.status));
  const me = r.body;
  check("profile fresh: onboarding_complete False", me?.onboarding_complete === false);
  check("profile id is a real uuid", me?.id && me.id !== "u1");
  const realUid = me.id;

  // --- 3. PATCH /users/me ---
  r = await call("PATCH", "/api/v1/users/me", {
    headers: H,
    json: {
      name: "Smoke Farmer",
      language_pref: "kn",
      default_unit: "acre",
      total_area_hectares: 1.2,
      irrigation_type: "rainfed",
      state: "Karnataka",
      district: "Mysuru",
      onboarding_complete: true,
    },
  });
  check("PATCH /users/me 200", r.status === 200, String(r.status));
  check("PATCH persisted onboarding_complete", r.body?.onboarding_complete === true);
  check("PATCH persisted name", r.body?.name === "Smoke Farmer");

  r = await call("PATCH", "/api/v1/users/me", { headers: H, json: { default_unit: "hectare" } });
  check(
    "PATCH partial keeps other fields",
    r.body?.name === "Smoke Farmer" && r.body?.default_unit === "hectare"
  );

  // --- 3b. weather (live Open-Meteo) ---
  r = await call("GET", "/api/v1/weather", { headers: H });
  check("GET /weather 200", r.status === 200, String(r.status));
  const w = r.body ?? {};
  check("weather available for Karnataka/Mysuru", w.available === true, JSON.stringify(w).slice(0, 160));
  check(
    "weather has a temperature + location label",
    w.temperature_c != null && (w.location_label || "").includes("Mysuru")
  );
  check("weather has a multi-day forecast", (w.forecast || []).length >= 2);
  r = await call("GET", "/api/v1/weather", { headers: H, params: { state: "Punjab", district: "Amritsar" } });
  check("GET /weather with override 200 + available", r.status === 200 && r.body?.available === true);

  // --- 3c. locations ---
  r = await call("GET", "/api/v1/locations", { headers: H });
  check("GET /locations 200", r.status === 200, String(r.status));
  const locItems = r.body?.items ?? [];
  check("locations grouped by state, non-empty", locItems.length > 20);
  const ka = locItems.find((g) => g.state === "Karnataka");
  check("Karnataka present with districts incl. Mysuru", ka && ka.districts.includes("Mysuru"));

  // --- 4. soil lookup ---
  r = await call("GET", "/api/v1/soil-lookup", { headers: H, params: { state: "Karnataka", district: "Mysuru" } });
  check("soil-lookup 200", r.status === 200, String(r.status));
  check("soil-lookup has confidence", ["taluk", "district", "none"].includes(r.body?.confidence));

  // --- 5. catalog ---
  r = await call("GET", "/api/v1/catalog/crops", { headers: H });
  check("catalog/crops 200 + non-empty", r.status === 200 && r.body.items.length > 0);
  const crop = r.body.items.find((c) => c.name === "Rice") ?? r.body.items[0];
  check(
    "catalog/crops includes growth_stages",
    (crop.growth_stages || []).length >= 2,
    JSON.stringify(crop.growth_stages).slice(0, 120)
  );
  r = await call("GET", "/api/v1/catalog/agri-inputs", { headers: H });
  check("catalog/agri-inputs 200 + non-empty", r.status === 200 && r.body.items.length > 0);

  // --- 6. create field + planting + scouting observation ---
  // Sowing 30 days ago -> Rice is in "Vegetative (Tillering)" (days 20-45),
  // the stage RICE_STEM_BORER_SCOUT gates on.
  const sowing = addDays(utcToday(), -30);

  r = await call("POST", "/api/v1/fields", {
    headers: H,
    json: {
      name: "North Plot",
      area_size_hectares: 1.2,
      lat: 12.3,
      long: 76.65,
      boundary: [
        { lat: 12.3, long: 76.65 },
        { lat: 12.31, long: 76.66 },
        { lat: 12.3, long: 76.67 },
      ],
      soil_type: "Red Sandy Loam",
    },
  });
  check("POST /fields 201", r.status === 201, `${r.status} ${r.text.slice(0, 200)}`);
  const fieldId = r.body.id;
  check("created field owned by real uid", r.body.user_id === realUid);

  r = await call("POST", "/api/v1/plantings", {
    headers: H,
    json: {
      field_id: fieldId,
      crop_id: crop.id,
      variety_id: crop.varieties.length ? crop.varieties[0].id : null,
      sowing_date: sowing,
      status: "active",
    },
  });
  check("POST /plantings 201", r.status === 201, `${r.status} ${r.text.slice(0, 200)}`);
  const plantingId = r.body.id;

  r = await call("POST", "/api/v1/scouting-observations", {
    headers: H,
    json: {
      planting_id: plantingId,
      metric_key: "dead_hearts_percent",
      metric_value: 8,
      observed_at: utcToday(),
      notes: "smoke test",
    },
  });
  check("POST /scouting-observations 201", r.status === 201, `${r.status} ${r.text.slice(0, 200)}`);
  const scoutingId = r.body.id;

  // --- 7. GET each resource sees it back, scoped to the real user ---
  r = await call("GET", "/api/v1/fields", { headers: H });
  check("GET /fields 200", r.status === 200, String(r.status));
  check(
    "listed field owned by real uid",
    r.body.items.some((f) => f.id === fieldId && f.user_id === realUid)
  );
  r = await call("GET", "/api/v1/scouting-observations", { headers: H });
  check("GET /scouting-observations includes the new one", r.body.items.some((o) => o.id === scoutingId));

  // --- 7b. another user's field is not editable ---
  await call("POST", "/api/v1/auth/request-otp", { json: { phone_number: OTHER_PHONE } });
  r = await call("POST", "/api/v1/auth/verify-otp", { json: { phone_number: OTHER_PHONE, otp: OTP } });
  const otherHeaders = { Authorization: `Bearer ${r.body.access_token}` };
  r = await call("PATCH", `/api/v1/fields/${fieldId}`, { headers: otherHeaders, json: { name: "Hijacked" } });
  check("PATCH someone else's field -> 403", r.status === 403, String(r.status));

  // --- 7c. unique_id: settable, globally unique, format-validated ---
  r = await call("PATCH", "/api/v1/users/me", { headers: H, json: { unique_id: "1234" } });
  check("PATCH unique_id 200", r.status === 200 && r.body?.unique_id === "1234", String(r.status));
  r = await call("PATCH", "/api/v1/users/me", { headers: otherHeaders, json: { unique_id: "1234" } });
  check("PATCH duplicate unique_id -> 409", r.status === 409, `${r.status} ${r.text.slice(0, 160)}`);
  r = await call("PATCH", "/api/v1/users/me", { headers: otherHeaders, json: { unique_id: "5678" } });
  check("PATCH different unique_id 200", r.status === 200 && r.body?.unique_id === "5678", String(r.status));
  r = await call("PATCH", "/api/v1/users/me", { headers: otherHeaders, json: { unique_id: "12a4" } });
  check("PATCH non-digit unique_id -> 422", r.status === 422, String(r.status));
  await cleanupPhone(OTHER_PHONE);

  // --- 8. scheme matching (internal key) ---
  const IK = { "X-Internal-Key": settings.internalApiKey };
  r = await call("POST", "/api/v1/internal/run-scheme-matching", { headers: IK });
  check("run-scheme-matching 200", r.status === 200, `${r.status} ${r.text.slice(0, 200)}`);
  check(
    "run-scheme-matching created >=1 match for onboarded user",
    (r.body?.matches_created ?? 0) >= 1,
    r.text
  );

  // --- 9. recommendations (twice — idempotent) ---
  r = await call("POST", "/api/v1/internal/run-recommendations", { headers: IK });
  check("run-recommendations 200", r.status === 200, `${r.status} ${r.text.slice(0, 200)}`);
  check("run-recommendations fired the scouting rule", (r.body?.recommendations_created ?? 0) >= 1, r.text);
  const r2 = await call("POST", "/api/v1/internal/run-recommendations", { headers: IK });
  check(
    "run-recommendations idempotent (no new rows on 2nd run)",
    (r2.body?.recommendations_created ?? 0) === 0,
    r2.text
  );

  // --- 10. alerts ---
  r = await call("GET", "/api/v1/alerts", { headers: H });
  check("GET /alerts 200", r.status === 200, String(r.status));
  const items = r.body.items;
  const schemeAlerts = items.filter((a) => a.kind === "scheme_match");
  const recAlerts = items.filter((a) => a.kind === "recommendation");
  check("alert feed has the scheme match", schemeAlerts.length >= 1, `${items.length} items`);
  check(
    "alert feed has a recommendation (scouting rule fired end-to-end)",
    recAlerts.length >= 1,
    `${items.length} items`
  );

  // --- 11. PATCH alert status ---
  if (schemeAlerts.length) {
    const aid = schemeAlerts[0].id;
    r = await call("PATCH", `/api/v1/alerts/scheme_match/${aid}`, { headers: H, json: { status: "viewed" } });
    check("PATCH alert -> viewed 200", r.status === 200 && r.body?.status === "viewed", String(r.status));
    r = await call("PATCH", `/api/v1/alerts/scheme_match/${aid}`, { headers: H, json: { status: "bogus" } });
    check("PATCH alert invalid status -> 422", r.status === 422, String(r.status));
  }

  // --- 12. auth required ---
  r = await call("GET", "/api/v1/users/me");
  check("GET /users/me without token -> 401/403", [401, 403].includes(r.status), String(r.status));

  // --- cleanup ---
  await deleteUserRows(realUid);
} finally {
  if (server) await new Promise((resolve) => server.close(resolve));
  await pool.end();
}

const failed = results.filter(([, c]) => !c).map(([n]) => n);
console.log();
console.log(`${results.length - failed.length}/${results.length} passed`);
if (failed.length) {
  console.log("FAILED:", failed);
  process.exit(1);
}
