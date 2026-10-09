"""Soil type from a photograph. Two candidates, one bar, same test set.

Run:  python -m ml.training.train_soil_type_model

Candidates:
  (a) HSV histogram + texture -> RandomForest  (classical, ~1 MB artifact)
  (b) MobileNetV3-Small transfer learning      (pretrained, ~6 MB artifact)

Whichever clears the bar and scores higher is the one to serve. If neither
clears it, neither ships and the existing region-based `soilLookup.js` stands
alone — which is the current behaviour, so that is not a regression.

## Why (a) exists at all, given (b) is available

The inherited script's docstring explains that it started as MobileNetV2
transfer learning and fell back to hand-engineered features because that
environment could not reach `storage.googleapis.com` to download ImageNet
weights (403, a network policy rather than a code bug). **That constraint does
not apply here** — pretrained weights download fine, which was verified before
this script was written.

So (a) is no longer a fallback. It is kept as a genuine competitor, because
the inherited reasoning for it is sound: soil type from a photo is dominated
by colour (red laterite vs black cotton soil vs pale alluvial vs grey cinder),
and if a 1 MB classical model matches a pretrained CNN on this data, it is the
better thing to serve.

## This feature is additive, never a replacement

The farmer already gets a soil type from their district via `soilLookup.js`.
A photo model layered on top has to be clearly better than that default to be
worth anything, which is why the bar is 0.80 against a 0.534 majority
baseline rather than merely "better than chance".

## Leakage check runs before any number is trusted

295 training and 73 test images is small enough that a handful of
near-duplicate frames spanning the split could manufacture the entire margin.
An average-hash comparison runs first and its result is reported. Duplicates
found are removed from training, not noted and ignored.

## Cinder is reported but not barred

The test set has 6 Cinder images, giving recall a resolution of 0.167. Any
threshold on that would be measuring noise. Cinder is also the one class
`soil_to_crop_bridge.py` cannot map into the crop model's vocabulary at all,
so its practical value is limited regardless.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split

from ml import paths
from ml.evaluation import Report, per_class_recall
from ml.features.soil_image import FEATURE_VERSION, IMG_SIZE, extract_features, image_digest

# Bars from MODEL_BARS.md section 7.
BAR_ACCURACY = 0.80
BAR_CLASS_RECALL = 0.60
BARRED_CLASSES = ["Alluvial Soil", "Black Soil", "Red Soil"]
UNBARRED_CLASSES = ["Cinder Soil"]

RANDOM_STATE = 42
CNN_EPOCHS = 30
CNN_BATCH = 16


def _list_images(directory: Path) -> list[tuple[Path, str]]:
    items: list[tuple[Path, str]] = []
    for class_dir in sorted(p for p in directory.iterdir() if p.is_dir()):
        for image in sorted(class_dir.iterdir()):
            if image.is_file():
                items.append((image, class_dir.name))
    return items


def _leakage_check(train_items, test_items, report: Report) -> set:
    """Average-hash overlap between the train and test directories."""
    test_hashes = {}
    for path, label in test_items:
        test_hashes.setdefault(image_digest(path), []).append((path.name, label))

    duplicates = []
    for path, label in train_items:
        digest = image_digest(path)
        if digest in test_hashes:
            duplicates.append((path, label, test_hashes[digest]))

    if duplicates:
        print(f"\nLEAKAGE: {len(duplicates)} training images duplicate a test image")
        for path, label, matches in duplicates[:5]:
            print(f"  {label}/{path.name}  ==  {matches[0][1]}/{matches[0][0]}")
        report.note(
            f"{len(duplicates)} near-duplicate images spanned the train/test "
            f"boundary and were REMOVED from training before fitting"
        )
    else:
        print("\nLeakage check: no near-duplicate images span the train/test split")
        report.note("leakage check ran: no near-duplicates across the train/test split")
    return {path for path, _, _ in duplicates}


def _features_for(items) -> tuple[np.ndarray, np.ndarray]:
    X = np.stack([extract_features(path) for path, _ in items])
    y = np.array([label for _, label in items])
    return X, y


def _train_classical(X_tr, y_tr, X_val, y_val):
    """Depth-constrained RandomForest, selected on validation.

    Depth is constrained deliberately. The inherited disease model used the
    same unconstrained configuration on a similar feature count and produced a
    214 MB artifact at 18.6% accuracy - fully grown trees memorising the
    training set. Small data plus 55 features is exactly where that happens.
    """
    best = None
    for max_depth in (6, 10, 16, None):
        for min_leaf in (1, 2, 4):
            model = RandomForestClassifier(
                n_estimators=400,
                max_depth=max_depth,
                min_samples_leaf=min_leaf,
                class_weight="balanced",
                random_state=RANDOM_STATE,
                n_jobs=-1,
            )
            model.fit(X_tr, y_tr)
            score = accuracy_score(y_val, model.predict(X_val))
            if best is None or score > best[0]:
                best = (score, model, {"max_depth": max_depth, "min_samples_leaf": min_leaf})
    score, model, params = best
    print(f"  (a) selected {params}, validation accuracy {score:.4f}")
    return model


def _train_cnn(train_items, val_items, classes):
    """MobileNetV3-Small with a frozen backbone and a retrained head.

    The backbone is frozen rather than fine-tuned end to end: with ~190
    training images, updating 2.5M parameters would overfit long before it
    generalised. Augmentation (flip, rotation, colour jitter) is applied to
    stretch what little data there is.
    """
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, Dataset
    from PIL import Image

    from ml.features.cnn import build_mobilenet_v3, soil_eval_transform, soil_train_transform

    torch.manual_seed(RANDOM_STATE)
    index = {name: i for i, name in enumerate(classes)}

    # Shared with ml/algorithms/soil_type_prediction.py via ml/features/cnn.py.
    train_tf = soil_train_transform()
    eval_tf = soil_eval_transform()

    class SoilDataset(Dataset):
        def __init__(self, items, tf):
            self.items, self.tf = items, tf

        def __len__(self):
            return len(self.items)

        def __getitem__(self, i):
            path, label = self.items[i]
            with Image.open(path) as handle:
                image = handle.convert("RGB")
            return self.tf(image), index[label]

    model = build_mobilenet_v3("mobilenet_v3_small", len(classes), pretrained=True)
    for param in model.features.parameters():
        param.requires_grad = False

    counts = Counter(label for _, label in train_items)
    weights = torch.tensor(
        [len(train_items) / (len(classes) * counts[c]) for c in classes], dtype=torch.float
    )
    criterion = nn.CrossEntropyLoss(weight=weights)
    optimiser = torch.optim.Adam(
        [p for p in model.parameters() if p.requires_grad], lr=1e-3
    )

    train_loader = DataLoader(SoilDataset(train_items, train_tf), batch_size=CNN_BATCH, shuffle=True)
    val_loader = DataLoader(SoilDataset(val_items, eval_tf), batch_size=CNN_BATCH)

    best_state, best_acc = None, -1.0
    for epoch in range(CNN_EPOCHS):
        model.train()
        for images, labels in train_loader:
            optimiser.zero_grad()
            loss = criterion(model(images), labels)
            loss.backward()
            optimiser.step()

        model.eval()
        correct = total = 0
        with torch.no_grad():
            for images, labels in val_loader:
                correct += (model(images).argmax(1) == labels).sum().item()
                total += labels.size(0)
        accuracy = correct / total
        if accuracy > best_acc:
            # Early-stopping on validation, so the epoch count is chosen by the
            # data rather than by whatever CNN_EPOCHS happens to be.
            best_acc, best_state = accuracy, {k: v.clone() for k, v in model.state_dict().items()}
        if epoch % 5 == 0 or epoch == CNN_EPOCHS - 1:
            print(f"    epoch {epoch:2d}  val acc {accuracy:.4f}")

    model.load_state_dict(best_state)
    print(f"  (b) best validation accuracy {best_acc:.4f}")
    return model, eval_tf, index


def _cnn_predict(model, eval_tf, index, items):
    import torch
    from PIL import Image

    inverse = {v: k for k, v in index.items()}
    model.eval()
    predictions = []
    with torch.no_grad():
        for path, _ in items:
            with Image.open(path) as handle:
                tensor = eval_tf(handle.convert("RGB")).unsqueeze(0)
            predictions.append(inverse[int(model(tensor).argmax(1).item())])
    return np.array(predictions)


def _evaluate(name, y_true, y_pred, report: Report) -> float:
    accuracy = accuracy_score(y_true, y_pred)
    recalls = per_class_recall(y_true, y_pred, BARRED_CLASSES + UNBARRED_CLASSES)
    print(f"\n--- {name} ---")
    print(f"accuracy {accuracy:.4f}")
    for label, score in recalls.items():
        flag = "" if label in BARRED_CLASSES else "   (reported, not barred)"
        print(f"  recall({label:14s}) {score:.4f}{flag}")
    print(classification_report(y_true, y_pred, zero_division=0))

    report.check(f"{name}: accuracy", BAR_ACCURACY, float(accuracy))
    for label in BARRED_CLASSES:
        report.check(f"{name}: recall({label})", BAR_CLASS_RECALL, recalls[label])
    return float(accuracy)


def main() -> None:
    train_dir = paths.require(paths.SOIL_IMAGES_TRAIN)
    test_dir = paths.require(paths.SOIL_IMAGES_TEST)

    train_items = _list_images(train_dir)
    test_items = _list_images(test_dir)
    classes = sorted({label for _, label in train_items})
    print(f"train: {len(train_items)} images   test: {len(test_items)} images")
    print(f"classes: {classes}")
    print("train distribution:", dict(Counter(label for _, label in train_items)))
    print("test  distribution:", dict(Counter(label for _, label in test_items)))

    report = Report("Soil type from photo")
    duplicates = _leakage_check(train_items, test_items, report)
    if duplicates:
        train_items = [(p, l) for p, l in train_items if p not in duplicates]
        print(f"training on {len(train_items)} images after removing duplicates")

    # Split by DIGEST GROUP, not by image. The training directory contains
    # near-duplicates of its own (the first run split naively and validation
    # accuracy came out at exactly 1.0000, which is what tipped this off), so
    # splitting per-image would seat copies of the same photo on both sides of
    # the fit/validation boundary and make validation useless for selection.
    groups: dict[str, list] = {}
    for path, label in train_items:
        groups.setdefault(image_digest(path), []).append((path, label))
    group_keys = list(groups)
    group_labels = [groups[k][0][1] for k in group_keys]
    duplicate_groups = sum(1 for k in group_keys if len(groups[k]) > 1)
    print(
        f"{len(train_items)} training images collapse into {len(group_keys)} "
        f"distinct images ({duplicate_groups} have internal duplicates)"
    )
    report.note(
        f"the training directory itself contains duplicates: {len(train_items)} "
        f"images are only {len(group_keys)} distinct ones; fit/val was split by "
        f"digest group so copies cannot straddle the boundary"
    )

    fit_keys, val_keys = train_test_split(
        group_keys, test_size=0.2, random_state=RANDOM_STATE, stratify=group_labels
    )
    fit_items = [item for k in fit_keys for item in groups[k]]
    val_items = [item for k in val_keys for item in groups[k]]
    print(f"fit: {len(fit_items)}   val: {len(val_items)}   test: {len(test_items)} (untouched)")

    majority = Counter(label for _, label in train_items).most_common(1)[0][0]
    baseline = float(np.mean([label == majority for _, label in test_items]))
    print(f"majority-class baseline on test: {baseline:.4f}  ({majority})")
    report.note(f"majority-class baseline on the test set is {baseline:.4f}")

    print("\nExtracting colour/texture features...")
    X_fit, y_fit = _features_for(fit_items)
    X_val, y_val = _features_for(val_items)
    X_test, y_test = _features_for(test_items)

    print("\n(a) classical CV + RandomForest")
    classical = _train_classical(X_fit, y_fit, X_val, y_val)
    accuracy_a = _evaluate("(a) classical", y_test, classical.predict(X_test), report)

    print("\n(b) MobileNetV3-Small transfer learning")
    cnn, eval_tf, index = _train_cnn(fit_items, val_items, classes)
    y_pred_b = _cnn_predict(cnn, eval_tf, index, test_items)
    accuracy_b = _evaluate("(b) mobilenetv3", y_test, y_pred_b, report)

    winner = "(a) classical" if accuracy_a >= accuracy_b else "(b) mobilenetv3"
    report.note(
        f"candidate accuracies - classical {accuracy_a:.4f}, mobilenetv3 "
        f"{accuracy_b:.4f}; better candidate is {winner}"
    )
    report.note(
        "Cinder recall is reported but not barred: 6 test images give it a "
        "resolution of 0.167"
    )
    report.note("additive to the region-based soilLookup.js, never a replacement")
    print(report.render())

    paths.ensure_artifacts_dir()
    joblib.dump(
        {
            "model": classical,
            "class_names": classes,
            "img_size": IMG_SIZE,
            "feature_version": FEATURE_VERSION,
            "test_accuracy": accuracy_a,
        },
        paths.SOIL_TYPE_MODEL,
    )
    import torch

    torch.save(
        {
            "state_dict": cnn.state_dict(),
            "classes": classes,
            "architecture": "mobilenet_v3_small",
            "test_accuracy": accuracy_b,
        },
        paths.SOIL_TYPE_CNN_MODEL,
    )
    (paths.ARTIFACTS_DIR / "soil_type_comparison.json").write_text(
        json.dumps(
            {
                "classical_accuracy": accuracy_a,
                "mobilenetv3_accuracy": accuracy_b,
                "baseline_accuracy": baseline,
                "winner": winner,
                "passed_bar": report.passed,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\nSaved both candidates -> {paths.ARTIFACTS_DIR.relative_to(paths.REPO_ROOT)}")


if __name__ == "__main__":
    main()
