"""Tobacco leaf lesion segmentation (model 17): lesion vs healthy/background.

Run:
    python -m ml.training.train_tobacco_lesion_segmentation
    python -m ml.training.train_tobacco_lesion_segmentation --audit-only

Bar: MODEL_BARS.md section 9, 2026-09-24 entry "model 17". Lesion IoU at least
0.50 on real test tiles, and per-tile lesion-share MAE at most half the
training-mean baseline's.

## Why the shipped split is discarded

The 320 real tiles come from 84 photos, and 34 of those photos have tiles in
both shipped splits. 77% of tiles are augmentations with no recorded source.
Evaluating on that split would measure memory. Instead:

1. Real tiles are grouped into capture sessions from the timestamp in their
   file name (`IMG_YYYYMMDD_HHMMSS`, photos 10 s or less apart), and sessions
   are split 60/20/20. Validation and test hold **real tiles only**.
2. A `data1/` augmented tile joins the session of its most similar real tile
   (untuned ImageNet features, similarity >= 0.84, the p99 of unrelated real
   pairs) and is dropped if that session is not in training. An unlinked
   `data1/` tile within 0.80 of any validation or test tile is also dropped.
3. `data2/` augmented tiles derive from originals absent from this dataset, so
   they go to training.

Model and augmentation are shared with the wheat canopy model
(`train_wheat_segmentation.py`): LR-ASPP on MobileNetV3-Large, random crops,
flips and 90-degree rotations.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import time

import numpy as np
import pandas as pd
from PIL import Image
from sklearn.model_selection import GroupShuffleSplit

from ml import paths
from ml.evaluation import Report
from ml.training.train_wheat_segmentation import _embed, _predict, _SegDataset, build_model

CLASSES = ["background", "lesion"]
LESION = 1

BAR_LESION_IOU = 0.50
BAR_SHARE_VS_BASELINE = 0.50

SESSION_GAP_SECONDS = 10
LINK_THRESHOLD = 0.84  # p99 similarity of tiles from different real photos
DROP_NEAR_EVAL = 0.80
SAMPLES_PER_EPOCH = 480
BATCH_SIZE = 8
MAX_EPOCHS = 25
PATIENCE = 4
SEED = 42


def _records() -> pd.DataFrame:
    root = paths.require(paths.TOBACCO_SEGMENTATION_ROOT)
    frames = []
    for split in ("train", "val"):
        meta = pd.read_csv(root / f"{split}_metadata.csv")
        meta["image"] = [root / split / "images" / f for f in meta["image_file"]]
        meta["mask"] = [root / split / "masks" / f for f in meta["mask_file"]]
        frames.append(meta)
    df = pd.concat(frames, ignore_index=True)
    df["folder"] = df["source_path"].str.split("/").str[0]
    df["photo"] = df["source_path"].str.extract(r"(IMG_\d{8}_\d{6})")[0]
    real = df["type"] == "real"
    if df.loc[real, "photo"].isna().any():
        raise SystemExit("Real tiles without a parseable IMG_ timestamp")
    return df


def _sessions(df: pd.DataFrame) -> pd.Series:
    """Session id per real photo: photos 10 s or less apart share a session."""
    times = pd.to_datetime(df["photo"].dropna().unique(), format="IMG_%Y%m%d_%H%M%S")
    order = np.sort(times)
    session, sessions = 0, {}
    for i, t in enumerate(order):
        if i and (t - order[i - 1]) / np.timedelta64(1, "s") > SESSION_GAP_SECONDS:
            session += 1
        sessions[pd.Timestamp(t).strftime("IMG_%Y%m%d_%H%M%S")] = session
    return df["photo"].map(sessions)


def _assign(df: pd.DataFrame, report: Report) -> pd.DataFrame:
    df = df.copy()
    real = (df["type"] == "real").to_numpy()
    df["session"] = _sessions(df)

    sessions = df.loc[real, "session"].unique()
    outer = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=SEED)
    rest, test = next(outer.split(sessions, groups=sessions))
    inner = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=SEED)  # 0.25 x 0.8 = 20%
    fit, val = next(inner.split(sessions[rest], groups=sessions[rest]))
    fold_of = {**{s: "train" for s in sessions[rest][fit]}, **{s: "val" for s in sessions[rest][val]},
               **{s: "test" for s in sessions[test]}}
    df["fold"] = df["session"].map(fold_of)

    embeddings = _embed(list(df["image"]))
    real_idx = np.where(real)[0]
    eval_idx = np.where(real & df["fold"].isin(["val", "test"]).to_numpy())[0]
    similarity = embeddings @ embeddings[real_idx].T

    linked = dropped = 0
    for i in np.where(~real)[0]:
        if df.at[i, "folder"] != "data1":
            df.at[i, "fold"] = "train"
            continue
        best = int(similarity[i].argmax())
        if similarity[i, best] >= LINK_THRESHOLD:
            linked += 1
            df.at[i, "fold"] = "train" if df.at[real_idx[best], "fold"] == "train" else "dropped"
        else:
            near_eval = (embeddings[i] @ embeddings[eval_idx].T).max() >= DROP_NEAR_EVAL
            df.at[i, "fold"] = "dropped" if near_eval else "train"
        dropped += df.at[i, "fold"] == "dropped"

    counts = df.groupby(["fold", "type"]).size().unstack(fill_value=0)
    print(f"Real tiles: {real.sum()} from {df.loc[real, 'photo'].nunique()} photos in "
          f"{len(sessions)} capture sessions (gap <= {SESSION_GAP_SECONDS}s)")
    print(f"data1 augmented linked to a real tile (>= {LINK_THRESHOLD}): {linked}; dropped as "
          f"copies of validation/test material: {dropped}")
    print(counts.to_string())
    report.note(f"shipped split discarded (34 photos straddled it); real tiles split by "
                f"{len(sessions)} capture sessions; {dropped} augmented tiles dropped as "
                f"copies of validation/test photos")
    return df


def _share(mask: np.ndarray) -> float:
    return float((mask == LESION).mean())


def _metrics(predictions, truths, baseline_share: float) -> dict:
    intersection = sum(int(((p == LESION) & (t == LESION)).sum()) for p, t in zip(predictions, truths))
    union = sum(int(((p == LESION) | (t == LESION)).sum()) for p, t in zip(predictions, truths))
    true_share = np.array([_share(t) for t in truths])
    pred_share = np.array([_share(p) for p in predictions])
    return {
        "lesion_iou": intersection / union if union else float("nan"),
        "share_mae": float(np.abs(pred_share - true_share).mean()),
        "share_mae_baseline": float(np.abs(baseline_share - true_share).mean()),
        "mean_true_share": float(true_share.mean()),
        "mean_pred_share": float(pred_share.mean()),
        "tiles": len(truths),
    }


def _pairs(df, fold):
    rows = df[df["fold"] == fold]
    return list(zip(rows["image"], rows["mask"]))


def _train(train_pairs, val_pairs, baseline_share):
    import torch
    from torch.utils.data import DataLoader, RandomSampler

    torch.manual_seed(SEED)
    random.seed(SEED)
    model = build_model(pretrained=True, num_classes=len(CLASSES))
    optimizer = torch.optim.AdamW(
        [{"params": model.backbone.parameters(), "lr": 1e-4},
         {"params": model.classifier.parameters(), "lr": 1e-3}],
        weight_decay=1e-4,
    )
    counts = np.zeros(len(CLASSES))
    for _, mask in train_pairs:
        counts += np.bincount((np.array(Image.open(mask)) > 0).ravel(), minlength=len(CLASSES))
    weights = 1.0 / np.sqrt(counts / counts.sum())
    criterion = torch.nn.CrossEntropyLoss(weight=torch.tensor(weights / weights.mean(), dtype=torch.float32))

    dataset = _SegDataset(train_pairs, train=True)
    sampler = RandomSampler(dataset, replacement=True, num_samples=SAMPLES_PER_EPOCH,
                            generator=torch.Generator().manual_seed(SEED))
    loader = DataLoader(dataset, batch_size=BATCH_SIZE, sampler=sampler)

    best, best_state, stale = -1.0, None, 0
    for epoch in range(1, MAX_EPOCHS + 1):
        started = time.time()
        model.train()
        for x, y in loader:
            y = (y > 0).long()
            optimizer.zero_grad()
            criterion(model(x)["out"], y).backward()
            optimizer.step()
        val = _metrics(*_binarise(*_predict(model, val_pairs)), baseline_share)
        improved = val["lesion_iou"] > best
        if improved:
            best, stale = val["lesion_iou"], 0
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        else:
            stale += 1
        print(f"  epoch {epoch:2d}  val lesion IoU {val['lesion_iou']:.4f}  share MAE "
              f"{val['share_mae']:.4f} (baseline {val['share_mae_baseline']:.4f})  "
              f"{'*' if improved else ' '}  ({time.time() - started:.0f}s)", flush=True)
        if stale >= PATIENCE:
            print(f"  early stop: no validation gain in {PATIENCE} epochs")
            break
    model.load_state_dict(best_state)
    return model, best


def _binarise(predictions, truths):
    return predictions, [(t > 0).astype(np.int64) for t in truths]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()

    report = Report("Tobacco lesion segmentation (model 17)")
    df = _assign(_records(), report)
    train_pairs, val_pairs, test_pairs = _pairs(df, "train"), _pairs(df, "val"), _pairs(df, "test")
    baseline_share = float(np.mean([_share(np.array(Image.open(m)) > 0) for _, m in train_pairs]))
    print(f"Training-mean lesion share (baseline): {baseline_share:.4f}")
    if args.audit_only:
        return

    started = time.time()
    model, val_iou = _train(train_pairs, val_pairs, baseline_share)
    minutes = (time.time() - started) / 60

    # Test, read once: real tiles only.
    result = _metrics(*_binarise(*_predict(model, test_pairs)), baseline_share)
    ratio = result["share_mae"] / result["share_mae_baseline"]
    print(f"\nTEST ({result['tiles']} real tiles)  lesion IoU {result['lesion_iou']:.4f}  share MAE "
          f"{result['share_mae']:.4f} (baseline {result['share_mae_baseline']:.4f}, ratio {ratio:.3f})  "
          f"mean share true {result['mean_true_share']:.4f} / predicted {result['mean_pred_share']:.4f}")

    report.check("lesion IoU (real test tiles)", BAR_LESION_IOU, result["lesion_iou"])
    report.check("lesion-share MAE / baseline MAE", BAR_SHARE_VS_BASELINE, ratio, higher_is_better=False)
    report.note(f"validation lesion IoU {val_iou:.4f}")
    report.note("PROVISIONAL regardless: two days of photos from one source; disease not named; "
                "close-up tiles, not whole leaves")
    print(report.render())

    import torch

    torch.save({
        "state_dict": model.state_dict(),
        "passed_bar": report.passed,
        "architecture": "lraspp_mobilenet_v3_large",
        "classes": CLASSES,
        "test_metrics": result,
    }, paths.TOBACCO_LESION_MODEL)
    fold_counts = df.groupby(["fold", "type"]).size().unstack(fill_value=0).to_dict()
    paths.TOBACCO_LESION_MODEL.with_name("tobacco_lesion_segmentation_metrics.json").write_text(json.dumps({
        "passed_bar": report.passed, "validation_lesion_iou": val_iou, "test": result,
        "share_mae_ratio": ratio, "folds": fold_counts, "train_minutes": round(minutes, 1),
    }, indent=2, default=str) + "\n", encoding="utf-8")
    df[["sample_id", "source_path", "type", "fold"]].to_csv(
        paths.TOBACCO_LESION_MODEL.with_name("tobacco_lesion_folds.csv"), index=False)
    print(f"\nSaved -> {paths.TOBACCO_LESION_MODEL.relative_to(paths.REPO_ROOT)}  (trained in {minutes:.1f} min)")


if __name__ == "__main__":
    main()
