from __future__ import annotations

from fastapi import APIRouter

from ml.serving import capabilities as caps
from ml.serving.sanitize import public

router = APIRouter()


@router.get("/health")
def health() -> dict:
    """Liveness only: loads nothing."""
    return {"status": "ok"}


@router.get("/v1/models")
def models() -> dict:
    return public({"models": caps.roster()})


@router.get("/v1/models/{model_id}/classes")
def model_classes(model_id: str) -> dict:
    return public({"model": model_id, "crop_keys": caps.model_classes(model_id)})


@router.get("/v1/capabilities")
def capabilities(crop: str) -> dict:
    return public(caps.capabilities(crop))
