"""End-to-end smoke test: frontend-shaped calls -> API -> DB -> response.

Exercises the full integration chain the way the Expo app hits it: OTP auth,
the user-profile round-trip (GET/PATCH /api/v1/users/me), soil lookup, catalog,
a co-created field+planting sync push/pull, the internal recommendation/scheme
batch runs, and the alert feed + status PATCH.

Run from the repo root against the dev MySQL:
    PYTHONPATH=. backend/venv/Scripts/python backend/scripts/smoke_e2e.py

SMS sending and OTP generation are monkeypatched (no Fast2SMS call). The test
user (phone 9123456780) and all its rows are deleted on the way in and out.
"""
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text

import backend.api.v1.auth as auth_mod
from backend.core.config import settings
from backend.core.database import SessionLocal
from backend.main import app

PHONE = "9123456780"
OTP = "123456"

auth_mod.generate_otp = lambda: OTP
auth_mod.send_otp_sms = lambda phone, otp: True

client = TestClient(app)
results = []


def check(name, cond, extra=""):
    results.append((name, cond, extra))
    print(("PASS " if cond else "FAIL ") + name + (f"  {extra}" if extra else ""))


# --- cleanup any prior run ---
with SessionLocal() as db:
    uid = db.execute(text("select id from users where phone_number=:p"), {"p": PHONE}).scalar()
    if uid:
        db.execute(text("delete from scheme_matches where user_id=:u"), {"u": uid})
        db.execute(text("delete from recommendations where planting_id in (select p.id from plantings p join fields f on p.field_id=f.id where f.user_id=:u)"), {"u": uid})
        db.execute(text("delete from scouting_observations where planting_id in (select p.id from plantings p join fields f on p.field_id=f.id where f.user_id=:u)"), {"u": uid})
        db.execute(text("delete from interventions where planting_id in (select p.id from plantings p join fields f on p.field_id=f.id where f.user_id=:u)"), {"u": uid})
        db.execute(text("delete from plantings where field_id in (select id from fields where user_id=:u)"), {"u": uid})
        db.execute(text("delete from fields where user_id=:u"), {"u": uid})
        db.execute(text("delete from users where id=:u"), {"u": uid})
    db.execute(text("delete from otp_requests where phone_number=:p"), {"p": PHONE})
    db.commit()

# --- 1. auth: request + verify OTP ---
r = client.post("/api/v1/auth/request-otp", json={"phone_number": PHONE})
check("request-otp 200", r.status_code == 200, str(r.status_code))

r = client.post("/api/v1/auth/verify-otp", json={"phone_number": PHONE, "otp": OTP})
check("verify-otp 200", r.status_code == 200, str(r.status_code))
token = r.json().get("access_token")
check("verify-otp returns JWT", bool(token))
H = {"Authorization": f"Bearer {token}"}

# --- 2. GET /users/me (new endpoint) ---
r = client.get("/api/v1/users/me", headers=H)
check("GET /users/me 200", r.status_code == 200, str(r.status_code))
me = r.json()
check("profile fresh: onboarding_complete False", me.get("onboarding_complete") is False)
check("profile id is a real uuid", me.get("id") not in (None, "u1"))
real_uid = me["id"]

# --- 3. PATCH /users/me (onboarding round-trip) ---
patch = {
    "name": "Smoke Farmer",
    "language_pref": "kn",
    "default_unit": "acre",
    "total_area_hectares": 1.2,
    "irrigation_type": "rainfed",
    "state": "Karnataka",
    "district": "Mysuru",
    "onboarding_complete": True,
}
r = client.patch("/api/v1/users/me", headers=H, json=patch)
check("PATCH /users/me 200", r.status_code == 200, str(r.status_code))
check("PATCH persisted onboarding_complete", r.json().get("onboarding_complete") is True)
check("PATCH persisted name", r.json().get("name") == "Smoke Farmer")

r = client.patch("/api/v1/users/me", headers=H, json={"default_unit": "hectare"})
check("PATCH partial keeps other fields", r.json().get("name") == "Smoke Farmer" and r.json().get("default_unit") == "hectare")

# --- 3b. weather for the profile's state/district (live Open-Meteo) ---
r = client.get("/api/v1/weather", headers=H)
check("GET /weather 200", r.status_code == 200, str(r.status_code))
w = r.json()
check("weather available for Karnataka/Mysuru", w.get("available") is True, str(w)[:160])
check("weather has a temperature + location label",
      w.get("temperature_c") is not None and "Mysuru" in (w.get("location_label") or ""))
check("weather has a multi-day forecast", len(w.get("forecast") or []) >= 2)
r = client.get("/api/v1/weather", headers=H, params={"state": "Punjab", "district": "Amritsar"})
check("GET /weather with override 200 + available", r.status_code == 200 and r.json().get("available") is True)

# --- 3c. locations reference (onboarding pickers, from MySQL) ---
r = client.get("/api/v1/locations", headers=H)
check("GET /locations 200", r.status_code == 200, str(r.status_code))
loc_items = r.json().get("items", [])
check("locations grouped by state, non-empty", len(loc_items) > 20)
ka = next((g for g in loc_items if g["state"] == "Karnataka"), None)
check("Karnataka present with districts incl. Mysuru",
      ka is not None and "Mysuru" in ka["districts"])

# --- 4. soil lookup ---
r = client.get("/api/v1/soil-lookup", headers=H, params={"state": "Karnataka", "district": "Mysuru"})
check("soil-lookup 200", r.status_code == 200, str(r.status_code))
check("soil-lookup has confidence", r.json().get("confidence") in ("taluk", "district", "none"))

# --- 5. catalog ---
r = client.get("/api/v1/catalog/crops", headers=H)
check("catalog/crops 200 + non-empty", r.status_code == 200 and len(r.json()["items"]) > 0)
crops_by_name = {c["name"]: c for c in r.json()["items"]}
crop = crops_by_name.get("Rice") or r.json()["items"][0]
check("catalog/crops includes growth_stages", len(crop.get("growth_stages") or []) >= 2, str(crop.get("growth_stages"))[:120])
r = client.get("/api/v1/catalog/agri-inputs", headers=H)
check("catalog/agri-inputs 200 + non-empty", r.status_code == 200 and len(r.json()["items"]) > 0)

# --- 6. sync push field + planting + scouting observation (sync-manager shape) ---
# Sowing date 30 days ago -> Rice is in "Vegetative (Tillering)" (days 20-45),
# the stage RICE_STEM_BORER_SCOUT gates on.
from datetime import date, timedelta  # noqa: E402
sowing = (date.today() - timedelta(days=30)).isoformat()
field_id = str(uuid.uuid4())
planting_id = str(uuid.uuid4())
scouting_id = str(uuid.uuid4())
body = {
    "fields": {"created": [{
        "id": field_id, "user_id": "u1", "name": "North Plot",
        "area_size_hectares": 1.2, "lat": 12.30, "long": 76.65,
        "boundary": [{"lat": 12.30, "long": 76.65}, {"lat": 12.31, "long": 76.66}, {"lat": 12.30, "long": 76.67}],
        "soil_type": "Red Sandy Loam",
    }], "updated": [], "deleted": []},
    "plantings": {"created": [{
        "id": planting_id, "field_id": field_id, "crop_id": crop["id"],
        "variety_id": crop["varieties"][0]["id"] if crop["varieties"] else None,
        "sowing_date": sowing, "status": "active",
    }], "updated": [], "deleted": []},
    "interventions": {"created": [], "updated": [], "deleted": []},
    "scouting_observations": {"created": [{
        "id": scouting_id, "planting_id": planting_id,
        "metric_key": "dead_hearts_percent", "metric_value": 8,
        "observed_at": date.today().isoformat(), "notes": "smoke test",
    }], "updated": [], "deleted": []},
}
r = client.post("/api/v1/sync", headers=H, params={"last_pulled_at": 0}, json=body)
check("sync push (incl. scouting obs) 200", r.status_code == 200, str(r.status_code) + " " + r.text[:200])

# --- 7. sync pull sees them back, owned by the real user ---
r = client.get("/api/v1/sync", headers=H, params={"schema_version": 1})
check("sync pull 200", r.status_code == 200, str(r.status_code))
pulled = r.json()["changes"]
pf = pulled.get("fields", {}).get("created", []) + pulled.get("fields", {}).get("updated", [])
check("pulled field owned by real uid (server overrode client u1)",
      any(f["id"] == field_id and f["user_id"] == real_uid for f in pf))
so = pulled.get("scouting_observations", {}).get("created", [])
check("pulled scouting observation", any(o["id"] == scouting_id for o in so))

# --- 7b. a recommendations block in a push body is silently ignored (no 500) ---
last_ts = client.get("/api/v1/sync", headers=H, params={"schema_version": 1}).json()["timestamp"]
r = client.post(
    "/api/v1/sync", headers=H, params={"last_pulled_at": last_ts},
    json={"recommendations": {"created": [
        {"id": str(uuid.uuid4()), "planting_id": planting_id}], "updated": [], "deleted": []}},
)
check("recommendations in push body ignored (200, no 500)", r.status_code == 200,
      str(r.status_code) + " " + r.text[:160])

# --- 8. run scheme matching (internal key) — now that onboarding_complete=True ---
IK = {"X-Internal-Key": settings.internal_api_key}
r = client.post("/api/v1/internal/run-scheme-matching", headers=IK)
check("run-scheme-matching 200", r.status_code == 200, str(r.status_code) + " " + r.text[:200])
check("run-scheme-matching created >=1 match for onboarded user", r.json().get("matches_created", 0) >= 1, r.text)

# --- 9. run recommendations (twice — idempotent) ---
r = client.post("/api/v1/internal/run-recommendations", headers=IK)
check("run-recommendations 200", r.status_code == 200, str(r.status_code) + " " + r.text[:200])
first_created = r.json().get("recommendations_created", 0)
check("run-recommendations fired the scouting rule", first_created >= 1, r.text)
r2 = client.post("/api/v1/internal/run-recommendations", headers=IK)
check("run-recommendations idempotent (no new rows on 2nd run)",
      r2.json().get("recommendations_created", 0) == 0, r2.text)

# --- 10. GET /alerts shows the scheme match AND the scouting recommendation ---
r = client.get("/api/v1/alerts", headers=H)
check("GET /alerts 200", r.status_code == 200, str(r.status_code))
items = r.json()["items"]
scheme_alerts = [a for a in items if a["kind"] == "scheme_match"]
rec_alerts = [a for a in items if a["kind"] == "recommendation"]
check("alert feed has the scheme match", len(scheme_alerts) >= 1, f"{len(items)} items")
check("alert feed has a recommendation (scouting rule fired end-to-end)",
      len(rec_alerts) >= 1, f"{len(items)} items")

# --- 11. PATCH alert status ---
if scheme_alerts:
    aid = scheme_alerts[0]["id"]
    r = client.patch(f"/api/v1/alerts/scheme_match/{aid}", headers=H, json={"status": "viewed"})
    check("PATCH alert -> viewed 200", r.status_code == 200 and r.json().get("status") == "viewed", str(r.status_code))
    r = client.patch(f"/api/v1/alerts/scheme_match/{aid}", headers=H, json={"status": "bogus"})
    check("PATCH alert invalid status -> 422", r.status_code == 422, str(r.status_code))

# --- 12. auth required ---
r = client.get("/api/v1/users/me")
check("GET /users/me without token -> 401/403", r.status_code in (401, 403), str(r.status_code))

# --- cleanup ---
with SessionLocal() as db:
    db.execute(text("delete from scheme_matches where user_id=:u"), {"u": real_uid})
    db.execute(text("delete from recommendations where planting_id=:p"), {"p": planting_id})
    db.execute(text("delete from scouting_observations where planting_id=:p"), {"p": planting_id})
    db.execute(text("delete from plantings where id=:p"), {"p": planting_id})
    db.execute(text("delete from fields where id=:f"), {"f": field_id})
    db.execute(text("delete from users where id=:u"), {"u": real_uid})
    db.execute(text("delete from otp_requests where phone_number=:p"), {"p": PHONE})
    db.commit()

failed = [n for n, c, _ in results if not c]
print()
print(f"{len(results) - len(failed)}/{len(results)} passed")
if failed:
    print("FAILED:", failed)
    raise SystemExit(1)
