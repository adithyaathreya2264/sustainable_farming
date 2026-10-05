"""
ml/training/train_insect_model.py

Algorithm: YOLOv8n (nano) object detection, fine-tuned from Ultralytics'
pretrained COCO checkpoint.

IMPORTANT — WHY THIS WASN'T ACTUALLY RUN IN THIS SESSION:
Installing a working PyTorch in this sandbox failed twice:
  1. `pip install ultralytics` pulled a CUDA-enabled torch build (this
     sandbox has no GPU) with ~3GB of NVIDIA CUDA libraries as
     dependencies, which filled the sandbox's disk quota mid-install.
  2. After uninstalling those and retrying, torch's CPU-only wheel index
     (download.pytorch.org) isn't reachable from this sandbox's network
     allowlist, and reinstalling plain `torch` from PyPI hit the same
     disk-quota wall pulling CUDA deps again.
This is an environment limitation, not a problem with the script or the
data. The fix (below) needs an environment with more disk headroom and
either a GPU or normal internet access — Google Colab's free tier is both.

WHY YOLO SPECIFICALLY: the source data (images/train + labels/train, one
bounding box per insect, single class "insects") is already in YOLO
format — this is a detection task (where in the image is the insect),
not classification, since every image is positive and there's no
negative/no-insect class to classify against.

WHY ONLY ONE CLASS: the source labels only distinguish "insect" vs
nothing — not species. This model will find insects in a photo, not
identify which pest it is. If you need species-level ID, you'd need
per-species labeled data (see the multi-class options in the dataset
sourcing list from earlier).

WHY nano (YOLOv8n) SPECIFICALLY: with only 50 images (40 train / 10 val
after prepare_insect_yolo_split.py), a larger YOLO variant (s/m/l/x) would
overfit fast and gain nothing — nano is the right size for a dataset this
small, and fine-tunes quickly even on a free Colab GPU (a few minutes).

TO RUN (e.g. in Colab):
    !pip install ultralytics
    python3 prepare_insect_yolo_split.py   # run this first
    python3 train_insect_model.py
"""
import os as _os
BASE_DIR = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))  # -> .../ml, works regardless of where this project is placed
from ultralytics import YOLO

DATA_YAML = _os.path.join(BASE_DIR, "datasets/crop_insects_yolo/data.yaml")
MODEL_OUT_DIR = _os.path.join(BASE_DIR, "saved_models")
EPOCHS = 50  # fine for 50 images + nano model + pretrained start; raise if you add more images later


def main():
    model = YOLO("yolov8n.pt")  # starts from Ultralytics' COCO-pretrained nano checkpoint

    results = model.train(
        data=DATA_YAML,
        epochs=EPOCHS,
        imgsz=416,          # smaller than the usual 640 — appropriate for this tiny dataset
        batch=8,
        patience=15,        # early stop if val loss plateaus, given how little data there is
        project=MODEL_OUT_DIR,
        name="insect_model",
        seed=42,
    )

    metrics = model.val()
    print(f"mAP50: {metrics.box.map50:.3f}")
    print(f"mAP50-95: {metrics.box.map:.3f}")
    print(f"Best weights saved under {MODEL_OUT_DIR}/insect_model/weights/best.pt")


if __name__ == "__main__":
    main()
