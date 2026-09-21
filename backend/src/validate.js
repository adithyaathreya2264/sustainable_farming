// A small declarative validator that reproduces pydantic v2's error shapes and
// lax coercion rules for the request models this API uses.
import { ValidationFailure } from "./errors.js";

const isObj = (v) => v !== null && typeof v === "object" && !Array.isArray(v);

function joinChoices(values) {
  const q = values.map((v) => `'${v}'`);
  return q.length === 1 ? q[0] : `${q.slice(0, -1).join(", ")} or ${q[q.length - 1]}`;
}

const BOOL_TRUE = new Set(["1", "true", "t", "yes", "y", "on"]);
const BOOL_FALSE = new Set(["0", "false", "f", "no", "n", "off"]);

function dateProblem(s) {
  if (s.length < 10) return "input is too short";
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (!m) return "invalid character in year";
  if (Number(m[2]) < 1 || Number(m[2]) > 12) return "month value is outside expected range of 1-12";
  return "day value is outside expected range";
}

function validDate(s) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return false;
  const d = new Date(`${s}T00:00:00Z`);
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === s;
}

/**
 * Coerce one value. Returns { ok: true, value } or { ok: false, errors }.
 * `spec.type`: str | float | bool | date | enum | list_dict.
 */
function coerce(spec, value, loc) {
  const err = (type, msg, ctx) => ({
    ok: false,
    errors: [{ type, loc, msg, input: value, ...(ctx ? { ctx } : {}) }],
  });

  switch (spec.type) {
    case "str": {
      if (typeof value !== "string") return err("string_type", "Input should be a valid string");
      if (spec.max !== undefined && value.length > spec.max) {
        return err(
          "string_too_long",
          `String should have at most ${spec.max} characters`,
          { max_length: spec.max }
        );
      }
      if (spec.pattern && !spec.pattern.test(value)) {
        return err(
          "string_pattern_mismatch",
          `String should match pattern '${spec.patternSource}'`,
          { pattern: spec.patternSource }
        );
      }
      if (spec.custom) {
        try {
          return { ok: true, value: spec.custom(value) };
        } catch (e) {
          return err("value_error", `Value error, ${e.message}`, { error: {} });
        }
      }
      return { ok: true, value };
    }
    case "float": {
      let n;
      if (typeof value === "number") n = value;
      else if (typeof value === "boolean") n = value ? 1 : 0;
      else if (typeof value === "string") {
        if (value.trim() === "" || Number.isNaN(Number(value))) {
          return err(
            "float_parsing",
            "Input should be a valid number, unable to parse string as a number"
          );
        }
        n = Number(value);
      } else return err("float_type", "Input should be a valid number");
      if (spec.ge !== undefined && n < spec.ge) {
        return err(
          "greater_than_equal",
          `Input should be greater than or equal to ${spec.ge}`,
          { ge: spec.ge }
        );
      }
      return { ok: true, value: n };
    }
    case "bool": {
      if (typeof value === "boolean") return { ok: true, value };
      if (value === 1 || value === 0) return { ok: true, value: value === 1 };
      if (typeof value === "string") {
        const s = value.trim().toLowerCase();
        if (BOOL_TRUE.has(s)) return { ok: true, value: true };
        if (BOOL_FALSE.has(s)) return { ok: true, value: false };
        return err("bool_parsing", "Input should be a valid boolean, unable to interpret input");
      }
      return err("bool_type", "Input should be a valid boolean");
    }
    case "date": {
      if (typeof value !== "string") return err("date_type", "Input should be a valid date");
      if (!validDate(value)) {
        const why = dateProblem(value);
        return err(
          "date_from_datetime_parsing",
          `Input should be a valid date or datetime, ${why}`,
          { error: why }
        );
      }
      return { ok: true, value };
    }
    case "enum": {
      if (typeof value !== "string" || !spec.values.includes(value)) {
        return err("enum", `Input should be ${joinChoices(spec.values)}`, {
          expected: joinChoices(spec.values),
        });
      }
      return { ok: true, value };
    }
    case "list_dict": {
      if (!Array.isArray(value)) return err("list_type", "Input should be a valid list");
      const errors = [];
      value.forEach((item, i) => {
        if (!isObj(item)) {
          errors.push({
            type: "dict_type",
            loc: [...loc, i],
            msg: "Input should be a valid dictionary",
            input: item,
          });
        }
      });
      return errors.length ? { ok: false, errors } : { ok: true, value };
    }
    default:
      throw new Error(`unknown spec type ${spec.type}`);
  }
}

/**
 * Validate a JSON body against `fields` (array of specs):
 *   { name, type, required?, default?, max?, ge?, pattern?, values?, custom? }
 * Optional fields (required !== true) accept null, like `T | None = None`.
 * Returns { data, present } — `data` holds only keys that were present in the
 * body (pydantic's exclude_unset), plus defaults for absent fields that have one.
 */
export function validateBody(fields, body) {
  if (body === undefined) {
    throw new ValidationFailure([
      { type: "missing", loc: ["body"], msg: "Field required", input: null },
    ]);
  }
  if (!isObj(body)) {
    throw new ValidationFailure([
      {
        type: "model_attributes_type",
        loc: ["body"],
        msg: "Input should be a valid dictionary or object to extract fields from",
        input: body,
      },
    ]);
  }
  const errors = [];
  const data = {};
  const present = new Set();
  for (const spec of fields) {
    const loc = ["body", spec.name];
    if (!(spec.name in body)) {
      if (spec.required) {
        errors.push({ type: "missing", loc, msg: "Field required", input: body });
      } else if ("default" in spec) {
        data[spec.name] = spec.default;
      }
      continue;
    }
    const raw = body[spec.name];
    if (raw === null && !spec.required && !spec.nonNull) {
      data[spec.name] = null;
      present.add(spec.name);
      continue;
    }
    const res = coerce(spec, raw, loc);
    if (res.ok) {
      data[spec.name] = res.value;
      present.add(spec.name);
    } else {
      errors.push(...res.errors);
    }
  }
  if (errors.length) throw new ValidationFailure(errors);
  return { data, present };
}

/** Validate query params: required strings, optional strings. */
export function validateQuery(specs, query) {
  const errors = [];
  const out = {};
  for (const spec of specs) {
    const v = query[spec.name];
    if (v === undefined) {
      if (spec.required) {
        errors.push({ type: "missing", loc: ["query", spec.name], msg: "Field required", input: null });
      } else out[spec.name] = null;
    } else out[spec.name] = Array.isArray(v) ? v[v.length - 1] : String(v);
  }
  if (errors.length) throw new ValidationFailure(errors);
  return out;
}

export const str = (name, o = {}) => {
  const spec = { name, type: "str", ...o };
  if (o.pattern) spec.patternSource = o.patternSource ?? o.pattern.source;
  return spec;
};
export const float = (name, o = {}) => ({ name, type: "float", ...o });
export const bool = (name, o = {}) => ({ name, type: "bool", ...o });
export const date = (name, o = {}) => ({ name, type: "date", ...o });
export const enumOf = (name, values, o = {}) => ({ name, type: "enum", values, ...o });
export const listDict = (name, o = {}) => ({ name, type: "list_dict", ...o });
