"""Does the leaf model's test score survive when test images have no close
training neighbour? A scene-level leakage check.

Run:  python -m ml.training.audit_leaf_scene_leakage --crop sugarcane

## Why this exists

The training script's duplicate check catches the *same photograph* — resized,
recompressed, flipped or rotated. It cannot catch *the same leaf photographed
twice*: a burst of shots seconds apart, or a slight reframing. Those have
different pixels and different hashes, so they pass the check. If such pairs
straddle the train/test boundary, the test fold partly measures recognition of
a leaf the model has already seen, and the score overstates performance on a
new farmer's new photo.

Sugarcane scoring 0.99 macro-F1 on validation, on a dataset already shown to
contain 614 conflicting-label duplicates, was reason enough to check.

## Method

1. Rebuild the exact split the training script used (same seed, same cache,
   same grouping).
2. Embed every train and test image with an **untuned ImageNet MobileNetV3-Large**.
   The fine-tuned model is deliberately not used: it has learned to cluster
   same-class images, so it would report high similarity for different leaves
   of the same disease and confound "same scene" with "same class".
3. For each test image, find its most similar training image by cosine
   similarity.
4. Bucket the test images by that similarity and report the trained model's
   accuracy in each bucket.

The verdict is read from the lowest-similarity bucket. If accuracy there
collapses, the headline number was memory.

## A pass here is necessary, not sufficient

This check only asks whether test images *look like* training images. Photos
from one capture session also share lighting, background and camera settings,
and a model can learn those as a shortcut ("this background means this
class") that survives a low image-similarity score. The session-grouped split in
`train_leaf_condition_model.py` is the authoritative check; this script is the
cheap first look that told us to run it.
"""

from __future__ import annotations

import argparse
from collections import Counter

import numpy as np

from ml import paths
from ml.evaluation import Report
from ml.leaf_conditions import LEAF_CONDITIONS
from ml.training.train_leaf_condition_model import (
    _LeafDataset,
    _cache_and_digest,
    _group,
    _index,
    _split,
)

BUCKETS = [(0.97, 1.01, "near-copy (>= 0.97)"), (0.92, 0.97, "similar (0.92-0.97)"), (-1.0, 0.92, "dissimilar (< 0.92)")]


def _embed(records):
    import torch
    from torch.utils.data import DataLoader
    from torchvision.models import MobileNet_V3_Large_Weights, mobilenet_v3_large

    from ml.features.cnn import leaf_eval_transform

    net = mobilenet_v3_large(weights=MobileNet_V3_Large_Weights.DEFAULT)
    net.classifier = torch.nn.Identity()  # pooled 960-d features
    net.eval()
    loader = DataLoader(_LeafDataset(records, {r["folder"]: 0 for r in records}, leaf_eval_transform()), batch_size=64)
    chunks = []
    with torch.no_grad():
        for images, _ in loader:
            chunks.append(torch.nn.functional.normalize(net(images), dim=1).numpy())
    return np.concatenate(chunks)


def _predict_trained(crop, test_records):
    import torch
    from torch.utils.data import DataLoader

    from ml.features.cnn import build_mobilenet_v3, leaf_eval_transform

    checkpoint = torch.load(paths.leaf_condition_model(crop), map_location="cpu", weights_only=False)
    classes = checkpoint["classes"]
    model = build_mobilenet_v3(checkpoint["architecture"], len(classes), pretrained=False)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    index = {c: i for i, c in enumerate(classes)}
    loader = DataLoader(_LeafDataset(test_records, index, leaf_eval_transform()), batch_size=64)
    predictions = []
    with torch.no_grad():
        for images, _ in loader:
            predictions.append(model(images).argmax(1).numpy())
    return np.array([classes[i] for i in np.concatenate(predictions)])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--crop", required=True, choices=sorted(LEAF_CONDITIONS))
    crop = parser.parse_args().crop

    items = _index(crop)
    records = _cache_and_digest(crop, items)
    groups, _ = _group(records, Report("scene audit"), crop)
    train_records, _val, test_records = _split(groups)
    print(f"\n{crop}: train {len(train_records)}  test {len(test_records)} (split rebuilt identically)")

    print("Embedding with untuned ImageNet MobileNetV3-Large...")
    train_emb = _embed(train_records)
    test_emb = _embed(test_records)
    similarity = test_emb @ train_emb.T
    nearest = similarity.argmax(axis=1)
    nearest_sim = similarity.max(axis=1)
    nearest_same_label = np.array(
        [train_records[j]["folder"] == test_records[i]["folder"] for i, j in enumerate(nearest)]
    )

    truth = np.array([r["folder"] for r in test_records])
    predicted = _predict_trained(crop, test_records)
    correct = predicted == truth

    print(f"\nNearest-training-image similarity: median {np.median(nearest_sim):.3f}, "
          f"p10 {np.percentile(nearest_sim, 10):.3f}, p90 {np.percentile(nearest_sim, 90):.3f}")
    print(f"\n{'bucket':24s} {'n':>5s} {'share':>7s} {'accuracy':>9s} {'nn same label':>14s}")
    rows = {}
    for low, high, name in BUCKETS:
        mask = (nearest_sim >= low) & (nearest_sim < high)
        n = int(mask.sum())
        acc = float(correct[mask].mean()) if n else float("nan")
        same = float(nearest_same_label[mask].mean()) if n else float("nan")
        rows[name] = (n, acc)
        print(f"{name:24s} {n:5d} {n / len(truth):7.1%} {acc:9.4f} {same:14.1%}")
    print(f"{'all test images':24s} {len(truth):5d} {'100.0%':>7s} {correct.mean():9.4f}")

    n_low, acc_low = rows[BUCKETS[-1][2]]
    print()
    if n_low < 30:
        print(f"INCONCLUSIVE: only {n_low} test images are dissimilar from every training image.")
    elif acc_low >= 0.85:
        print(f"NOT NEAR-COPY DEPENDENT: accuracy {acc_low:.4f} on the {n_low} test images with no "
              f"close training neighbour. This does not rule out session-level shortcuts "
              f"(shared light/background) - only a session-grouped split does.")
    else:
        print(f"LEAKAGE-DEPENDENT: accuracy falls to {acc_low:.4f} on the {n_low} test images with "
              f"no close training neighbour.")

    misses = Counter(f"{t} -> {p}" for t, p, ok in zip(truth, predicted, correct) if not ok)
    if misses:
        print("\nAll test errors (truth -> prediction):")
        for pair, n in misses.most_common():
            print(f"  {n:3d}  {pair}")


if __name__ == "__main__":
    main()
