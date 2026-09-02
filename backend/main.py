"""FastAPI app entrypoint.

Run from repo root: uvicorn backend.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI

from backend.api.v1.auth import router as auth_router
from backend.api.v1.sync import router as sync_router

app = FastAPI(title="Sustainable Farming API")

app.include_router(auth_router)
app.include_router(sync_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
