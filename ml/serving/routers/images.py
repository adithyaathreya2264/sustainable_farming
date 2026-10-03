"""Photo endpoints: 7b, 11, 12, 13, 14b, 17, 20-27 (through /v1/leaf), 28 (held).

Plain `def` handlers run in FastAPI's threadpool; a semaphore caps concurrent
CPU inference so a burst of uploads cannot starve the Node process sharing the
machine.
"""

from __future__ import annotations

import threading

from fastapi import APIRouter, File, Form, UploadFile

from ml.serving import holds
from ml.serving.images import MAX_BYTES, ImageTooLarge, decode_upload
from ml.serving.sanitize import public

router = APIRouter(prefix="/v1")

_inference_slots = threading.BoundedSemaphore(2)


def _read(photo: UploadFile):
    data = photo.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ImageTooLarge(f"image exceeds {MAX_BYTES // (1024 * 1024)} MB")
    return decode_upload(data)


def _run(fn, *args, **kwargs) -> dict:
    with _inference_slots:
        return public(fn(*args, **kwargs))


@router.post("/soil-type")
def soil_type(photo: UploadFile = File(...)) -> dict:
    from ml.algorithms.soil_type_prediction import predict_soil_type

    return _run(predict_soil_type, _read(photo), "mobilenetv3")


@router.post("/insects")
def insects(photo: UploadFile = File(...), crop: str = Form(...)) -> dict:
    from ml.algorithms.insect_detection import detect_insects

    return _run(detect_insects, _read(photo), crop)


@router.post("/leaf")
def leaf(
    photo: UploadFile = File(...),
    crop: str = Form(...),
    symptom_reported: bool = Form(False),
) -> dict:
    from ml.algorithms.leaf_condition_prediction import diagnose_leaf

    return _run(diagnose_leaf, _read(photo), crop, symptom_reported=symptom_reported)


@router.post("/wheat-heading")
def wheat_heading(photo: UploadFile = File(...), crop: str = Form("wheat")) -> dict:
    from ml.algorithms.wheat_canopy_segmentation import detect_wheat_heading

    return _run(detect_wheat_heading, _read(photo), crop)


@router.post("/tobacco-lesions")
def tobacco_lesions(photo: UploadFile = File(...), crop: str = Form("tobacco")) -> dict:
    from ml.algorithms.tobacco_lesion_segmentation import measure_tobacco_lesions

    return _run(measure_tobacco_lesions, _read(photo), crop)


# Shown with every kernel result: the module's own caveats predate the audit.
KERNEL_LIGHTING_CAVEAT = (
    "In testing, the average colour of a photo alone predicted the label almost as "
    "well as the model, so the result may reflect lighting rather than damage."
)


@router.post("/wheat-kernels")
def wheat_kernels(photo: UploadFile = File(...)) -> dict:
    """Model 28. Held (ml/serving/holds.py): refused with 409 before the photo
    is decoded, until the lighting check in MODEL_RESULTS.md section 28."""
    holds.check("wheat_kernels")
    from ml.algorithms.wheat_kernel_damage import assess_wheat_kernels

    result = _run(assess_wheat_kernels, _read(photo), "wheat")
    result["caveats"] = list(result.get("caveats", [])) + [KERNEL_LIGHTING_CAVEAT]
    return result
