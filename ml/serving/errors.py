"""Map model-layer exceptions to HTTP responses with a machine-readable `reason`.

Node (backend/src/services/mlClient.js) switches on `reason`, not on text.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ml.algorithms._loader import ModelDidNotShip
from ml.serving.holds import ModelOnHold
from ml.serving.images import ImageRejected, ImageTooLarge
from ml.serving.sanitize import LeakedProbability

log = logging.getLogger("ml.serving")


def _body(reason: str, detail: str, **extra) -> dict:
    return {"reason": reason, "detail": detail, **extra}


def install(app: FastAPI) -> None:
    @app.exception_handler(ModelDidNotShip)
    async def _did_not_ship(_: Request, exc: ModelDidNotShip):
        return JSONResponse(status_code=409, content=_body("model_did_not_ship", str(exc).splitlines()[0]))

    @app.exception_handler(ModelOnHold)
    async def _on_hold(_: Request, exc: ModelOnHold):
        return JSONResponse(status_code=409, content=_body("model_on_hold", str(exc), hold_reason=exc.reason))

    @app.exception_handler(ImageTooLarge)
    async def _too_large(_: Request, exc: ImageTooLarge):
        return JSONResponse(status_code=413, content=_body("image_too_large", str(exc)))

    @app.exception_handler(ImageRejected)
    async def _bad_image(_: Request, exc: ImageRejected):
        return JSONResponse(status_code=422, content=_body("invalid_image", str(exc)))

    @app.exception_handler(ValueError)
    async def _invalid(_: Request, exc: ValueError):
        return JSONResponse(status_code=422, content=_body("invalid_input", str(exc)))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content=_body("invalid_input", "request validation failed", errors=exc.errors()))

    @app.exception_handler(FileNotFoundError)
    async def _missing(_: Request, exc: FileNotFoundError):
        return JSONResponse(status_code=503, content=_body("artifact_missing", str(exc).splitlines()[0]))

    @app.exception_handler(LeakedProbability)
    async def _leak(_: Request, exc: LeakedProbability):
        log.error("blocked a response at the serving boundary: %s", exc)
        return JSONResponse(status_code=500, content=_body("inference_failed", "response blocked at serving boundary"))

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception):
        log.exception("inference failed", exc_info=exc)
        return JSONResponse(status_code=500, content=_body("inference_failed", type(exc).__name__))
