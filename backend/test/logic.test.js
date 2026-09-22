// Pure-logic unit tests (no database, no network): `npm test`.
import assert from "node:assert/strict";
import { test } from "node:test";

process.env.DATABASE_URL ??= "mysql+pymysql://u:p@localhost:3306/x?charset=utf8mb4";
process.env.JWT_SECRET ??= "test-secret";
process.env.INTERNAL_API_KEY ??= "test-internal";

const { parseDatabaseUrl } = await import("../src/config.js");
const { ValidationFailure } = await import("../src/errors.js");
const { validateBody, str, float, bool, date, enumOf, listDict } = await import("../src/validate.js");
const { pyRepr, pyStr, pyCapitalize } = await import("../src/pyRepr.js");
const { flattenEligibility } = await import("../src/routes/alerts.js");
const { conditionMet, OPERATORS } = await import("../src/services/ruleEngine.js");
const { describe } = await import("../src/services/weatherReport.js");
const { getSoilType } = await import("../src/services/soilLookup.js");
const { currentGrowthStage } = await import("../src/services/growthStage.js");
const { addDays, daysBetween, utcToday, utcnow, toNaiveIso } = await import("../src/time.js");

const errorsOf = (fields, body) => {
  try {
    validateBody(fields, body);
  } catch (e) {
    assert.ok(e instanceof ValidationFailure);
    return e.errors;
  }
  return null;
};

test("DATABASE_URL: SQLAlchemy-style mysql+pymysql URL is parsed", () => {
  const c = parseDatabaseUrl("mysql+pymysql://sf_app:p%40ss@db.local:3307/sustainable-farming?charset=utf8mb4");
  assert.deepEqual(c, {
    host: "db.local",
    port: 3307,
    user: "sf_app",
    password: "p@ss",
    database: "sustainable-farming",
    charset: "utf8mb4",
  });
});

test("validation: missing / wrong type / pattern / max length / ge (pydantic shapes)", () => {
  const spec = [
    str("unique_id", { pattern: /^\d{4}$/, patternSource: "^\\d{4}$" }),
    str("name", { max: 3 }),
    float("area", { ge: 0 }),
    str("req", { required: true }),
  ];
  const errs = errorsOf(spec, { unique_id: "12a4", name: "abcd", area: -1 });
  assert.deepEqual(
    errs.map((e) => [e.type, e.loc.join("."), e.msg]),
    [
      ["string_pattern_mismatch", "body.unique_id", "String should match pattern '^\\d{4}$'"],
      ["string_too_long", "body.name", "String should have at most 3 characters"],
      ["greater_than_equal", "body.area", "Input should be greater than or equal to 0"],
      ["missing", "body.req", "Field required"],
    ]
  );
  assert.deepEqual(errorsOf(spec, undefined), [
    { type: "missing", loc: ["body"], msg: "Field required", input: null },
  ]);
  assert.equal(errorsOf(spec, [1])[0].type, "model_attributes_type");
  assert.equal(errorsOf([str("a", { required: true })], { a: 5 })[0].type, "string_type");
});

test("validation: exclude_unset semantics, explicit null, defaults, coercion", () => {
  const spec = [str("a"), float("b"), bool("c"), enumOf("s", ["x", "y"], { default: "x", nonNull: true })];
  const { data, present } = validateBody(spec, { a: null, b: "1.5", c: "yes" });
  assert.deepEqual(data, { a: null, b: 1.5, c: true, s: "x" });
  assert.deepEqual([...present].sort(), ["a", "b", "c"]);
  assert.equal(errorsOf(spec, { s: null })[0].type, "enum");
  assert.equal(errorsOf(spec, { s: "z" })[0].msg, "Input should be 'x' or 'y'");
});

test("validation: dates, lists, phone custom validator", () => {
  assert.equal(errorsOf([date("d")], { d: "2026-02-30" })[0].type, "date_from_datetime_parsing");
  assert.equal(errorsOf([date("d")], { d: "2026-09-21" }), null);
  assert.equal(errorsOf([listDict("b")], { b: [{}, 1] })[0].loc.join("."), "body.b.1");
  const phone = str("phone_number", {
    required: true,
    custom: (v) => {
      if (!/^(?:\+91|0)?\d{10}$/.test(v)) throw new Error("must be a valid 10-digit Indian mobile number");
      return v.slice(-10);
    },
  });
  assert.equal(validateBody([phone], { phone_number: "+919876543210" }).data.phone_number, "9876543210");
  const e = errorsOf([phone], { phone_number: "12" })[0];
  assert.equal(e.msg, "Value error, must be a valid 10-digit Indian mobile number");
  assert.deepEqual(e.ctx, { error: {} });
});

test("python repr/str formatting", () => {
  assert.equal(pyRepr("x"), "'x'");
  assert.equal(pyRepr("it's"), `"it's"`);
  assert.equal(pyRepr(["b", "a"].sort()), "['a', 'b']");
  assert.equal(pyStr(true), "True");
  assert.equal(pyStr(null), "None");
  assert.equal(pyCapitalize("land HOLDING"), "Land holding");
});

test("eligibility flattening matches the Python feed", () => {
  const lines = flattenEligibility({
    land_holding: "Cultivable land",
    exclusions: ["Income tax payers", "Institutional holders"],
    flag: true,
  });
  assert.deepEqual(lines, [
    "Land holding: Cultivable land",
    "Exclusions: Income tax payers",
    "Exclusions: Institutional holders",
    "Flag: True",
  ]);
});

test("rule engine: operators, scouting before weather, stage-only rules", () => {
  assert.ok(OPERATORS[">="](5, 5) && !OPERATORS[">"](5, 5) && OPERATORS["!="](1, 2));
  const rule = { condition_field: "dead_hearts_percent", operator: ">=", threshold_value: 5 };
  assert.deepEqual(conditionMet(rule, {}, { dead_hearts_percent: 8 }), [true, 8]);
  assert.deepEqual(conditionMet(rule, {}, { dead_hearts_percent: 4 }), [false, 4]);
  assert.deepEqual(conditionMet(rule, {}, {}), [false, null]);
  assert.deepEqual(conditionMet({ condition_field: null }, {}, {}), [true, null]);
  assert.deepEqual(conditionMet({ ...rule, operator: "??" }, {}, { dead_hearts_percent: 9 }), [false, null]);
  assert.throws(() => conditionMet(rule, { dead_hearts_percent: [1, 2] }, {}), TypeError);
});

test("growth stage: half-open windows, gaps, no stages", async () => {
  const stages = [
    { stage_name: "A", typical_days_from_sowing_start: 10, typical_days_from_sowing_end: 30 },
    { stage_name: "B", typical_days_from_sowing_start: 30, typical_days_from_sowing_end: 55 },
  ];
  const fake = { query: async () => stages };
  const at = (days) => ({ sowing_date: addDays(utcToday(), -days), crop_id: "c" });
  assert.equal(await currentGrowthStage(at(9), fake), null); // before first (gap)
  assert.equal(await currentGrowthStage(at(10), fake), "A");
  assert.equal(await currentGrowthStage(at(29), fake), "A");
  assert.equal(await currentGrowthStage(at(30), fake), "B"); // end is exclusive
  assert.equal(await currentGrowthStage(at(55), fake), null);
  assert.equal(await currentGrowthStage(at(20), { query: async () => [] }), null);
});

test("weather WMO mapping and soil lookup fallback", () => {
  assert.deepEqual(describe(0), ["clear", "Clear sky"]);
  assert.deepEqual(describe(99), ["thunderstorm", "Thunderstorm with heavy hail"]);
  assert.deepEqual(describe(4), ["unknown", "Unknown"]);
  assert.deepEqual(describe(null), ["unknown", "Unknown"]);
  assert.equal(getSoilType(" karnataka ", "MYSURU", "T. Narasipura").confidence, "taluk");
  assert.equal(getSoilType("Karnataka", "Mysuru", "Nowhere").soil_type, "Red Loamy Soil");
  assert.equal(getSoilType("Karnataka", "Belagavi").soil_type, "Black Soil");
  assert.equal(getSoilType("Kerala", "Idukki"), null);
});

test("naive-UTC time helpers", () => {
  assert.equal(addDays("2026-03-01", -1), "2026-02-28");
  assert.equal(daysBetween("2026-09-21", "2026-08-22"), 30);
  assert.match(utcnow(), /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/);
  assert.equal(toNaiveIso("2026-09-21 10:15:30"), "2026-09-21T10:15:30");
  assert.equal(toNaiveIso(null), null);
});
