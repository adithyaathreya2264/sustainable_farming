"""FastAPI app entrypoint.

Run from repo root: uvicorn backend.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.v1.advisory import router as advisory_router
from backend.api.v1.agronomy import router as agronomy_router
from backend.api.v1.alerts import router as alerts_router
from backend.api.v1.auth import router as auth_router
from backend.api.v1.catalog import router as catalog_router
from backend.api.v1.market import router as market_router
from backend.api.v1.internal import router as internal_router
from backend.api.v1.locations import router as locations_router
from backend.api.v1.soil import router as soil_router
from backend.api.v1.sync import router as sync_router
from backend.api.v1.users import router as users_router
from backend.api.v1.weather import router as weather_router
from backend.core.config import settings

app = FastAPI(title="Sustainable Farming API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    # Auth is a Bearer header, not a cookie — no credentialed requests, so this
    # stays False and `allow_origins=["*"]` remains valid.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(sync_router)
app.include_router(soil_router)
app.include_router(catalog_router)
app.include_router(locations_router)
app.include_router(internal_router)
app.include_router(alerts_router)
app.include_router(weather_router)
# Dataset-derived features (see datasets/README.md).
app.include_router(agronomy_router)
app.include_router(market_router)
app.include_router(advisory_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
