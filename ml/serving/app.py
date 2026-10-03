"""FastAPI app. See `ml/serving/__init__.py` for how to run it."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ml.serving import errors
from ml.serving.routers import images, market, meta, tabular

log = logging.getLogger("ml.serving")


def _preload() -> None:
    """Warm every shipped model (ML_PRELOAD=1) so the first request of a demo
    does not pay the torch/YOLO load. Failures are logged, not fatal: a refused
    or missing model must not stop the others from serving."""
    from ml.algorithms import (
        crop_recommendation,
        disease_info_retrieval,
        insect_detection,
        leaf_condition_prediction,
        price_forecast,
        soil_type_prediction,
        tobacco_lesion_segmentation,
        wheat_canopy_segmentation,
        yield_prediction,
    )

    steps = [
        ("crop_recommendation", crop_recommendation._npk_bundle),
        ("crop_soil_type", crop_recommendation._soil_bundle),
        ("disease_qa", disease_info_retrieval._index),
        ("yield", yield_prediction._typical_input_table),
        ("price", price_forecast._load),
        ("soil_type_photo", soil_type_prediction._cnn),
        ("insects", insect_detection._load),
        ("leaf_rice", lambda: leaf_condition_prediction._load("rice")),
        ("leaf_pearl_millet", lambda: leaf_condition_prediction._load("pearl millet")),
        ("wheat_heading", wheat_canopy_segmentation._load),
        *[
            (f"leaf_{key}", (lambda k=key: leaf_condition_prediction._load(k)))
            for key in ("coffee", "tea", "cauliflower", "cauliflower curd",
                        "onion", "onion bulb", "potato", "tomato fruit")
        ],
        ("tobacco", tobacco_lesion_segmentation._load),
    ]
    for name, step in steps:
        try:
            step()
            log.info("preloaded %s", name)
        except Exception as exc:  # noqa: BLE001
            log.warning("preload %s skipped: %s", name, str(exc).splitlines()[0])


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        import torch

        # Leave half the cores for Node and MySQL on the same machine.
        torch.set_num_threads(max(1, (os.cpu_count() or 2) // 2))
    except ImportError:
        pass
    if os.environ.get("ML_PRELOAD") == "1":
        _preload()
    yield


app = FastAPI(title="sustainable-farming ML sidecar", lifespan=lifespan)
errors.install(app)
for router in (meta.router, tabular.router, images.router, market.router):
    app.include_router(router)
