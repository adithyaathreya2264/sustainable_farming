// Helpers that reproduce Python's str()/repr() text where the API exposes it.

export function pyStrRepr(s) {
  const useDouble = s.includes("'") && !s.includes('"');
  const quote = useDouble ? '"' : "'";
  let out = "";
  for (const ch of s) {
    if (ch === "\\") out += "\\\\";
    else if (ch === quote) out += `\\${ch}`;
    else if (ch === "\n") out += "\\n";
    else if (ch === "\r") out += "\\r";
    else if (ch === "\t") out += "\\t";
    else if (ch.codePointAt(0) < 0x20 || ch.codePointAt(0) === 0x7f) {
      out += `\\x${ch.codePointAt(0).toString(16).padStart(2, "0")}`;
    } else out += ch;
  }
  return quote + out + quote;
}

export function pyRepr(v) {
  if (v === null || v === undefined) return "None";
  if (v === true) return "True";
  if (v === false) return "False";
  if (typeof v === "string") return pyStrRepr(v);
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : String(v);
  if (Array.isArray(v)) return `[${v.map(pyRepr).join(", ")}]`;
  return `{${Object.entries(v)
    .map(([k, val]) => `${pyStrRepr(k)}: ${pyRepr(val)}`)
    .join(", ")}}`;
}

/** Python str(): like repr except top-level strings are unquoted. */
export function pyStr(v) {
  return typeof v === "string" ? v : pyRepr(v);
}

/** Python str.capitalize(): first char upper, the rest lower. */
export function pyCapitalize(s) {
  if (!s) return s;
  return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
}
