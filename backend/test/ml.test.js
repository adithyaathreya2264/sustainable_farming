// ML integration unit tests (no database, no real sidecar): `npm test`.
// A throwaway HTTP server stands in for ml/serving so mlClient's error mapping
// is tested against real sockets, timeouts and refused connections.
import assert from "node:assert/strict";
import http from "node:http";
import { after, before, test } from "node:test";

process.env.DATABASE_URL ??= "mysql+pymysql://u:p@localhost:3306/x?charset=utf8mb4";
process.env.JWT_SECRET ??= "test-secret";
process.env.INTERNAL_API_KEY ??= "test-internal";

const fake = http.createServer((req, res) => {
  const send = (status, body) => {
    res.writeHead(status, { "Content-Type": "application/json" });
    res.end(JSON.stringify(body));
  };
  if (req.url.startsWith("/ok")) return send(200, { answer: 42, echo: req.url });
  if (req.url.startsWith("/refused")) return send(409, { reason: "model_did_not_ship", detail: "no" });
  if (req.url.startsWith("/invalid")) return send(422, { reason: "invalid_image", detail: "bad" });
  if (req.url.startsWith("/boom")) return send(500, { reason: "inference_failed" });
  if (req.url.startsWith("/upload")) {
    let size = 0;
    req.on("data", (c) => (size += c.length));
    req.on("end", () => send(200, { content_type: req.headers["content-type"], size }));
    return;
  }
  if (req.url.startsWith("/hang")) return; // never answers
  send(404, {});
});

let ml;
let HttpError;
before(async () => {
  await new Promise((r) => fake.listen(0, "127.0.0.1", r));
  process.env.ML_SIDECAR_URL = `http://127.0.0.1:${fake.address().port}`;
  ml = await import("../src/services/mlClient.js");
  ({ HttpError } = await import("../src/errors.js"));
});
after(() => {
  fake.closeAllConnections();
  fake.close();
});

const rejectsWith = async (promise, status, reason) => {
  await assert.rejects(promise, (err) => {
    assert.ok(err instanceof HttpError);
    assert.equal(err.status, status);
    assert.equal(err.extra.reason, reason);
    return true;
  });
};

test("mlClient: success returns the JSON body, query params encoded", async () => {
  const body = await ml.mlGet("/ok", { crop: "pearl millet", empty: "", missing: undefined });
  assert.equal(body.answer, 42);
  assert.equal(body.echo, "/ok?crop=pearl+millet");
});

test("mlClient: 409 stays a 409 with reason model_did_not_ship", async () => {
  await rejectsWith(ml.mlPost("/refused", {}), 409, "model_did_not_ship");
});

test("mlClient: 422 passes through with the sidecar's reason", async () => {
  await rejectsWith(ml.mlGet("/invalid"), 422, "invalid_image");
});

test("mlClient: sidecar 5xx becomes 503 ml_unavailable, never a 500", async () => {
  await rejectsWith(ml.mlGet("/boom"), 503, "ml_unavailable");
});

test("mlClient: refused connection becomes 503 ml_unavailable", async () => {
  const closed = http.createServer();
  await new Promise((r) => closed.listen(0, "127.0.0.1", r));
  const port = closed.address().port;
  await new Promise((r) => closed.close(r));
  const saved = process.env.ML_SIDECAR_URL;
  process.env.ML_SIDECAR_URL = `http://127.0.0.1:${port}`;
  try {
    await rejectsWith(ml.mlGet("/ok"), 503, "ml_unavailable");
  } finally {
    process.env.ML_SIDECAR_URL = saved;
  }
});

test("mlClient: image upload is multipart with the photo and fields", async () => {
  const body = await ml.mlImage("/upload", Buffer.from([0xff, 0xd8, 0xff, 1, 2, 3]), "image/jpeg", {
    crop: "rice",
    symptom_reported: true,
  });
  assert.match(body.content_type, /^multipart\/form-data; boundary=/);
  assert.ok(body.size > 6);
});

test("mlClient: a hung sidecar times out into 503", { timeout: 30_000 }, async () => {
  const realTimeout = AbortSignal.timeout;
  AbortSignal.timeout = () => realTimeout.call(AbortSignal, 200);
  try {
    await rejectsWith(ml.mlGet("/hang"), 503, "ml_unavailable");
  } finally {
    AbortSignal.timeout = realTimeout;
  }
});

// --- pure input mappings ---------------------------------------------------

const {
  appSoilKeyFromPhoto,
  seasonFromSowingDate,
  soilKeyFromField,
  soilTestToSample,
  soilTypeToModelVocab,
} = await import("../src/services/mlInputs.js");

test("soil type: app keys and legacy English labels map; others do not guess", () => {
  assert.equal(soilTypeToModelVocab("black"), "Black");
  assert.equal(soilTypeToModelVocab("Black / Regur"), "Black");
  assert.equal(soilTypeToModelVocab("arid"), "Arid and Desert");
  assert.equal(soilTypeToModelVocab("Laterite"), "Laterite");
  assert.equal(soilTypeToModelVocab("saline"), null);
  assert.equal(soilTypeToModelVocab("peaty"), null);
  assert.equal(soilTypeToModelVocab("ಕಪ್ಪು ಮಣ್ಣು"), null);
  assert.equal(soilTypeToModelVocab(null), null);
  assert.equal(soilKeyFromField("Red soil"), "red");
});

test("soil photo classes map to app keys; cinder has no equivalent", () => {
  assert.equal(appSoilKeyFromPhoto("Black Soil"), "black");
  assert.equal(appSoilKeyFromPhoto("Cinder Soil"), null);
});

test("season from sowing month", () => {
  assert.equal(seasonFromSowingDate("2026-07-01", "rice"), "Kharif");
  assert.equal(seasonFromSowingDate("2026-11-15", "wheat"), "Rabi");
  assert.equal(seasonFromSowingDate("2027-01-10", "wheat"), "Rabi");
  assert.equal(seasonFromSowingDate("2026-03-01", "maize"), "Summer");
  assert.equal(seasonFromSowingDate("2026-03-01", "sugarcane"), "Whole Year");
});

test("soil test -> sample only when all four readings exist", () => {
  assert.deepEqual(soilTestToSample({ nitrogen: "40.000", phosphorus: 30, potassium: 20, ph: "6.20" }), {
    N: 40,
    P: 30,
    K: 20,
    pH: 6.2,
  });
  assert.equal(soilTestToSample({ nitrogen: 40, phosphorus: null, potassium: 20, ph: 6 }), null);
  assert.equal(soilTestToSample(null), null);
});

// --- soil-test card (model 5b) ------------------------------------------------

const { soilTestToCard } = await import("../src/services/mlInputs.js");
const { parseSoilTest, SOIL_TEST_COLUMNS } = await import("../src/routes/fields.js");

const FULL_ROW = {
  nitrogen: "280.000", phosphorus: 22, potassium: 250, ph: "6.80", ec: 0.4, organic_carbon: 0.62,
  sulphur: 12, zinc: 0.9, iron: 6.5, copper: 0.8, manganese: 5, boron: 0.6,
};

test("soil card: a full test maps to the model's 12 features", () => {
  const { card, missing } = soilTestToCard(FULL_ROW);
  assert.deepEqual(missing, []);
  assert.deepEqual(Object.keys(card), ["N", "P", "K", "pH", "EC", "OC", "S", "Zn", "Fe", "Cu", "Mn", "B"]);
  assert.equal(card.N, 280);
  assert.equal(card.pH, 6.8);
});

test("soil card: missing values are named, never filled in", () => {
  const { missing } = soilTestToCard({ nitrogen: 280, phosphorus: 22, potassium: 250, ph: 6.8 });
  assert.deepEqual(missing, ["ec", "organic_carbon", "sulphur", "zinc", "iron", "copper", "manganese", "boron"]);
});

test("parseSoilTest: accepts all 12 columns, rejects negatives and pH > 14", () => {
  assert.equal(SOIL_TEST_COLUMNS.length, 12);
  assert.deepEqual(parseSoilTest({ nitrogen: "40", zinc: "" }), {
    ...Object.fromEntries(SOIL_TEST_COLUMNS.map((c) => [c, null])),
    nitrogen: 40,
  });
  assert.equal(parseSoilTest({}), null);
  assert.throws(() => parseSoilTest({ zinc: -1 }), HttpError);
  assert.throws(() => parseSoilTest({ ph: 15 }), HttpError);
  assert.throws(() => parseSoilTest([1]), HttpError);
});
