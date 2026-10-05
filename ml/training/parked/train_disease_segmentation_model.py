"""
ml/training/train_disease_segmentation_model.py

Algorithm: YOLOv8n-seg (instance SEGMENTATION, not plain bounding-box
detection).

WHY SEGMENTATION SPECIFICALLY: I checked the label file format before
choosing — Crop_Diseases/labels/train/*.txt contain polygon point lists
(class_id x1 y1 x2 y2 x3 y3 ...), not the 4-number bounding boxes
Crop_Insects uses. That's YOLO's segmentation label format. Training a
plain detector on segmentation labels would either fail or silently
ignore the polygon shape and just fit a bounding box around it, throwing
away the actual lesion-outline information the labels encode. Using
YOLOv8n-SEG instead uses that shape data properly — the output is a
pixel-level lesion mask, not just a box.

Single class ("disease" — presence/outline, not which disease), 50
images, same nano-model and same reasoning as train_insect_model.py for
why a small model fits a dataset this size.

NOT RUN IN THIS SESSION — same environment blocker as train_insect_model.py:
PyTorch could not be installed here (CUDA-build disk quota issue, and
the CPU-only wheel index is unreachable from this sandbox's network).
Run this on Colab: !pip install ultralytics, then
prepare_disease_yolo_split.py, then this script.
"""
import os as _os
BASE_DIR = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))  # -> .../ml, works regardless of where this project is placed
from ultralytics import YOLO

DATA_YAML = _os.path.join(BASE_DIR, "datasets/crop_diseases_yolo/data.yaml")
MODEL_OUT_DIR = _os.path.join(BASE_DIR, "saved_models")
EPOCHS = 50


def main():
    model = YOLO("yolov8n-seg.pt")  # segmentation checkpoint, not the plain detection one

    model.train(
        data=DATA_YAML,
        epochs=EPOCHS,
        imgsz=416,
        batch=8,
        patience=15,
        project=MODEL_OUT_DIR,
        name="disease_segmentation_model",
        seed=42,
    )

    metrics = model.val()
    print(f"mask mAP50: {metrics.seg.map50:.3f}")
    print(f"mask mAP50-95: {metrics.seg.map:.3f}")
    print(f"Best weights -> {MODEL_OUT_DIR}/disease_segmentation_model/weights/best.pt")


if __name__ == "__main__":
    main()
