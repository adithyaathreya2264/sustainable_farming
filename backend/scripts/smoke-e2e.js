// End-to-end smoke test: frontend-shaped calls -> API -> DB -> response.
//
// Run from backend/:  npm run smoke
// By default starts the app in-process on an ephemeral port; set
// SMOKE_BASE_URL=http://localhost:8000 to hit an already-running server.
// Uses the real dev MySQL. Test users (phones 9123456780 / 9999999999) and all
// their rows are deleted on the way in and out. Login is mock (see MOCK_OTP).
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createApp } from "../src/app.js";
import { settings } from "../src/config.js";
import { pool, query } from "../src/db.js";
import { addDays, utcToday } from "../src/time.js";
import { UPLOADS_DIR } from "../src/routes/ml.js";
import { mlGet } from "../src/services/mlClient.js";

const FIXTURE_JPEG = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "test", "fixtures", "insect.jpg");

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

async function upload(path_, headers, fields) {
  const form = new FormData();
  form.append("photo", new Blob([fs.readFileSync(FIXTURE_JPEG)], { type: "image/jpeg" }), "p.jpg");
  for (const [k, v] of Object.entries(fields)) form.append(k, String(v));
  const res = await fetch(new URL(path_, BASE), { method: "POST", headers, body: form });
  const text = await res.text();
  let body;
  try {
    body = JSON.parse(text);
  } catch {
    body = undefined;
  }
  return { status: res.status, body, text };
}

// Invariants 1 and 3 of ml/README.md, checked on every ML response.
const leaks = (text) => /probabilit|"_raw|"score"/.test(text ?? "");

async function deleteUserRows(uid) {
  for (const row of await query("SELECT image_path FROM ml_inferences WHERE user_id = ? AND image_path IS NOT NULL", [uid])) {
    fs.rmSync(path.join(UPLOADS_DIR, ...row.image_path.split("/")), { force: true });
  }
  await query("DELETE FROM ml_inferences WHERE user_id = ?", [uid]);
  await query("DELETE FROM soil_tests WHERE field_id IN (SELECT id FROM fields WHERE user_id = ?)", [uid]);
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


  // --- 7a. ML serving (skipped when the sidecar is not running) ---
  const sidecarUp = await mlGet("/health").then(() => true, () => false);
  if (!sidecarUp) {
    console.log("ML sidecar not reachable: checking the degraded path only (start it with `npm run ml`)");
    r = await call("GET", "/api/v1/plantings/recommend-crop", { headers: H, params: { field_id: fieldId } });
    check("sidecar down -> recommend-crop 503 ml_unavailable", r.status === 503 && r.body?.reason === "ml_unavailable", `${r.status} ${r.text.slice(0, 120)}`);
    r = await call("GET", "/api/v1/ml/market/outlook", { headers: H, params: { commodity: "maize" } });
    check("sidecar down -> market 503, never 500", r.status === 503, String(r.status));
  } else {
    r = await call("GET", "/api/v1/plantings/recommend-crop", { headers: H, params: { field_id: fieldId } });
    check("recommend-crop 200", r.status === 200, `${r.status} ${r.text.slice(0, 200)}`);
    // "Red Sandy Loam" (a legacy free-text soil) maps to Red, so model 2 runs.
    check("recommend-crop uses the soil-type model", r.body?.basis === "soil_type" && r.body?.model === "crop_soil_type", r.body?.basis);
    check("recommend-crop entries carry confidence labels", Boolean(r.body?.recommended?.confidence_label));
    const unreachable = r.body?.unreachable_seeded_crops ?? [];
    check("model 2 reaches sugarcane but not ragi", !unreachable.includes("sugarcane") && unreachable.includes("ragi"), unreachable.join(","));
    check("recommend-crop no probability", !leaks(r.text));

    r = await call("GET", "/api/v1/ml/capabilities", { headers: H, params: { planting_id: plantingId } });
    const caps = r.body?.capabilities ?? {};
    check("capabilities 200 (rice)", r.status === 200 && caps.leaf_diagnosis?.available && caps.insect_detection?.available, r.text.slice(0, 200));
    check("rice leaf model is conditional", caps.leaf_diagnosis?.conditional === true);

    r = await call("GET", `/api/v1/ml/plantings/${plantingId}/fertilizer`, { headers: H });
    check("fertilizer 200 via state average", r.status === 200 && r.body?.available && r.body?.basis === "state_average", r.text.slice(0, 200));
    check("fertilizer products come from agri_catalog", Array.isArray(r.body?.products));

    r = await call("GET", `/api/v1/ml/plantings/${plantingId}/yield-outlook`, { headers: H });
    check("yield-outlook 200 with a band", r.status === 200 && typeof r.body?.position === "string", r.text.slice(0, 200));
    check("yield-outlook has no unit and no raw number", r.body?.unit === null && !leaks(r.text));

    r = await call("GET", `/api/v1/ml/plantings/${plantingId}/diseases`, { headers: H, params: { q: "brown spots on leaves" } });
    check("disease search 200 with matches", r.status === 200 && (r.body?.matches ?? []).length > 0, r.text.slice(0, 160));
    r = await call("GET", `/api/v1/ml/plantings/${plantingId}/diseases/all`, { headers: H });
    check("see-all-diseases path lists 8 rice diseases", (r.body?.diseases ?? []).length === 8);

    r = await call("GET", "/api/v1/ml/market/outlook", { headers: H, params: { commodity: "maize", district: "Davanagere" } });
    check("market outlook maize/Davanagere has a district forecast", r.body?.level === "district" && r.body?.forecast, r.text.slice(0, 160));
    r = await call("GET", "/api/v1/ml/market/outlook", { headers: H, params: { commodity: "paddy" } });
    check("market outlook paddy is outlook-only", r.status === 200 && r.body?.forecast === null);

    // Soil fertility (5b): none -> partial card -> full card.
    r = await call("GET", `/api/v1/ml/fields/${fieldId}/soil-fertility`, { headers: H });
    check("soil-fertility with no soil test -> no_soil_test", r.body?.reason === "no_soil_test", r.text.slice(0, 120));
    r = await call("POST", `/api/v1/fields/${fieldId}/soil-tests`, { headers: H, json: { nitrogen: 280, phosphorus: 22, potassium: 250, ph: 6.8 } });
    check("POST soil-tests 201", r.status === 201, `${r.status} ${r.text.slice(0, 120)}`);
    r = await call("GET", `/api/v1/ml/fields/${fieldId}/soil-fertility`, { headers: H });
    check("partial card -> incomplete_soil_test naming 8 values", r.body?.reason === "incomplete_soil_test" && r.body?.missing?.length === 8, r.text.slice(0, 160));
    r = await call("POST", `/api/v1/fields/${fieldId}/soil-tests`, {
      headers: H,
      json: { nitrogen: 280, phosphorus: 22, potassium: 250, ph: 6.8, ec: 0.4, organic_carbon: 0.62, sulphur: 12, zinc: 0.9, iron: 6.5, copper: 0.8, manganese: 5, boron: 0.6 },
    });
    r = await call("GET", `/api/v1/ml/fields/${fieldId}/soil-fertility`, { headers: H });
    check("full card -> fertility class, provenance flagged", ["low", "medium", "high"].includes(r.body?.fertility_class) && r.body?.provenance_verified === false && !leaks(r.text), r.text.slice(0, 160));
    r = await call("POST", `/api/v1/fields/${fieldId}/soil-tests`, { headers: H, json: { ph: 20 } });
    check("soil-test pH 20 -> 422", r.status === 422, String(r.status));

    r = await upload(`/api/v1/ml/plantings/${plantingId}/photo-check`, H, { kind: "insects" });
    check("photo-check insects 200", r.status === 200 && Array.isArray(r.body?.result?.detections), `${r.status} ${r.text.slice(0, 200)}`);
    const inferenceId = r.body?.inference_id;
    r = await upload(`/api/v1/ml/plantings/${plantingId}/photo-check`, H, { kind: "leaf" });
    check("photo-check leaf without symptom -> 422 symptom_required", r.status === 422 && r.body?.reason === "symptom_required", r.text);
    r = await upload(`/api/v1/ml/plantings/${plantingId}/photo-check`, H, { kind: "tobacco_lesions" });
    check("photo-check unavailable kind -> 409", r.status === 409, r.text);

    // Models 20-28: part checks through the leaf pipeline, and a held model.
    const catalog = (await call("GET", "/api/v1/catalog/crops", { headers: H })).body.items;
    const plantCrop = async (name) =>
      (await call("POST", "/api/v1/plantings", {
        headers: H,
        json: { field_id: fieldId, crop_id: catalog.find((c) => c.name === name).id, variety_id: null, sowing_date: sowing, status: "active" },
      })).body.id;
    const tomatoId = await plantCrop("Tomato");
    r = await call("GET", "/api/v1/ml/capabilities", { headers: H, params: { planting_id: tomatoId } });
    check("tomato offers fruit_grade (model 27)", r.body?.capabilities?.fruit_grade?.available === true, r.text.slice(0, 160));
    r = await upload(`/api/v1/ml/plantings/${tomatoId}/photo-check`, H, { kind: "fruit_grade" });
    check("fruit_grade upload -> a grade", r.status === 200 && r.body?.result?.condition?.category === "grade", `${r.status} ${r.text.slice(0, 160)}`);
    const wheatId = await plantCrop("Wheat");
    r = await call("GET", "/api/v1/ml/capabilities", { headers: H, params: { planting_id: wheatId } });
    check("wheat_kernels held (awaiting_lighting_check)", r.body?.capabilities?.wheat_kernels?.reason === "awaiting_lighting_check", r.text.slice(0, 200));
    check("wheat offers insect_detection (wheat thrips)", r.body?.capabilities?.insect_detection?.available === true, r.text.slice(0, 200));
    const before = (await call("GET", "/api/v1/ml/inferences", { headers: H })).body.items.length;
    r = await upload(`/api/v1/ml/plantings/${wheatId}/photo-check`, H, { kind: "wheat_kernels" });
    const after = (await call("GET", "/api/v1/ml/inferences", { headers: H })).body.items.length;
    check("held wheat_kernels upload -> 409, no photo stored", r.status === 409 && r.body?.reason === "awaiting_lighting_check" && after === before, `${r.status} ${r.text.slice(0, 160)}`);

    r = await call("GET", "/api/v1/ml/inferences", { headers: H, params: { planting_id: plantingId } });
    check("photo history lists the insect check", (r.body?.items ?? []).some((i) => i.id === inferenceId));
    const img = await fetch(new URL(`/api/v1/ml/inferences/${inferenceId}/image`, BASE), { headers: H });
    check("stored photo is retrievable by its owner", img.status === 200);
    r = await call("DELETE", `/api/v1/ml/inferences/${inferenceId}`, { headers: H });
    check("delete photo check 204", r.status === 204, String(r.status));
    const gone = await fetch(new URL(`/api/v1/ml/inferences/${inferenceId}/image`, BASE), { headers: H });
    check("deleted photo is gone", gone.status === 404, String(gone.status));
  }

  // --- 7b. another user's field is not editable ---
  await call("POST", "/api/v1/auth/request-otp", { json: { phone_number: OTHER_PHONE } });
  r = await call("POST", "/api/v1/auth/verify-otp", { json: { phone_number: OTHER_PHONE, otp: OTP } });
  const otherHeaders = { Authorization: `Bearer ${r.body.access_token}` };
  r = await call("PATCH", `/api/v1/fields/${fieldId}`, { headers: otherHeaders, json: { name: "Hijacked" } });
  check("PATCH someone else's field -> 403", r.status === 403, String(r.status));
  r = await upload(`/api/v1/ml/plantings/${plantingId}/photo-check`, otherHeaders, { kind: "insects" });
  check("photo-check on someone else's planting -> 403", r.status === 403, String(r.status));

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
