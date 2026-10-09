"""Wheat canopy segmentation (model 14): background / head / stem / leaf.

Run:
    python -m ml.training.train_wheat_segmentation
    python -m ml.training.train_wheat_segmentation --audit-only

Bar: MODEL_BARS.md section 9, 2026-09-24 entry "model 14". Head IoU at least
0.60, plant-vs-background IoU at least 0.80, canopy-cover MAE at most 0.05 and
at most half the constant baseline's, heading balanced accuracy at least 0.85.

## What the model is for

Not disease. The pixel labels support two outputs a farmer can use: whether
wheat heads are visible (a growth-stage signal), and canopy cover (a coarse
vigour signal). Both are computed from the predicted mask by fixed rules
written into the bar before training, so neither can be tuned on test.

## Pipeline

1. **Near-copy control.** No site, session or EXIF metadata exists, so images
   are compared with untuned ImageNet features. Train images at similarity
   0.93 or more are grouped before carving validation; train images that
   close to any test image are removed from train. The shipped val set is the
   test fold and is never altered.
2. **Train** LR-ASPP with a MobileNetV3-Large backbone, starting from
   torchvision's COCO/VOC segmentation weights with the two 21-class
   classifiers replaced by 4-class ones. Random crops, flips and 90-degree
   rotations: the photos are top-down, so orientation carries no meaning.
3. **Select on validation** mean IoU, with early stopping.
4. **Test once** and apply the bar.
"""

from __future__ import annotations

import argparse
import json
import random
import time

import numpy as np
from PIL import Image
from sklearn.model_selection import GroupShuffleSplit

from ml import paths
from ml.evaluation import Report
from ml.features.cnn import IMAGENET_MEAN, IMAGENET_STD, leaf_eval_transform

CLASSES = ["background", "head", "stem", "leaf"]
BACKGROUND, HEAD = 0, 1

BAR_HEAD_IOU = 0.60
BAR_PLANT_IOU = 0.80
BAR_COVER_MAE = 0.05
BAR_COVER_VS_BASELINE = 0.50
BAR_HEADING_BALANCED_ACCURACY = 0.85

HEAD_RULE = 0.005  # an image is "headed" when heads cover at least 0.5% of it
SIMILARITY_THRESHOLD = 0.93
VAL_FRACTION = 0.20
TRAIN_CROP = 320
BATCH_SIZE = 8
MAX_EPOCHS = 25
PATIENCE = 4
SEED = 42


def _pairs(split: str) -> list[tuple]:
    root = paths.require(paths.WHEAT_SEGMENTATION_ROOT) / split
    images = sorted((root / "images").glob("*.jpg"))
    pairs = [(image, root / "masks" / f"{image.stem}.png") for image in images]
    missing = [m.name for _, m in pairs if not m.exists()]
    if missing:
        raise SystemExit(f"{split}: {len(missing)} images have no mask, e.g. {missing[:3]}")
    return pairs


def _embed(images) -> np.ndarray:
    """L2-normalised untuned ImageNet MobileNetV3-Large features."""
    import torch
    from torchvision.models import MobileNet_V3_Large_Weights, mobilenet_v3_large

    net = mobilenet_v3_large(weights=MobileNet_V3_Large_Weights.DEFAULT)
    net.classifier = torch.nn.Identity()
    net.eval()
    transform = leaf_eval_transform()
    chunks = []
    with torch.no_grad():
        for start in range(0, len(images), 32):
            batch = torch.stack([transform(Image.open(p).convert("RGB")) for p in images[start:start + 32]])
            chunks.append(torch.nn.functional.normalize(net(batch), dim=1).numpy())
    return np.concatenate(chunks)


def _near_copy_control(train, test, report: Report):
    """Drop train images near a test image; group the rest by similarity."""
    train_emb = _embed([image for image, _ in train])
    test_emb = _embed([image for image, _ in test])

    near_test = (train_emb @ test_emb.T).max(axis=1) >= SIMILARITY_THRESHOLD
    kept = [i for i in range(len(train)) if not near_test[i]]
    print(f"Train images at similarity >= {SIMILARITY_THRESHOLD} to a test image: "
          f"{int(near_test.sum())} (removed from train; test untouched)")
    report.note(f"{int(near_test.sum())} train images removed as near-copies of test images; test kept as shipped")

    parent = list(range(len(kept)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    emb = train_emb[kept]
    similar = np.triu(emb @ emb.T >= SIMILARITY_THRESHOLD, 1)
    links = 0
    for a, b in zip(*np.where(similar)):
        if find(a) != find(b):
            parent[find(a)] = find(b)
            links += 1
    groups = [find(i) for i in range(len(kept))]
    print(f"Near-copy links within train: {links}; {len(kept)} images form {len(set(groups))} groups")
    return [train[i] for i in kept], groups


def _load(pair):
    image = Image.open(pair[0]).convert("RGB")
    mask = np.array(Image.open(pair[1]), dtype=np.int64)
    return image, mask


class _SegDataset:
    def __init__(self, pairs, train: bool):
        import torch
        from torchvision import transforms

        self.pairs, self.train = pairs, train
        self.normalize = transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD)
        self.jitter = transforms.ColorJitter(0.2, 0.2, 0.15, 0.02)
        self.to_tensor = transforms.ToTensor()
        self.torch = torch

    def __len__(self):
        return len(self.pairs)

    def __getitem__(self, i):
        image, mask = _load(self.pairs[i])
        if self.train:
            width, height = image.size
            left = random.randint(0, width - TRAIN_CROP)
            top = random.randint(0, height - TRAIN_CROP)
            image = image.crop((left, top, left + TRAIN_CROP, top + TRAIN_CROP))
            mask = mask[top:top + TRAIN_CROP, left:left + TRAIN_CROP]
            image = self.jitter(image)
            x = self.to_tensor(image)
            y = self.torch.from_numpy(mask.copy())
            if random.random() < 0.5:
                x, y = x.flip(-1), y.flip(-1)
            if random.random() < 0.5:
                x, y = x.flip(-2), y.flip(-2)
            k = random.randint(0, 3)
            x, y = self.torch.rot90(x, k, (-2, -1)), self.torch.rot90(y, k, (-2, -1))
            return self.normalize(x.contiguous()), y.contiguous()
        return self.normalize(self.to_tensor(image)), self.torch.from_numpy(mask)


def build_model(pretrained: bool = True, num_classes: int = len(CLASSES)):
    import torch
    from torchvision.models.segmentation import LRASPP_MobileNet_V3_Large_Weights, lraspp_mobilenet_v3_large

    if pretrained:
        model = lraspp_mobilenet_v3_large(weights=LRASPP_MobileNet_V3_Large_Weights.DEFAULT)
    else:
        # Serving: every weight comes from the checkpoint, so fetch nothing.
        model = lraspp_mobilenet_v3_large(weights=None, weights_backbone=None)
    head = model.classifier
    head.low_classifier = torch.nn.Conv2d(head.low_classifier.in_channels, num_classes, 1)
    head.high_classifier = torch.nn.Conv2d(head.high_classifier.in_channels, num_classes, 1)
    return model


def _predict(model, pairs):
    """Predicted and true masks for every pair, full resolution."""
    import torch

    dataset = _SegDataset(pairs, train=False)
    model.eval()
    predictions, truths = [], []
    with torch.no_grad():
        for i in range(len(dataset)):
            x, y = dataset[i]
            predictions.append(model(x.unsqueeze(0))["out"][0].argmax(0).numpy())
            truths.append(y.numpy())
    return predictions, truths


def _metrics(predictions, truths, baseline_cover: float) -> dict:
    confusion = np.zeros((len(CLASSES), len(CLASSES)), dtype=np.int64)
    for p, t in zip(predictions, truths):
        confusion += np.bincount(t.ravel() * len(CLASSES) + p.ravel(), minlength=len(CLASSES) ** 2).reshape(
            len(CLASSES), len(CLASSES))
    intersection = np.diag(confusion)
    union = confusion.sum(0) + confusion.sum(1) - intersection
    iou = {c: float(intersection[i] / union[i]) if union[i] else float("nan") for i, c in enumerate(CLASSES)}

    plant_true = sum(int(((t != BACKGROUND) & (p != BACKGROUND)).sum()) for p, t in zip(predictions, truths))
    plant_union = sum(int(((t != BACKGROUND) | (p != BACKGROUND)).sum()) for p, t in zip(predictions, truths))

    cover_true = np.array([(t != BACKGROUND).mean() for t in truths])
    cover_pred = np.array([(p != BACKGROUND).mean() for p in predictions])
    headed_true = np.array([(t == HEAD).mean() >= HEAD_RULE for t in truths])
    headed_pred = np.array([(p == HEAD).mean() >= HEAD_RULE for p in predictions])
    tpr = (headed_pred & headed_true).sum() / max(headed_true.sum(), 1)
    tnr = (~headed_pred & ~headed_true).sum() / max((~headed_true).sum(), 1)

    return {
        "iou": iou,
        "mean_iou": float(np.nanmean(list(iou.values()))),
        "plant_iou": plant_true / plant_union if plant_union else float("nan"),
        "cover_mae": float(np.abs(cover_pred - cover_true).mean()),
        "cover_mae_baseline": float(np.abs(baseline_cover - cover_true).mean()),
        "heading_balanced_accuracy": float((tpr + tnr) / 2),
        "heading_recall": float(tpr),
        "heading_specificity": float(tnr),
        "headed_images": int(headed_true.sum()),
        "unheaded_images": int((~headed_true).sum()),
    }


def _class_weights(pairs):
    counts = np.zeros(len(CLASSES))
    for _, mask_path in pairs:
        counts += np.bincount(np.array(Image.open(mask_path)).ravel(), minlength=len(CLASSES))
    weights = 1.0 / np.sqrt(counts / counts.sum())
    return weights / weights.mean()


def _train(train_pairs, val_pairs, baseline_cover):
    import torch
    from torch.utils.data import DataLoader

    torch.manual_seed(SEED)
    random.seed(SEED)
    model = build_model(pretrained=True)
    head_params = list(model.classifier.parameters())
    optimizer = torch.optim.AdamW(
        [{"params": model.backbone.parameters(), "lr": 1e-4}, {"params": head_params, "lr": 1e-3}],
        weight_decay=1e-4,
    )
    weights = torch.tensor(_class_weights(train_pairs), dtype=torch.float32)
    criterion = torch.nn.CrossEntropyLoss(weight=weights)
    loader = DataLoader(_SegDataset(train_pairs, train=True), batch_size=BATCH_SIZE, shuffle=True,
                        generator=torch.Generator().manual_seed(SEED))

    best, best_state, stale = -1.0, None, 0
    for epoch in range(1, MAX_EPOCHS + 1):
        started = time.time()
        model.train()
        for x, y in loader:
            optimizer.zero_grad()
            loss = criterion(model(x)["out"], y)
            loss.backward()
            optimizer.step()
        val = _metrics(*_predict(model, val_pairs), baseline_cover)
        improved = val["mean_iou"] > best
        if improved:
            best, stale = val["mean_iou"], 0
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        else:
            stale += 1
        print(f"  epoch {epoch:2d}  val mIoU {val['mean_iou']:.4f}  head {val['iou']['head']:.3f}  "
              f"plant {val['plant_iou']:.3f}  cover MAE {val['cover_mae']:.3f}  "
              f"{'*' if improved else ' '}  ({time.time() - started:.0f}s)", flush=True)
        if stale >= PATIENCE:
            print(f"  early stop: no validation gain in {PATIENCE} epochs")
            break
    model.load_state_dict(best_state)
    return model, best


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()

    report = Report("Wheat canopy segmentation (model 14)")
    train_all, test = _pairs("train"), _pairs("val")
    print(f"Shipped: train {len(train_all)}, val {len(test)} (val is the test fold)")
    train_kept, groups = _near_copy_control(train_all, test, report)

    splitter = GroupShuffleSplit(n_splits=1, test_size=VAL_FRACTION, random_state=SEED)
    fit_idx, val_idx = next(splitter.split(train_kept, groups=groups))
    train_pairs = [train_kept[i] for i in fit_idx]
    val_pairs = [train_kept[i] for i in val_idx]
    print(f"Split by group: train {len(train_pairs)}  val {len(val_pairs)}  test {len(test)}")

    baseline_cover = float(np.mean([(np.array(Image.open(m)) != BACKGROUND).mean() for _, m in train_pairs]))
    print(f"Constant cover baseline (train mean): {baseline_cover:.3f}")
    if args.audit_only:
        return

    started = time.time()
    model, val_miou = _train(train_pairs, val_pairs, baseline_cover)
    minutes = (time.time() - started) / 60

    # Test, read once.
    result = _metrics(*_predict(model, test), baseline_cover)
    print(f"\nTEST  mIoU {result['mean_iou']:.4f}  plant IoU {result['plant_iou']:.4f}  "
          f"cover MAE {result['cover_mae']:.4f} (baseline {result['cover_mae_baseline']:.4f})")
    print("  IoU per class: " + "  ".join(f"{c} {v:.4f}" for c, v in result["iou"].items()))
    print(f"  heading: balanced accuracy {result['heading_balanced_accuracy']:.4f}  recall "
          f"{result['heading_recall']:.4f}  specificity {result['heading_specificity']:.4f}  "
          f"({result['headed_images']} headed / {result['unheaded_images']} not)")

    report.check("head IoU (test)", BAR_HEAD_IOU, result["iou"]["head"])
    report.check("plant-vs-background IoU (test)", BAR_PLANT_IOU, result["plant_iou"])
    report.check("canopy cover MAE (test)", BAR_COVER_MAE, result["cover_mae"], higher_is_better=False)
    report.check("cover MAE / baseline MAE (test)", BAR_COVER_VS_BASELINE,
                 result["cover_mae"] / result["cover_mae_baseline"], higher_is_better=False)
    report.check("heading balanced accuracy (test)", BAR_HEADING_BALANCED_ACCURACY,
                 result["heading_balanced_accuracy"])
    report.note(f"validation mIoU {val_miou:.4f}; test mIoU {result['mean_iou']:.4f} "
                f"(leaf {result['iou']['leaf']:.4f}, stem {result['iou']['stem']:.4f} - not barred)")
    report.note("PROVISIONAL regardless: a 40% sample of GWFSS; sites and cameras unknown "
                "relative to Indian fields; top-down canopy photos only")
    print(report.render())

    import torch

    torch.save(
        {
            "state_dict": model.state_dict(),
            "passed_bar": report.passed,
            "architecture": "lraspp_mobilenet_v3_large",
            "classes": CLASSES,
            "head_rule": HEAD_RULE,
            "test_metrics": result,
        },
        paths.WHEAT_SEGMENTATION_MODEL,
    )
    metrics_path = paths.WHEAT_SEGMENTATION_MODEL.with_name("wheat_canopy_segmentation_metrics.json")
    metrics_path.write_text(json.dumps({
        "passed_bar": report.passed,
        "validation_mean_iou": val_miou,
        "test": result,
        "sizes": {"train": len(train_pairs), "val": len(val_pairs), "test": len(test)},
        "train_minutes": round(minutes, 1),
    }, indent=2) + "\n", encoding="utf-8")
    print(f"\nSaved -> {paths.WHEAT_SEGMENTATION_MODEL.relative_to(paths.REPO_ROOT)}  (trained in {minutes:.1f} min)")


if __name__ == "__main__":
    main()
