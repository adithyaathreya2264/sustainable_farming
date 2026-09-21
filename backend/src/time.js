// Naive-UTC datetime convention (see the Python backend's models/base.py utcnow):
// every DATETIME column holds UTC with no timezone, written/read as strings.

const pad = (n) => String(n).padStart(2, "0");

/** 'YYYY-MM-DD HH:MM:SS' (UTC), rounded to the second like MySQL DATETIME(0). */
export function utcnow() {
  const d = new Date(Math.round(Date.now() / 1000) * 1000);
  return (
    `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ` +
    `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`
  );
}

/** Today's UTC date as 'YYYY-MM-DD'. */
export function utcToday() {
  return utcnow().slice(0, 10);
}

/** 'YYYY-MM-DD' shifted by whole days (UTC-safe). */
export function addDays(dateStr, days) {
  const d = new Date(`${dateStr}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

/** Whole-day difference a - b for two 'YYYY-MM-DD' strings. */
export function daysBetween(a, b) {
  return Math.round(
    (Date.parse(`${a}T00:00:00Z`) - Date.parse(`${b}T00:00:00Z`)) / 86_400_000
  );
}

/** MySQL 'YYYY-MM-DD HH:MM:SS' -> naive ISO 'YYYY-MM-DDTHH:MM:SS' (what FastAPI emitted). */
export function toNaiveIso(dbDatetime) {
  return dbDatetime == null ? null : String(dbDatetime).replace(" ", "T");
}
