// Placeholder soil-type lookup with 3-tier fallback: taluk -> district -> none.
const ROWS = [
  { state: "Karnataka", district: "Mysuru", taluk: "Mysuru", soil_type: "Red Sandy Loam" },
  { state: "Karnataka", district: "Mysuru", taluk: "T. Narasipura", soil_type: "Red Loamy Soil" },
  { state: "Karnataka", district: "Mysuru", taluk: null, soil_type: "Red Loamy Soil" },
  { state: "Karnataka", district: "Mandya", taluk: "Mandya", soil_type: "Black Cotton Soil" },
  { state: "Karnataka", district: "Mandya", taluk: null, soil_type: "Black Cotton Soil" },
  { state: "Karnataka", district: "Belagavi", taluk: null, soil_type: "Black Soil" },
];

const norm = (v) => (v ? v.trim().toLowerCase() : null);

export function getSoilType(state, district, taluk = null) {
  const nState = norm(state);
  const nDistrict = norm(district);
  const nTaluk = norm(taluk);

  const districtRows = ROWS.filter(
    (r) => norm(r.state) === nState && norm(r.district) === nDistrict
  );
  if (districtRows.length === 0) return null;

  if (nTaluk) {
    const hit = districtRows.find((r) => norm(r.taluk) === nTaluk);
    if (hit) return { soil_type: hit.soil_type, confidence: "taluk", source: "placeholder" };
  }
  const row = districtRows.find((r) => r.taluk === null) ?? districtRows[0];
  return { soil_type: row.soil_type, confidence: "district", source: "placeholder" };
}
