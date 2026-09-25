// Read-only reference endpoints: soil-lookup, catalog, locations.
import { Router } from "express";
import { requireUser } from "../auth.js";
import { query } from "../db.js";
import { getSoilType } from "../services/soilLookup.js";
import { validateQuery } from "../validate.js";

export const soilRouter = Router(); // mounted at /api/v1
export const catalogRouter = Router(); // mounted at /api/v1/catalog
export const locationsRouter = Router(); // mounted at /api/v1/locations

soilRouter.get("/soil-lookup", requireUser, (req, res) => {
  const q = validateQuery(
    [
      { name: "state", required: true },
      { name: "district", required: true },
      { name: "taluk" },
    ],
    req.query
  );
  const result = getSoilType(q.state, q.district, q.taluk);
  res.json(
    result ?? { soil_type: null, confidence: "none", source: null }
  );
});

catalogRouter.get("/crops", requireUser, async (_req, res) => {
  // The Python query joined varieties and growth stages with
  // ORDER BY crop_varieties.name, crop_growth_stages.stage_order, which is what
  // ordered the crops in the response; reproduce that order.
  const ordering = await query(
    `SELECT c.id FROM crops c
       LEFT JOIN crop_varieties v ON c.id = v.crop_id
       LEFT JOIN crop_growth_stages g ON c.id = g.crop_id
     WHERE c.active = 1
     ORDER BY v.name, g.stage_order`
  );
  const orderedIds = [...new Set(ordering.map((o) => o.id))];
  const cropRows = await query("SELECT * FROM crops WHERE active = 1");
  const cropById = new Map(cropRows.map((c) => [c.id, c]));
  const crops = orderedIds.map((id) => cropById.get(id));
  const varieties = await query("SELECT * FROM crop_varieties ORDER BY name");
  const stages = await query("SELECT * FROM crop_growth_stages ORDER BY stage_order");
  const items = crops.map((c) => ({
    id: c.id,
    name: c.name,
    ml_key: c.ml_key ?? null,
    varieties: varieties
      .filter((v) => v.crop_id === c.id)
      .map((v) => ({ id: v.id, name: v.name })),
    growth_stages: stages
      .filter((s) => s.crop_id === c.id)
      .map((s) => ({
        stage_name: s.stage_name,
        stage_order: s.stage_order,
        typical_days_from_sowing_start: s.typical_days_from_sowing_start,
        typical_days_from_sowing_end: s.typical_days_from_sowing_end,
      })),
  }));
  res.json({ items });
});

catalogRouter.get("/agri-inputs", requireUser, async (_req, res) => {
  const rows = await query("SELECT * FROM agri_catalog WHERE active = 1");
  res.json({
    items: rows.map((r) => ({
      id: r.id,
      category: r.category,
      name: r.name,
      unit_of_measure: r.unit_of_measure,
      crop_applicability:
        typeof r.crop_applicability === "string"
          ? JSON.parse(r.crop_applicability)
          : r.crop_applicability ?? null,
      typical_dosage_per_hectare:
        r.typical_dosage_per_hectare === null ? null : Number(r.typical_dosage_per_hectare),
    })),
  });
});

locationsRouter.get("/", requireUser, async (_req, res) => {
  const rows = await query(
    "SELECT state, district FROM locations WHERE active = 1 ORDER BY state, district"
  );
  const grouped = new Map();
  for (const r of rows) {
    if (!grouped.has(r.state)) grouped.set(r.state, []);
    grouped.get(r.state).push(r.district);
  }
  res.json({
    items: [...grouped].map(([state, districts]) => ({ state, districts })),
  });
});

