"""Wheat kernel sunn-pest damage from a photo of grain (model 28).

Run:
    python -m ml.training.train_wheat_kernel_damage
    python -m ml.training.train_wheat_kernel_damage --audit-only

Bar: MODEL_BARS.md section 9, 2026-09-25 entry "model 28". The leaf bar with
two classes: macro-F1 at least 0.85, recall at least 0.70 for both classes,
and healthy precision at least 0.90.

## Why not the leaf pipeline

The photos are 5184x2920 heaps of kernels from six Turkish cultivars. Sunn pest
(Eurygaster) feeding leaves small puncture marks on each kernel. The leaf
pipeline shrinks a photo to 256 px, which would erase them. Here each photo is
cached at 1536 px wide:

- training uses random 384 px crops (a few kernels each);
- prediction averages the softmax over a fixed grid of crops covering the photo.

## Split

170 photos, each its own group. The split is 60/20/20, stratified by
cultivar x label, so every cultivar is represented on both sides. Exact
duplicate photos, if any, are grouped first. About 34 test photos make this
weak evidence however the numbers come out, and the bar says so.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from collections import Counter, defaultdict

import numpy as np
from PIL import Image
from sklearn.metrics import f1_score, precision_score
from sklearn.model_selection import StratifiedShuffleSplit

from ml import paths
from ml.evaluation import Report, per_class_recall
from ml.features.cnn import IMAGENET_MEAN, IMAGENET_STD, build_mobilenet_v3

CLASSES = ["damaged", "healthy"]
ARCH = "mobilenet_v3_large"
CACHE_WIDTH = 1536
CROP = 384
GRID = (4, 2)  # columns x rows of evaluation crops
CROPS_PER_IMAGE = 12  # per training epoch
MAX_EPOCHS = 20
PATIENCE = 4
BATCH = 16
SEED = 42

BAR_MACRO_F1 = 0.85
BAR_CLASS_RECALL = 0.70
BAR_HEALTHY_PRECISION = 0.90

Image.MAX_IMAGE_PIXELS = None


def _index() -> list[dict]:
    root = paths.require(paths.WHEAT_KERNEL_IMAGES)
    records = []
    for image in sorted(root.glob("*/*/*/*.png")):
        label, cultivar = image.parent.name, image.parent.parent.name
        if label not in CLASSES:
            raise SystemExit(f"Unexpected class folder {label!r} at {image}")
        records.append({"source": image, "label": label, "cultivar": cultivar,
                        "digest": hashlib.md5(image.read_bytes()).hexdigest()})
    return records


def _cache(record: dict) -> Image.Image:
    cached = paths.IMAGE_CACHE_DIR / "wheat_kernels" / f"{record['digest']}.png"
    if not cached.exists():
        cached.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(record["source"]) as handle:
            image = handle.convert("RGB")
        height = round(image.height * CACHE_WIDTH / image.width)
        image.resize((CACHE_WIDTH, height), Image.Resampling.BICUBIC).save(cached, format="PNG")
    return Image.open(cached).convert("RGB")


def _grid_crops(image: Image.Image) -> list[Image.Image]:
    cols, rows = GRID
    xs = np.linspace(0, image.width - CROP, cols).astype(int)
    ys = np.linspace(0, image.height - CROP, rows).astype(int)
    return [image.crop((x, y, x + CROP, y + CROP)) for y in ys for x in xs]


def _tensor(image, train: bool):
    from torchvision import transforms

    steps = []
    if train:
        steps += [transforms.RandomHorizontalFlip(), transforms.RandomVerticalFlip(),
                  transforms.RandomRotation(180), transforms.ColorJitter(0.15, 0.15, 0.1, 0.02)]
    steps += [transforms.ToTensor(), transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD)]
    return transforms.Compose(steps)(image)


def _predict(model, images: list[Image.Image]) -> np.ndarray:
    """Mean class probability over the evaluation grid, per photo."""
    import torch

    model.eval()
    out = []
    with torch.no_grad():
        for image in images:
            batch = torch.stack([_tensor(c, train=False) for c in _grid_crops(image)])
            out.append(torch.softmax(model(batch), dim=1).mean(0).numpy())
    return np.array(out)


def _macro(truth, predicted) -> float:
    return float(f1_score(truth, predicted, labels=CLASSES, average="macro", zero_division=0))


def _train(train, val):
    import torch
    from torch import nn

    torch.manual_seed(SEED)
    random.seed(SEED)
    model = build_mobilenet_v3(ARCH, len(CLASSES), pretrained=True)
    counts = Counter(r["label"] for r in train)
    weights = torch.tensor([(len(train) / (len(CLASSES) * counts[c])) ** 0.5 for c in CLASSES], dtype=torch.float)
    criterion = nn.CrossEntropyLoss(weight=weights, label_smoothing=0.1)
    optimizer = torch.optim.AdamW([
        {"params": model.features.parameters(), "lr": 1e-4},
        {"params": model.classifier.parameters(), "lr": 1e-3},
    ], weight_decay=1e-4)
    index = {c: i for i, c in enumerate(CLASSES)}
    val_truth = [r["label"] for r in val]

    best, best_state, stale = -1.0, None, 0
    for epoch in range(1, MAX_EPOCHS + 1):
        started = time.time()
        samples = []
        for r in train:
            image = r["image"]
            for _ in range(CROPS_PER_IMAGE):
                x = random.randint(0, image.width - CROP)
                y = random.randint(0, image.height - CROP)
                samples.append((image.crop((x, y, x + CROP, y + CROP)), index[r["label"]]))
        random.shuffle(samples)
        model.train()
        for start in range(0, len(samples), BATCH):
            chunk = samples[start:start + BATCH]
            xb = torch.stack([_tensor(img, train=True) for img, _ in chunk])
            yb = torch.tensor([label for _, label in chunk])
            optimizer.zero_grad()
            criterion(model(xb), yb).backward()
            optimizer.step()
        predicted = [CLASSES[i] for i in _predict(model, [r["image"] for r in val]).argmax(1)]
        score = _macro(val_truth, predicted)
        improved = score > best
        if improved:
            best, stale = score, 0
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        else:
            stale += 1
        print(f"  epoch {epoch:2d}  val macro-F1 {score:.4f}  {'*' if improved else ' '}  "
              f"({time.time() - started:.0f}s)", flush=True)
        if stale >= PATIENCE:
            print(f"  early stop: no validation gain in {PATIENCE} epochs")
            break
    model.load_state_dict(best_state)
    return model, best


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()
    started = time.time()

    report = Report("Wheat kernel sunn-pest damage (model 28)")
    records = _index()
    by_digest = defaultdict(list)
    for r in records:
        by_digest[r["digest"]].append(r)
    conflicting = [g for g in by_digest.values() if len({r["label"] for r in g}) > 1]
    if conflicting:
        raise SystemExit(f"{len(conflicting)} identical photos carry both labels")
    photos = [g[0] for g in by_digest.values()]
    print(f"{len(records)} files, {len(photos)} distinct photos; "
          f"{dict(Counter((p['cultivar'], p['label']) for p in photos))}")
    report.note(f"{len(records)} files are {len(photos)} distinct photos (exact duplicates grouped)")

    strata = [f"{p['cultivar']}/{p['label']}" for p in photos]
    outer = StratifiedShuffleSplit(n_splits=1, test_size=0.20, random_state=SEED)
    rest, test = next(outer.split(photos, strata))
    inner = StratifiedShuffleSplit(n_splits=1, test_size=0.25, random_state=SEED)
    fit_i, val_i = next(inner.split([photos[i] for i in rest], [strata[i] for i in rest]))
    train = [photos[rest[i]] for i in fit_i]
    val = [photos[rest[i]] for i in val_i]
    test = [photos[i] for i in test]
    for name, fold in (("train", train), ("val", val), ("test", test)):
        print(f"  {name:5s} {len(fold):3d} photos  {dict(Counter(r['label'] for r in fold))}")
    if args.audit_only:
        return

    print("Caching photos at 1536 px...")
    for r in train + val + test:
        r["image"] = _cache(r)

    model, val_f1 = _train(train, val)

    # Test, read once.
    truth = np.array([r["label"] for r in test])
    predicted = np.array([CLASSES[i] for i in _predict(model, [r["image"] for r in test]).argmax(1)])
    macro = _macro(truth, predicted)
    recalls = per_class_recall(truth, predicted, CLASSES)
    healthy_precision = float(precision_score(truth, predicted, labels=["healthy"], average="micro", zero_division=0))
    print(f"\nTEST ({len(test)} photos)  macro-F1 {macro:.4f}  accuracy {(truth == predicted).mean():.4f}  "
          f"recall {recalls}  healthy precision {healthy_precision:.4f}")
    per_cultivar = {c: float((truth[m] == predicted[m]).mean())
                    for c in sorted({r["cultivar"] for r in test})
                    for m in [np.array([r["cultivar"] == c for r in test])]}
    print("  accuracy by cultivar:", {c: round(v, 3) for c, v in per_cultivar.items()})

    report.check("macro-F1 (test)", BAR_MACRO_F1, macro)
    for c in CLASSES:
        report.check(f"recall({c})", BAR_CLASS_RECALL, recalls[c])
    report.check("precision(healthy)", BAR_HEALTHY_PRECISION, healthy_precision)
    report.note(f"validation macro-F1 {val_f1:.4f}; {len(test)} test photos - weak evidence by construction")
    report.note("PROVISIONAL regardless: six Turkish cultivars under one lab setup")
    print(report.render())

    import torch

    torch.save({"state_dict": model.state_dict(), "passed_bar": report.passed, "architecture": ARCH,
                "classes": CLASSES, "cache_width": CACHE_WIDTH, "crop": CROP, "grid": GRID},
               paths.WHEAT_KERNEL_MODEL)
    paths.WHEAT_KERNEL_MODEL.with_name("wheat_kernel_damage_metrics.json").write_text(json.dumps({
        "passed_bar": report.passed, "macro_f1": macro, "recall": recalls,
        "healthy_precision": healthy_precision, "accuracy_by_cultivar": per_cultivar,
        "validation_macro_f1": val_f1, "test_photos": len(test),
        "minutes": round((time.time() - started) / 60, 1),
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Saved -> {paths.WHEAT_KERNEL_MODEL.relative_to(paths.REPO_ROOT)}")


if __name__ == "__main__":
    main()
