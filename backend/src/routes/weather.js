// GET /api/v1/weather — always 200; `available: false` on provider failure.
import { Router } from "express";
import { requireUser } from "../auth.js";
import { getWeatherReport } from "../services/weatherReport.js";
import { validateQuery } from "../validate.js";

export const weatherRouter = Router();

const CACHE_TTL_MS = 10 * 60 * 1000;
const cache = new Map(); // key -> [storedAtMs, report]

weatherRouter.get("/", requireUser, async (req, res) => {
  const q = validateQuery([{ name: "state" }, { name: "district" }], req.query);
  const state = (q.state || req.user.state || "").trim();
  const district = (q.district || req.user.district || "").trim();

  const key = `${state.toLowerCase()}\u0000${district.toLowerCase()}`;
  const now = performance.now();
  const hit = cache.get(key);
  if (hit && now - hit[0] < CACHE_TTL_MS) return res.json(hit[1]);

  const report = await getWeatherReport(state, district);
  // Only cache a real answer — a transient provider failure shouldn't stick.
  if (report.available) cache.set(key, [now, report]);
  return res.json(report);
});
