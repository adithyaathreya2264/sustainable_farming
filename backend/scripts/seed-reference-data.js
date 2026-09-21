// Seed reference data: crops/varieties, agri input catalog, growth stages,
// agronomic rules, govt schemes, locations.
//
// Idempotent and insert-only — each row is looked up by its natural key first;
// existing rows are never modified. Source-of-truth data is versioned in the
// repo (scripts/reference-data.json and scripts/seed_data/locations.json).
//
// Usage (from backend/):  npm run seed
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { newId, pool, query, queryOne } from "../src/db.js";
import { utcnow } from "../src/time.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const ref = JSON.parse(fs.readFileSync(path.join(here, "reference-data.json"), "utf8"));
const locations = JSON.parse(
  fs.readFileSync(path.join(here, "seed_data", "locations.json"), "utf8")
);

async function getOrCreateCrop(name) {
  const existing = await queryOne("SELECT id FROM crops WHERE name = ?", [name]);
  if (existing) return existing.id;
  const id = newId();
  const now = utcnow();
  await query(
    "INSERT INTO crops (id, name, active, created_at, updated_at) VALUES (?, ?, 1, ?, ?)",
    [id, name, now, now]
  );
  return id;
}

async function getCropId(name) {
  const crop = await queryOne("SELECT id FROM crops WHERE name = ?", [name]);
  if (!crop) throw new Error(`crop '${name}' not seeded yet — run seedCrops() first`);
  return crop.id;
}

async function seedCrops() {
  for (const entry of ref.crops) {
    const cropId = await getOrCreateCrop(entry.name);
    for (const variety of entry.varieties) {
      const exists = await queryOne(
        "SELECT id FROM crop_varieties WHERE crop_id = ? AND name = ?",
        [cropId, variety]
      );
      if (!exists) {
        const now = utcnow();
        await query(
          "INSERT INTO crop_varieties (id, crop_id, name, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
          [newId(), cropId, variety, now, now]
        );
      }
    }
  }
}

async function seedAgriCatalog() {
  for (const e of ref.agri_catalog) {
    const exists = await queryOne("SELECT id FROM agri_catalog WHERE name = ? AND category = ?", [
      e.name,
      e.category,
    ]);
    if (exists) continue;
    const now = utcnow();
    await query(
      `INSERT INTO agri_catalog (id, category, name, crop_applicability, unit_of_measure,
         typical_dosage_per_hectare, active, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, NULL, 1, ?, ?)`,
      [newId(), e.category, e.name, JSON.stringify(e.crops), e.unit, now, now]
    );
  }
}

async function seedGrowthStages() {
  for (const [cropName, stageName, order, start, end] of ref.growth_stages) {
    const cropId = await getCropId(cropName);
    const exists = await queryOne(
      "SELECT id FROM crop_growth_stages WHERE crop_id = ? AND stage_name = ?",
      [cropId, stageName]
    );
    if (exists) continue;
    const now = utcnow();
    await query(
      `INSERT INTO crop_growth_stages (id, crop_id, stage_name, stage_order,
         typical_days_from_sowing_start, typical_days_from_sowing_end, confidence, source,
         created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'low', ?, ?, ?)`,
      [newId(), cropId, stageName, order, start, end, ref.growth_stage_source, now, now]
    );
  }
}

async function seedAgronomicRules() {
  for (const e of ref.agronomic_rules) {
    const exists = await queryOne("SELECT id FROM agronomic_rules WHERE rule_code = ?", [e.rule_code]);
    if (exists) continue;
    const now = utcnow();
    await query(
      `INSERT INTO agronomic_rules (id, rule_code, crop_id, stage_name, condition_field, operator,
         threshold_value, severity, recommendation_text, confidence, source, active,
         created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)`,
      [newId(), e.rule_code, await getCropId(e.crop), e.stage, e.condition_field, e.operator,
       e.threshold, e.severity, e.text, e.confidence, e.source, now, now]
    );
  }
}

async function seedGovtSchemes() {
  for (const e of ref.govt_schemes) {
    const exists = await queryOne("SELECT id FROM govt_schemes WHERE scheme_name = ?", [e.scheme_name]);
    if (exists) continue;
    const now = utcnow();
    await query(
      `INSERT INTO govt_schemes (id, scheme_name, authority, eligibility_criteria,
         benefit_description, application_url, active, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [newId(), e.scheme_name, e.authority, JSON.stringify(e.eligibility_criteria),
       e.benefit_description, e.application_url, e.active ? 1 : 0, now, now]
    );
  }
}

async function seedLocations() {
  const rows = await query("SELECT state, district FROM locations");
  const existing = new Set(rows.map((r) => `${r.state}\u0000${r.district}`));
  for (const entry of locations) {
    for (const district of entry.districts) {
      if (existing.has(`${entry.state}\u0000${district}`)) continue;
      const now = utcnow();
      await query(
        "INSERT INTO locations (id, state, district, active, created_at, updated_at) VALUES (?, ?, ?, 1, ?, ?)",
        [newId(), entry.state, district, now, now]
      );
    }
  }
}

async function count(table) {
  const row = await queryOne(`SELECT COUNT(*) AS n FROM \`${table}\``);
  return row.n;
}

try {
  await seedCrops();
  await seedAgriCatalog();
  await seedGrowthStages();
  await seedAgronomicRules();
  await seedGovtSchemes();
  await seedLocations();

  console.log(`crops: ${await count("crops")}`);
  console.log(`crop_varieties: ${await count("crop_varieties")}`);
  console.log(`agri_catalog: ${await count("agri_catalog")}`);
  console.log(`crop_growth_stages: ${await count("crop_growth_stages")}`);
  console.log(`agronomic_rules: ${await count("agronomic_rules")}`);
  console.log(`govt_schemes: ${await count("govt_schemes")}`);
  console.log(`locations: ${await count("locations")}`);
} finally {
  await pool.end();
}
