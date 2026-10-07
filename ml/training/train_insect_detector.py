"""Insect pest detection, YOLOv8, on the Roboflow RF100 "insects" dataset.

Run:
    python -m ml.training.train_insect_detector
    python -m ml.training.train_insect_detector --audit-only
    python -m ml.training.train_insect_detector --resume   # reuse/resume runs in ml/artifacts/yolo_runs

Bar: MODEL_BARS.md section 9, 2026-09-23 entry "model 11". Identification
macro-F1 at least 0.85, recall at least 0.70 on each of the 8 app-relevant
classes, and mAP@0.5 at least 0.70.

## Relation to the parked YOLO scripts

`ml/training/parked/train_insect_model.py` targeted a `data.yaml` that never
existed, built by a preparation script reading `/tmp/reextract/` on another
machine, from about 50 images. This replaces it with a real dataset and the
same discipline as every other model here: leakage checked, a bar written
first, size chosen on validation, test read once.

## Pipeline

1. **Audit.** Every image is hashed flip- and rotation-invariantly and
   duplicates are confirmed at pixel level. 16 pairs of the same photo sit in
   two of the shipped splits. Copies are removed from train (if they duplicate
   valid or test) and from valid (if they duplicate test). **Test is never
   altered**; it stays exactly as shipped, so the measurement is on the
   original held-out images.
2. **Build a filtered copy** of the dataset under `ml/artifacts/yolo_data/`. The
   raw folder is read-only to this script.
3. **Train two sizes** (YOLOv8n, YOLOv8s), COCO-pretrained, at the images'
   native 224px. Upscaling to YOLO's default 640 would triple CPU time and
   invent resolution the images do not have.
4. **Choose on valid** by mAP@0.5.
5. **Test once**: mAP@0.5 from the detector, and identification exactly as
   serving will do it — the highest-confidence box at the serving threshold,
   with no box counted as wrong.

Ultralytics defaults to downloading weights into the working directory and
writing runs to `./runs`. Both are redirected into `ml/artifacts/` so the repo
root stays clean.
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter, defaultdict

import numpy as np
from PIL import Image
from sklearn.metrics import classification_report, confusion_matrix, f1_score

from ml import paths
from ml.evaluation import Report, per_class_recall
from ml.features.cnn import dihedral_digest
from ml.insect_pests import APP_RELEVANT_CLASSES, INSECT_PESTS

BAR_ID_MACRO_F1 = 0.85
BAR_CLASS_RECALL = 0.70
BAR_MAP50 = 0.70

SERVING_CONF = 0.25  # ultralytics' default; serving uses the same value
IMGSZ = 224
EPOCHS = 100
PATIENCE = 20
CANDIDATES = ("yolov8n", "yolov8s")
DUPLICATE_PIXEL_THRESHOLD = 5.0
SPLITS = ("train", "valid", "test")

DATA_DIR = paths.ARTIFACTS_DIR / "yolo_data" / "insects"
RUNS_DIR = paths.ARTIFACTS_DIR / "yolo_runs"
WEIGHTS_DIR = paths.ARTIFACTS_DIR / "weights"
META_PATH = paths.ARTIFACTS_DIR / "insect_detector_meta.json"
MODEL_PATH = paths.ARTIFACTS_DIR / "insect_detector.pt"


def _class_names() -> list[str]:
    import yaml

    spec = yaml.safe_load((paths.require(paths.INSECTS_YOLO_ROOT) / "data.yaml").read_text())
    names = list(spec["names"])
    unknown = [n for n in names if n not in INSECT_PESTS]
    if unknown:
        raise SystemExit(f"Classes missing from ml/insect_pests.py: {unknown}")
    return names


def _load_records() -> list[dict]:
    root = paths.INSECTS_YOLO_ROOT
    records = []
    for split in SPLITS:
        for image_path in sorted((root / split / "images").iterdir()):
            label_path = root / split / "labels" / f"{image_path.stem}.txt"
            rows = [line.split() for line in label_path.read_text().splitlines() if line.strip()]
            with Image.open(image_path) as handle:
                image = handle.convert("RGB")
            records.append(
                {
                    "split": split,
                    "image": image_path,
                    "label": label_path,
                    "classes": [int(r[0]) for r in rows],
                    "digest": dihedral_digest(image),
                    "pixels": np.asarray(image.resize((64, 64)), dtype=np.float32),
                }
            )
    return records


def _pixel_distance(a, b) -> float:
    return min(
        min(np.abs(a - np.rot90(b, k)).mean(), np.abs(a - np.fliplr(np.rot90(b, k))).mean())
        for k in range(4)
    )


def _cross_split_duplicates(records, report: Report) -> set:
    """Images to drop so no photo appears in two splits. Test is never dropped."""
    rank = {"test": 0, "valid": 1, "train": 2}  # keep the lower rank
    by_digest = defaultdict(list)
    for record in records:
        by_digest[record["digest"]].append(record)

    drop, pairs = set(), Counter()
    for group in by_digest.values():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                if a["split"] == b["split"]:
                    continue
                if _pixel_distance(a["pixels"], b["pixels"]) >= DUPLICATE_PIXEL_THRESHOLD:
                    continue
                pairs[tuple(sorted((a["split"], b["split"])))] += 1
                loser = a if rank[a["split"]] > rank[b["split"]] else b
                drop.add(loser["image"])

    print(f"Cross-split duplicate pairs (pixel-verified): {dict(pairs) or 'none'}")
    print(f"Removing {len(drop)} images from train/valid; test untouched")
    report.note(
        f"{sum(pairs.values())} photos appeared in two shipped splits; {len(drop)} "
        f"copies removed from train/valid, test kept exactly as shipped"
    )
    return drop


def _build_dataset(records, drop: set, names: list[str]) -> dict:
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    counts = {}
    for split in SPLITS:
        kept = [r for r in records if r["split"] == split and r["image"] not in drop]
        (DATA_DIR / split / "images").mkdir(parents=True)
        (DATA_DIR / split / "labels").mkdir(parents=True)
        for record in kept:
            shutil.copy2(record["image"], DATA_DIR / split / "images" / record["image"].name)
            shutil.copy2(record["label"], DATA_DIR / split / "labels" / record["label"].name)
        counts[split] = len(kept)
    yaml_path = DATA_DIR / "data.yaml"
    yaml_path.write_text(
        f"path: {DATA_DIR.as_posix()}\ntrain: train/images\nval: valid/images\n"
        f"test: test/images\nnc: {len(names)}\nnames: {json.dumps(names)}\n",
        encoding="utf-8",
    )
    print(f"Filtered dataset: {counts}")
    return {"yaml": yaml_path, "counts": counts}


def _weights(candidate: str):
    from ultralytics.utils.downloads import attempt_download_asset

    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    target = WEIGHTS_DIR / f"{candidate}.pt"
    if not target.exists():
        downloaded = attempt_download_asset(f"{candidate}.pt")
        shutil.move(str(downloaded), target)
    return target


def _run_state(candidate: str) -> str:
    """'finished', 'partial' or 'none' for a candidate's run under RUNS_DIR.

    Ultralytics strips the optimizer and sets `epoch` to -1 in last.pt when a
    run ends (all epochs or early stop), so a checkpoint that still carries a
    real epoch is an interrupted run that can be resumed.
    """
    import torch

    last = RUNS_DIR / candidate / "weights" / "last.pt"
    if not last.exists():
        return "none"
    checkpoint = torch.load(last, map_location="cpu", weights_only=False)
    return "finished" if checkpoint.get("epoch", -1) == -1 else "partial"


def _train_minutes(candidate: str) -> float:
    """Total training time from results.csv.

    The `time` column is cumulative within one session but restarts at zero
    when a run is resumed, so each segment's final value is summed.
    """
    import csv

    with open(RUNS_DIR / candidate / "results.csv", newline="") as handle:
        times = [float(row["time"]) for row in csv.DictReader(handle)]
    total = sum(prev for prev, cur in zip(times, times[1:]) if cur < prev) + times[-1]
    return total / 60


def _train(candidate: str, data_yaml, resume: bool = False) -> tuple[object, float, float]:
    from ultralytics import YOLO

    state = _run_state(candidate) if resume else "none"
    if state == "finished":
        print(f"  {candidate}: run already finished, reusing it")
    elif state == "partial":
        print(f"  {candidate}: resuming interrupted run from last.pt")
        YOLO(str(RUNS_DIR / candidate / "weights" / "last.pt")).train(resume=True)
    else:
        YOLO(str(_weights(candidate))).train(
            data=str(data_yaml),
            imgsz=IMGSZ,
            epochs=EPOCHS,
            patience=PATIENCE,
            batch=32,
            device="cpu",
            workers=0,
            seed=42,
            deterministic=True,
            project=str(RUNS_DIR),
            name=candidate,
            exist_ok=True,
            plots=False,
            verbose=False,
        )
    minutes = _train_minutes(candidate)
    best = YOLO(str(RUNS_DIR / candidate / "weights" / "best.pt"))
    val = best.val(data=str(data_yaml), split="val", imgsz=IMGSZ, device="cpu", plots=False, verbose=False)
    print(f"  {candidate}: valid mAP@0.5 {val.box.map50:.4f}  ({minutes:.1f} min)")
    return best, float(val.box.map50), minutes


def _identify(model, split_dir, names):
    """Top-confidence class per image at the serving threshold; None if no box."""
    truths, predictions = [], []
    for image_path in sorted((split_dir / "images").iterdir()):
        label_path = split_dir / "labels" / f"{image_path.stem}.txt"
        labels = [int(l.split()[0]) for l in label_path.read_text().splitlines() if l.strip()]
        truth = Counter(labels).most_common(1)[0][0]
        result = model.predict(str(image_path), imgsz=IMGSZ, conf=SERVING_CONF, device="cpu", verbose=False)[0]
        if len(result.boxes):
            predicted = names[int(result.boxes.cls[int(result.boxes.conf.argmax())])]
        else:
            predicted = "(no detection)"
        truths.append(names[truth])
        predictions.append(predicted)
    return np.array(truths), np.array(predictions)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="reuse finished candidate runs and resume interrupted ones instead of retraining",
    )
    args = parser.parse_args()

    report = Report("Insect pest detection (YOLOv8)")
    names = _class_names()
    print("Loading and hashing images...")
    records = _load_records()
    drop = _cross_split_duplicates(records, report)
    built = _build_dataset(records, drop, names)

    test_instances = Counter()
    for record in records:
        if record["split"] == "test":
            test_instances.update(names[c] for c in set(record["classes"]))
    print("test images per class:", dict(sorted(test_instances.items())))
    if args.audit_only:
        return

    candidates = {}
    for candidate in CANDIDATES:
        print(f"\nTraining {candidate} at {IMGSZ}px (up to {EPOCHS} epochs, patience {PATIENCE})...")
        candidates[candidate] = _train(candidate, built["yaml"], resume=args.resume)

    chosen = max(candidates, key=lambda c: candidates[c][1])
    model, val_map50, minutes = candidates[chosen]
    print(f"\nChosen on valid: {chosen} (" + ", ".join(f"{c} {v[1]:.4f}" for c, v in candidates.items()) + ")")

    # Test, read once.
    test = model.val(data=str(built["yaml"]), split="test", imgsz=IMGSZ, device="cpu", plots=False, verbose=False)
    map50, map50_95 = float(test.box.map50), float(test.box.map)
    per_class_ap50 = {names[int(c)]: float(ap) for c, ap in zip(test.box.ap_class_index, test.box.ap50)}

    truth, predicted = _identify(model, DATA_DIR / "test", names)
    id_macro_f1 = float(f1_score(truth, predicted, labels=names, average="macro", zero_division=0))
    id_accuracy = float((truth == predicted).mean())
    recalls = per_class_recall(truth, predicted, names)
    no_detection = int((predicted == "(no detection)").sum())
    baseline = float((truth == Counter(truth).most_common(1)[0][0]).mean())

    print(f"\nTEST  mAP@0.5 {map50:.4f}   mAP@0.5:0.95 {map50_95:.4f}")
    print(f"      identification macro-F1 {id_macro_f1:.4f}   accuracy {id_accuracy:.4f}   "
          f"no-detection {no_detection}/{len(truth)}   majority baseline {baseline:.4f}")
    print(f"\n{'class':28s} {'n':>3s} {'id recall':>9s} {'AP@0.5':>7s}  relevant")
    for name in names:
        print(f"{name:28s} {test_instances[name]:3d} {recalls[name]:9.4f} "
              f"{per_class_ap50.get(name, float('nan')):7.4f}  {'yes' if name in APP_RELEVANT_CLASSES else 'no'}")
    print("\n" + classification_report(truth, predicted, labels=names, zero_division=0))
    matrix = confusion_matrix(truth, predicted, labels=names + ["(no detection)"])

    report.check("identification macro-F1 (test)", BAR_ID_MACRO_F1, id_macro_f1)
    for name in APP_RELEVANT_CLASSES:
        report.check(f"recall({name}) [n={test_instances[name]}]", BAR_CLASS_RECALL, recalls[name])
    report.check("mAP@0.5 (test)", BAR_MAP50, map50)
    report.note(f"chosen on valid: {chosen}; valid mAP@0.5 {val_map50:.4f}")
    report.note(f"majority-class identification baseline {baseline:.4f}")
    report.note(
        "PROVISIONAL regardless: tight 224px crops with one insect each are not "
        "field photos; the model was never shown an insect-free image"
    )
    print(report.render())

    shutil.copy2(RUNS_DIR / chosen / "weights" / "best.pt", MODEL_PATH)
    meta = {
        "passed_bar": report.passed,
        "architecture": chosen,
        "imgsz": IMGSZ,
        "serving_conf": SERVING_CONF,
        "class_names": names,
        "test_map50": map50,
        "test_map50_95": map50_95,
        "test_per_class_ap50": per_class_ap50,
        "test_identification_macro_f1": id_macro_f1,
        "test_identification_accuracy": id_accuracy,
        "test_identification_recall": recalls,
        "test_no_detection": no_detection,
        "test_instances": dict(test_instances),
        "valid_map50_by_candidate": {c: v[1] for c, v in candidates.items()},
        "train_minutes_by_candidate": {c: round(v[2], 1) for c, v in candidates.items()},
        "dataset_counts": built["counts"],
        "duplicates_removed": len(drop),
        "confusion_matrix": matrix.tolist(),
        "confusion_labels": names + ["(no detection)"],
    }
    META_PATH.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(f"\nSaved -> {MODEL_PATH.relative_to(paths.REPO_ROOT)} + {META_PATH.name}")


if __name__ == "__main__":
    main()
