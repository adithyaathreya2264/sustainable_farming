"""Vegetable variety/size classifier, all 14 folders (model 19). Never served.

Run:
    python -m ml.training.train_vegetable_classifier
    python -m ml.training.train_vegetable_classifier --audit-only

Bar: MODEL_BARS.md section 9, 2026-09-24 entry "model 19". Macro-F1 at least
0.85 and every one of the 14 classes with recall at least 0.70 on the test
fold. A class that cannot be measured counts as failing.

## One image, one label

The dataset files the same image under several class folders: of the 6,418
file names found in more than one folder, 6,331 are byte-identical copies and
87 genuinely differ (DATASETS_STATUS.md section 2.16). This script reuses the
leaf pipeline (`train_leaf_condition_model.py`):

- flip- and rotation-invariant duplicate detection, pixel-verified;
- **duplicate groups carrying more than one label are dropped**, while
  genuinely different images keep their folder label, whatever their name;
- sessions from the capture time in the file name (`IMG_YYYYMMDD_HHMMSS`), so
  every augmented copy of a photo stays on one side of the split;
- 60/20/20 by session, two-phase MobileNetV3-Large transfer learning chosen on
  validation, and test read once.

Classes left with fewer than `MIN_SESSIONS` sessions cannot reach the test
fold. They are excluded from training and fail their recall criterion,
instead of silently vanishing from the report.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict

import numpy as np
from sklearn.metrics import classification_report, confusion_matrix, f1_score

from ml import paths
from ml.evaluation import Report, per_class_recall
from ml.training.train_leaf_condition_model import (
    IMAGE_SUFFIXES,
    _cache_and_digest,
    _group,
    _LeafDataset,
    _predict,
    _split,
    _train,
)

CROP = "vegetables"  # cache and grouping key, not an app crop
BAR_MACRO_F1 = 0.85
BAR_CLASS_RECALL = 0.70
MIN_SESSIONS = 5


def _class_name(folder: str) -> str:
    return folder.replace("-aug", "").replace("-agu", "")


def _index() -> list:
    root = paths.require(paths.VEGETABLE_IMAGES)
    items = []
    for folder in sorted(p for p in root.glob("*/*") if p.is_dir()):
        images = sorted(f for f in folder.iterdir() if f.suffix.lower() in IMAGE_SUFFIXES)
        items.extend((f, _class_name(folder.name)) for f in images)
    return items


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()
    started = time.time()

    report = Report("Vegetable variety/size classifier (model 19)")
    items = _index()
    all_classes = sorted({label for _, label in items})
    print(f"{len(items)} images in {len(all_classes)} classes:")
    for name, n in sorted(Counter(label for _, label in items).items()):
        print(f"  {name:22s} {n:5d}")

    print("\nPreparing images at 256px (lossless cache) and hashing...")
    records = _cache_and_digest(CROP, items)
    groups, stats = _group(records, report, CROP)

    sessions = defaultdict(int)
    images = Counter()
    for g in groups:
        label = g[0]["folder"]
        sessions[label] += 1
        images[label] += len(g)
    print(f"\n{'class':22s} {'images kept':>11s} {'sessions':>8s}")
    for name in all_classes:
        print(f"  {name:22s} {images[name]:9d} {sessions[name]:8d}"
              f"{'   <- too few sessions, excluded' if sessions[name] < MIN_SESSIONS else ''}")
    trainable = [c for c in all_classes if sessions[c] >= MIN_SESSIONS]
    excluded = [c for c in all_classes if c not in trainable]
    report.note(f"classes excluded for fewer than {MIN_SESSIONS} sessions after conflict removal: {excluded or 'none'}")

    kept = [g for g in groups if g[0]["folder"] in trainable]
    train, val, test = _split(kept)
    print(f"\nSplit by session: train {len(train)}  val {len(val)}  test {len(test)}")
    if args.audit_only:
        return

    import torch
    from torch.utils.data import DataLoader

    from ml.features.cnn import leaf_eval_transform

    model, chosen, val_scores = _train(train, val, trainable)
    class_index = {c: i for i, c in enumerate(trainable)}
    loader = DataLoader(_LeafDataset(test, class_index, leaf_eval_transform()), batch_size=64)
    truth_idx, predicted_idx = _predict(model, loader)
    predicted = np.array([trainable[i] for i in predicted_idx])
    truth = np.array([trainable[i] for i in truth_idx])

    # Test, read once. Excluded classes are part of the bar and fail it.
    macro_f1 = float(f1_score(truth, predicted, labels=trainable, average="macro", zero_division=0))
    recalls = per_class_recall(truth, predicted, trainable)
    baseline = float((truth == Counter(truth).most_common(1)[0][0]).mean())
    vegetable = lambda c: c.split("_")[0].lower()  # noqa: E731
    type_accuracy = float(np.mean([vegetable(a) == vegetable(b) for a, b in zip(truth, predicted)]))
    print(f"\nTEST  macro-F1 {macro_f1:.4f} over {len(trainable)} trainable classes   "
          f"accuracy {(truth == predicted).mean():.4f}   majority baseline {baseline:.4f}   "
          f"vegetable-type accuracy {type_accuracy:.4f}")
    print(classification_report(truth, predicted, labels=trainable, zero_division=0))

    report.check(f"macro-F1 over {len(trainable)} trainable classes (test)", BAR_MACRO_F1, macro_f1)
    for name in all_classes:
        report.check(f"recall({name})", BAR_CLASS_RECALL, recalls.get(name, 0.0) if name in trainable else 0.0)
    report.note(f"majority-class baseline {baseline:.4f}; selected on validation: phase {chosen}")
    report.note("NOT SERVED regardless of verdict: no produce-grading use in the app")
    print(report.render())

    torch.save({
        "state_dict": model.state_dict(), "passed_bar": report.passed, "served": False,
        "classes": trainable, "excluded_classes": excluded, "architecture": "mobilenet_v3_large",
    }, paths.VEGETABLE_CLASSIFIER_MODEL)
    paths.VEGETABLE_CLASSIFIER_MODEL.with_name("vegetable_classifier_metrics.json").write_text(json.dumps({
        "passed_bar": report.passed, "served": False, "macro_f1": macro_f1, "recall": recalls,
        "excluded_classes": excluded, "images_kept": dict(images), "sessions": dict(sessions),
        "grouping": stats, "validation": val_scores, "vegetable_type_accuracy": type_accuracy,
        "confusion_labels": trainable,
        "confusion_matrix": confusion_matrix(truth, predicted, labels=trainable).tolist(),
        "minutes": round((time.time() - started) / 60, 1),
    }, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"Saved -> {paths.VEGETABLE_CLASSIFIER_MODEL.relative_to(paths.REPO_ROOT)}")


if __name__ == "__main__":
    main()
