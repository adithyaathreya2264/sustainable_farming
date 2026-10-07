"""Leaf condition from a photo, one model per crop. MobileNetV3-Large.

Run:
    python -m ml.training.train_leaf_condition_model --crop sugarcane
    python -m ml.training.train_leaf_condition_model --crop rice
    python -m ml.training.train_leaf_condition_model --crop sugarcane --audit-only

Bars: MODEL_BARS.md section 9, 2026-09-23 entry (model 10). Macro-F1 at
least 0.85, every class recall at least 0.70, healthy precision at least 0.90.

## Relation to the parked disease model

`ml/training/parked/train_disease_cnn_model.py` trained a from-scratch CNN on
PlantDoc for 2 epochs on about 320 images with the test set doubling as
validation. It was parked because PlantDoc holds none of the app's crops. This
is a replacement, not a revival: crop-specific data, a pretrained backbone, a
held-out test fold, and a leakage check that runs before anything is fitted.

## Pipeline

1. **Index.** Walk the crop's dataset root for folders that directly contain
   images. Sugarcane's disease folders sit one level deeper than its healthy
   and dried folders, so a fixed layout would silently miss classes. Every
   folder must appear in `ml/leaf_conditions.py`; an unknown class stops the
   run instead of training on an unlabelled category.
2. **Cache + digest, one decode pass.** Each photo goes through
   `prepare_leaf_image` — the same function serving calls — and is stored as a
   lossless PNG, so training sees exactly the pixels a served photo would
   produce. A flip- and rotation-invariant hash is computed at the same time.
3. **Group duplicates, then capture sessions.** Images sharing a hash, once
   confirmed pixel by pixel, are duplicates. Images of one class taken within
   10 seconds of each other (EXIF capture time) are one capture session. Every
   split is made by the union of both, so neither a copied photo nor a burst
   of frames of the same leaf can straddle a fold boundary. The session step
   was added after a first run whose test fold turned out to be mostly
   near-identical frames of training images; see MODEL_BARS.md section 9.
   **A group whose members carry different labels is dropped entirely**: one
   photograph cannot be both conditions, so the pair is a labelling error with
   no way to tell which label is right. (The disease Q&A corpus's cross-pair
   duplicates were kept because a *text* symptom genuinely can be shared by
   two diseases. A *photo* cannot be of two leaves.)
4. **Split** 60/20/20 by group with `StratifiedGroupKFold`. The test fold
   is reported in sessions as well as images, because sessions are the
   independent units: 60 test images from 2 sessions is 2 observations.
5. **Train, two phases, both judged on validation:**
   - A: backbone frozen, classifier head only.
   - B: continue from A's best, unfreezing the last feature blocks at a lower
     learning rate.
   Whichever phase scored higher validation macro-F1 is the model. Frozen
   BatchNorm layers are held in eval mode — `model.train()` would otherwise
   keep updating their running statistics even with gradients off, quietly
   drifting a backbone that is meant to be fixed.
6. **Test once**, score against the bar, save.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image
from sklearn.metrics import classification_report, confusion_matrix, f1_score, precision_score

from ml import paths
from ml.evaluation import Report, per_class_recall
from ml.features.cnn import (
    LEAF_PREPROCESS_VERSION,
    PREP_SIZE,
    build_mobilenet_v3,
    dihedral_digest,
    leaf_eval_transform,
    leaf_train_transform,
    prepare_leaf_image,
)
from ml.leaf_conditions import (
    CONDITIONAL_CROPS,
    EXCLUDED_FOLDERS,
    LABEL_PATH_LEVEL,
    LEAF_CONDITIONS,
    condition_for,
    healthy_folder,
)

# Bars — MODEL_BARS.md section 9, 2026-09-23.
BAR_MACRO_F1 = 0.85
BAR_CLASS_RECALL = 0.70
BAR_HEALTHY_PRECISION = 0.90

ARCH = "mobilenet_v3_large"
RANDOM_STATE = 42
BATCH = 32
PHASE_A_EPOCHS = 6
PHASE_B_EPOCHS = 10
PATIENCE = 3
# How many of MobileNetV3-Large's 17 feature blocks phase B unfreezes. The
# last blocks hold the most task-specific features; unfreezing everything on
# a few thousand images would overfit and would triple CPU training time.
UNFREEZE_LAST_BLOCKS = 5
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".jfif", ".heic"}


# --------------------------------------------------------------------------
# Indexing and caching
# --------------------------------------------------------------------------


# Per-class cap on images, drawn at random before caching, for datasets too
# large for the CPU budget. Grouping then runs on the sample as usual, so the
# leakage control is unchanged. User decision 2026-09-25 (onion).
MAX_PER_CLASS = {"onion": 1500, "onion bulb": 1500}


def _index(crop: str) -> list[tuple[Path, str]]:
    root = paths.require(paths.LEAF_IMAGE_ROOTS[crop])
    items: list[tuple[Path, str]] = []
    for directory in sorted(p for p in root.rglob("*") if p.is_dir()):
        candidates = sorted(
            f for f in directory.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_SUFFIXES
        )
        # Zero-byte files hold no image (coffee ships 102 of them); report, don't crash.
        images = [f for f in candidates if f.stat().st_size > 0]
        if len(images) < len(candidates):
            print(f"Skipping {len(candidates) - len(images)} empty (0-byte) files in {directory.name!r}")
        if images:
            reason = EXCLUDED_FOLDERS.get(crop, {}).get(directory.name)
            if reason:
                print(f"Excluding folder {directory.name!r} ({len(images)} images): {reason}")
                continue
            level = LABEL_PATH_LEVEL.get(crop)
            label = directory.name if level is None else directory.relative_to(root).parts[level]
            condition_for(crop, label)  # raises on an unregistered class
            items.extend((f, label) for f in images)

    cap = MAX_PER_CLASS.get(crop)
    if cap:
        rng = np.random.default_rng(RANDOM_STATE)
        by_label: dict[str, list] = defaultdict(list)
        for item in items:
            by_label[item[1]].append(item)
        items = []
        for label, members in sorted(by_label.items()):
            keep = sorted(rng.choice(len(members), min(cap, len(members)), replace=False))
            items.extend(members[i] for i in keep)
            print(f"Capped {label!r}: {len(keep)} of {len(members)} images (random, seed {RANDOM_STATE})")

    found = {folder for _, folder in items}
    missing = set(LEAF_CONDITIONS[crop]) - found
    if missing:
        raise SystemExit(f"Registered classes with no images on disk for {crop}: {sorted(missing)}")
    return items


def _cache_path(crop: str, source: Path) -> Path:
    stat = source.stat()
    key = f"{source.as_posix()}|{stat.st_size}|{int(stat.st_mtime)}|v{LEAF_PREPROCESS_VERSION}"
    return paths.IMAGE_CACHE_DIR / paths.crop_slug(crop) / f"{hashlib.sha1(key.encode()).hexdigest()}.png"


def _cache_and_digest(crop: str, items) -> list[dict]:
    """Prepare every image once; return records with cache path and digest."""
    manifest_path = paths.IMAGE_CACHE_DIR / f"{paths.crop_slug(crop)}_manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    records, built = [], 0
    started = time.time()
    for i, (source, folder) in enumerate(items):
        cached = _cache_path(crop, source)
        digest = manifest.get(cached.name)
        if digest is None or not cached.exists():
            prepared = prepare_leaf_image(source)
            cached.parent.mkdir(parents=True, exist_ok=True)
            prepared.save(cached, format="PNG")
            digest = dihedral_digest(prepared)
            manifest[cached.name] = digest
            built += 1
        records.append({"source": source, "cache": cached, "folder": folder, "digest": digest})
        if (i + 1) % 1000 == 0:
            print(f"  prepared {i + 1}/{len(items)}  ({time.time() - started:.0f}s)")

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest))
    print(f"  cache: {built} newly prepared, {len(items) - built} reused")
    return records


# Mean absolute pixel difference, 0-255 scale, under the best of the 8 flips and
# rotations, below which two images sharing a hash are treated as the same
# photo. Chosen from the measured sugarcane distribution: of 309 hash groups
# whose members carried conflicting labels, 286 differed by under 1/255 and
# none fell between 1 and 5, while the remaining 23 differed by 5 to 15+ -
# far enough apart to be different photographs that happened to share a hash.
# 5 sits in that gap. (Judged on pixel distance, not visual inspection.)
DUPLICATE_PIXEL_THRESHOLD = 5.0


def _pixel_distance(a: np.ndarray, b: np.ndarray) -> float:
    return min(
        min(np.abs(a - np.rot90(b, k)).mean(), np.abs(a - np.fliplr(np.rot90(b, k))).mean())
        for k in range(4)
    )


def _verify_groups(by_digest: dict[str, list[dict]]) -> list[list[dict]]:
    """Split each hash group into pixel-verified duplicate clusters.

    A 256-bit average hash is a candidate generator, not proof. Leaf photos are
    visually uniform enough that different leaves occasionally share a hash,
    and treating those as duplicates would discard good images as "label
    conflicts" they never were. Members are merged only when their pixels
    actually match.
    """
    verified: list[list[dict]] = []
    for members in by_digest.values():
        if len(members) == 1:
            verified.append(members)
            continue
        pixels = [
            np.asarray(Image.open(m["cache"]).convert("RGB"), dtype=np.float32) for m in members
        ]
        parent = list(range(len(members)))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                if _pixel_distance(pixels[i], pixels[j]) < DUPLICATE_PIXEL_THRESHOLD:
                    parent[find(i)] = find(j)
        clusters: dict[int, list[dict]] = defaultdict(list)
        for i, member in enumerate(members):
            clusters[find(i)].append(member)
        verified.extend(clusters.values())
    return verified


def _group(records, report: Report, crop: str | None = None) -> tuple[list[list[dict]], dict]:
    by_digest: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_digest[record["digest"]].append(record)

    hash_groups_with_copies = sum(1 for g in by_digest.values() if len(g) > 1)
    groups = _verify_groups(by_digest)
    print(
        f"  {hash_groups_with_copies} hash groups with more than one member; "
        f"after pixel verification (threshold {DUPLICATE_PIXEL_THRESHOLD}/255) "
        f"{sum(1 for g in groups if len(g) > 1)} are true duplicate groups"
    )
    duplicated = [g for g in groups if len(g) > 1]
    conflicting = [g for g in groups if len({r["folder"] for r in g}) > 1]
    clean = [g for g in groups if len({r["folder"] for r in g}) == 1]

    stats = {
        "images": len(records),
        "distinct_images": len(groups),
        "groups_with_duplicates": len(duplicated),
        "images_in_duplicate_groups": sum(len(g) for g in duplicated),
        "cross_label_groups_dropped": len(conflicting),
        "images_dropped_for_label_conflict": sum(len(g) for g in conflicting),
    }
    print(
        f"\nDuplicates: {stats['images']} images are {stats['distinct_images']} distinct; "
        f"{stats['groups_with_duplicates']} groups hold {stats['images_in_duplicate_groups']} "
        f"images with at least one copy (flips and rotations included)"
    )
    if conflicting:
        print(
            f"LABEL CONFLICT: {len(conflicting)} duplicate groups carry more than one "
            f"label - {stats['images_dropped_for_label_conflict']} images dropped"
        )
        for g in conflicting[:5]:
            print("   ", sorted(Counter(r["folder"] for r in g).items()))
        report.note(
            f"{len(conflicting)} duplicate groups ({stats['images_dropped_for_label_conflict']} "
            f"images) carried conflicting labels and were dropped - one photo cannot "
            f"be two conditions, and there is no basis for choosing a label"
        )
    report.note(
        f"{stats['images']} images collapse to {stats['distinct_images']} distinct "
        f"(flip/rotation-invariant hash, then pixel-verified)"
    )
    groups, session_stats = _merge_sessions(
        clean, report, SIMILARITY_GROUPING.get(crop), SHOT_SEQUENCE.get(crop), FILENAME_TIME.get(crop),
        SOURCE_ID.get(crop), crop in COMPLETE_LINKAGE,
    )
    stats.update(session_stats)
    return groups, stats


# Images of one class whose EXIF capture times are this close are one capture
# session. Measured on the sugarcane dataset (MODEL_BARS.md section 9, second
# 2026-09-23 entry): photos were taken in continuous streams, and consecutive
# frames are largely the same leaf, light and moment. 10 seconds is the finest
# defensible unit; at 30 seconds several classes collapse to one or two sessions.
SESSION_GAP_SECONDS = 10


def _capture_time(path: Path, name_pattern: str | None = None) -> float | None:
    """EXIF DateTimeOriginal (or DateTime) as a POSIX timestamp, if present.

    With `name_pattern` (two groups: YYYYMMDD and HHMMSS), a file without EXIF
    falls back to the time written in its name.
    """
    from datetime import datetime

    try:
        with Image.open(path) as image:
            exif = image.getexif()
            raw = (exif.get_ifd(0x8769).get(36867) if exif else None) or exif.get(306)
        if raw:
            return datetime.strptime(raw, "%Y:%m:%d %H:%M:%S").timestamp()
    except (OSError, ValueError, TypeError):
        pass
    if name_pattern:
        match = re.search(name_pattern, path.name)
        if match:
            try:
                return datetime.strptime(match.group(1) + match.group(2), "%Y%m%d%H%M%S").timestamp()
            except ValueError:
                return None
    return None


# Datasets without EXIF whose file names carry the capture time. Every
# augmented copy of a photo keeps the photo's name, so it lands in the photo's
# session. MODEL_BARS.md section 9, model 19.
FILENAME_TIME = {"vegetables": r"IMG_(\d{8})_(\d{6})"}

# Datasets that store several derived files per source photo under one name
# stem. Within a class, every file whose name yields the same source id is one
# group, before sessions or similarity are applied. MODEL_BARS.md section 9,
# models 20-27.
#   tea:          IMG_0242_result.jpg + 10 processed variants (blur, noise,
#                 grey, binary, rotate +-15) -> "IMG_0242"
#   tomato fruit: "d (1).jpg" and "d (1).png" -> "d (1)"
SOURCE_ID = {
    "tea": r"^(IMG_\d+)",
    "tomato fruit": r"^([a-z] \(\d+\))",
}


# Crops whose images mostly lack capture times, so the session split cannot
# catch non-geometric copies (brightened, zoomed, recropped). For these, photos
# whose untuned ImageNet features are at least this similar are grouped too.
# Rice: 0.93 sits above the 99th percentile of unrelated same-class pairs
# (0.912); at 0.93 no grouped pair crosses a disease label and the largest group
# is 17 photos. See MODEL_BARS.md section 9, model 12. Sugarcane is
# deliberately absent: its recorded result used the session split alone and
# must stay reproducible.
SIMILARITY_GROUPING = {
    "rice": 0.93,
    # Models 20-27, by the rule in MODEL_BARS.md section 9 (2026-09-25):
    # max(0.93, p99 of random same-class pairs rounded up), from
    # `python -m ml.training.calibrate_similarity`. p99 values: coffee 0.864,
    # cauliflower 0.889, cauliflower curd 0.947, potato 0.888, tomato fruit 0.889.
    "coffee": 0.93,
    "cauliflower": 0.93,
    "cauliflower curd": 0.95,
    "potato": 0.93,
    "tomato fruit": 0.93,
}

# Tasks grouped by complete rather than single linkage (see _merge_sessions):
# their near-copy links chained whole classes into one group at audit.
# MODEL_BARS.md section 9, models 23 and 27 correction (2026-09-25).
COMPLETE_LINKAGE = frozenset({"cauliflower curd", "tomato fruit"})

# Crops whose filenames carry a sequential camera shot number, used in place
# of EXIF capture time (pearl millet has none). Two rules, both within a class:
#
# 1. Every image with the same shot number is one group. "Blastnormal0DSC_0002"
#    and "Blastnormal2DSC_0002" are different crops of one photograph - too
#    different for the pixel check, the same shot all the same.
# 2. Shot n and shot n+1 are one session when their representatives (the
#    lowest "normalN" crop) are at least this similar in untuned ImageNet
#    features. Measured 2026-09-24: adjacent shots have median similarity 0.95
#    against 0.69 for shots more than 20 apart - they are bursts of one leaf.
#    96% of adjacent pairs clear 0.85, so a session boundary almost always marks
#    a real change of scene. Only adjacent shots are linked: a global similarity
#    threshold would chain, because about 1% of distant pairs also exceed 0.93.
#    MODEL_BARS.md section 9, model 13.
SHOT_SEQUENCE = {"pearl millet": (r"DSC_?(\d+)", 0.85)}


def _embed_records(records) -> np.ndarray:
    """L2-normalised features from an untuned ImageNet MobileNetV3-Large.

    Untuned on purpose: a model fine-tuned on these classes has learned to pull
    same-class images together, so it would rate different leaves of one
    disease as near-copies and over-merge groups.
    """
    import torch
    from torch.utils.data import DataLoader
    from torchvision.models import MobileNet_V3_Large_Weights, mobilenet_v3_large

    net = mobilenet_v3_large(weights=MobileNet_V3_Large_Weights.DEFAULT)
    net.classifier = torch.nn.Identity()
    net.eval()
    dataset = _LeafDataset(records, {r["folder"]: 0 for r in records}, leaf_eval_transform())
    chunks = []
    with torch.no_grad():
        for images, _ in DataLoader(dataset, batch_size=64):
            chunks.append(torch.nn.functional.normalize(net(images), dim=1).numpy())
    return np.concatenate(chunks)


def _merge_sessions(
    clusters: list[list[dict]],
    report: Report,
    similarity_threshold: float | None = None,
    shot_sequence: tuple[str, float] | None = None,
    name_time_pattern: str | None = None,
    source_pattern: str | None = None,
    complete_linkage: bool = False,
) -> tuple[list[list[dict]], dict]:
    """Union duplicate clusters with capture sessions into split groups.

    The duplicate check only catches the same photograph. It cannot catch a
    burst of different frames of the same leaf, which is what these datasets
    mostly consist of - a scene-level audit found a sugarcane test image's
    nearest training image at median similarity 0.980, against 0.652 for two
    unrelated leaves of the same class, and 78% of those neighbours were
    within three filenames of it. Grouping by capture session keeps a burst on
    one side of every fold boundary, so the test fold measures sessions the
    model has never seen - the closest proxy available for a new farmer's photo.

    Images with no capture time form their own session; they cannot be placed.
    """
    records = [r for cluster in clusters for r in cluster]
    parent = list(range(len(records)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        parent[find(a)] = find(b)

    source_links = 0
    if source_pattern is not None:
        first_of_source: dict[tuple[str, str], int] = {}
        for i, record in enumerate(records):
            match = re.search(source_pattern, record["source"].name)
            if match is None:
                continue
            key = (record["folder"], match.group(1))
            if key in first_of_source:
                if find(i) != find(first_of_source[key]):
                    union(i, first_of_source[key])
                    source_links += 1
            else:
                first_of_source[key] = i
        print(f"\nSource-id grouping ({source_pattern}): {len(first_of_source)} source photos; "
              f"{source_links} files joined to their source")

    starts, position = [], 0
    for cluster in clusters:
        starts.append(position)
        for offset in range(1, len(cluster)):
            union(position, position + offset)
        position += len(cluster)

    shot_links = sequence_links = 0
    sequence_sessions: dict[str, int] = {}
    if shot_sequence is not None:
        pattern, threshold = shot_sequence
        # Representative per (class, shot): the first filename in sort order,
        # which is the lowest "normalN" crop present.
        representative: dict[tuple[str, int], int] = {}
        for i in sorted(range(len(records)), key=lambda i: records[i]["source"].name):
            match = re.search(pattern, records[i]["source"].name)
            if match is None:
                raise SystemExit(f"No shot number in {records[i]['source'].name!r}")
            key = (records[i]["folder"], int(match.group(1)))
            if key in representative:
                if find(i) != find(representative[key]):
                    union(i, representative[key])
                    shot_links += 1
            else:
                representative[key] = i
        keys = sorted(representative)
        embeddings = _embed_records([records[representative[k]] for k in keys])
        position = {k: j for j, k in enumerate(keys)}
        for folder in sorted({k[0] for k in keys}):
            sessions = 0
            for key in (k for k in keys if k[0] == folder):
                following = (folder, key[1] + 1)
                sessions += 1
                if following in position and float(
                    embeddings[position[key]] @ embeddings[position[following]]
                ) >= threshold:
                    a, b = representative[key], representative[following]
                    if find(a) != find(b):
                        union(a, b)
                        sequence_links += 1
                    sessions -= 1
            sequence_sessions[folder] = sessions
        print(
            f"\nShot grouping ({pattern}): {len(keys)} distinct shots; {shot_links} crop "
            f"links; consecutive shots linked at similarity >= {threshold}: {sequence_links}"
        )

    similarity_links = 0
    if similarity_threshold is not None:
        # Every image is compared, not one representative per duplicate
        # cluster. The first implementation compared representatives, and
        # because a cluster's first member is stored in an arbitrary
        # orientation, a brightened copy stored rotated looked dissimilar to
        # its original and escaped grouping. An audit then found 19% of rice
        # test images with a training near-copy at >= 0.97. ImageNet features
        # are not rotation-invariant; comparing all members lets matching
        # orientations meet.
        embeddings = _embed_records(records)
        if complete_linkage:
            # Complete linkage: a group holds only images that are ALL pairwise
            # at least this similar, so near-copy links cannot chain a whole
            # class into one component. Single linkage did exactly that for
            # cauliflower curd and tomato fruit (one test group per class).
            from scipy.cluster.hierarchy import fcluster, linkage
            from scipy.spatial.distance import pdist

            tree = linkage(pdist(embeddings, metric="cosine"), method="complete")
            clusters = fcluster(tree, t=1.0 - similarity_threshold, criterion="distance")
            first: dict[int, int] = {}
            for i, c in enumerate(clusters):
                if c in first:
                    if find(i) != find(first[c]):
                        union(i, first[c])
                        similarity_links += 1
                else:
                    first[c] = i
        else:
            similar = np.triu(embeddings @ embeddings.T >= similarity_threshold, 1)
            for a, b in zip(*np.where(similar)):
                if find(a) != find(b):
                    union(a, b)
                    similarity_links += 1
        print(
            f"\nSimilarity grouping (untuned ImageNet features >= {similarity_threshold}): "
            f"{similarity_links} near-copy links between distinct photos"
        )

    # Crops grouped by similarity skip the session step. Rice showed why: its
    # few timestamps sit almost entirely in one class (Bacterial blight), and
    # session links chained with similarity links into a single component of
    # 931 images, which no stratified split can use. Similarity grouping
    # already catches burst frames, which are near-identical by nature, so the
    # session step adds chaining without adding protection. MODEL_BARS.md
    # model 12, precondition 3.
    use_sessions = similarity_threshold is None and shot_sequence is None
    by_class: dict[str, list[tuple[float, int]]] = defaultdict(list)
    untimed = 0
    for i, record in enumerate(records):
        record["captured_at"] = _capture_time(record["source"], name_time_pattern) if use_sessions else None
        if record["captured_at"] is None:
            untimed += 1
        else:
            by_class[record["folder"]].append((record["captured_at"], i))

    sessions_per_class: dict[str, int] = dict(sequence_sessions)
    for folder, stamped in by_class.items():
        stamped.sort()
        sessions = 1
        for (previous, prev_i), (current, cur_i) in zip(stamped, stamped[1:]):
            if current - previous <= SESSION_GAP_SECONDS:
                union(prev_i, cur_i)
            else:
                sessions += 1
        sessions_per_class[folder] = sessions

    components: dict[int, list[dict]] = defaultdict(list)
    for i, record in enumerate(records):
        record["group"] = find(i)
        components[record["group"]].append(record)
    groups = list(components.values())

    if use_sessions:
        print(
            f"\nCapture sessions (gap <= {SESSION_GAP_SECONDS}s): {len(clusters)} distinct "
            f"photos form {len(groups)} independent groups"
            + (f"; {untimed} images had no capture time and stand alone" if untimed else "")
        )
    elif shot_sequence is not None:
        print(f"{len(clusters)} distinct photos form {len(groups)} independent shot-sequence sessions")
    else:
        print(f"{len(clusters)} distinct photos form {len(groups)} independent similarity groups (no session step)")
    for folder, n in sorted(sessions_per_class.items()):
        print(f"  {folder:26s} {n:4d} sessions")
    if use_sessions:
        kind = "capture-session"
    elif shot_sequence is not None:
        kind = f"shot-sequence session (consecutive shots at similarity >= {shot_sequence[1]})"
    else:
        kind = f"near-copy (similarity >= {similarity_threshold})"
    report.note(
        f"{len(clusters)} distinct photos form only {len(groups)} independent {kind} "
        f"groups; all splits were made by group, so no copy or burst straddles a "
        f"fold boundary"
    )
    return groups, {
        "session_gap_seconds": SESSION_GAP_SECONDS,
        "independent_groups": len(groups),
        "sessions_per_class": sessions_per_class,
        "images_without_capture_time": untimed,
        "similarity_threshold": similarity_threshold,
        "similarity_links": similarity_links,
        "shot_sequence": list(shot_sequence) if shot_sequence else None,
        "shot_links": shot_links,
        "source_pattern": source_pattern,
        "source_links": source_links,
        "sequence_links": sequence_links,
    }


def _split(groups):
    """60/20/20 by session group, stratified by class.

    StratifiedGroupKFold keeps every group whole while approximating each
    class's proportion in every fold. Fold 1 of 5 is test; fold 1 of the
    remaining 4 is validation.
    """
    from sklearn.model_selection import StratifiedGroupKFold

    records = [r for g in groups for r in g]
    labels = np.array([r["folder"] for r in records])
    group_ids = np.array([gi for gi, g in enumerate(groups) for _ in g])

    outer = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    rest, test = next(outer.split(np.zeros(len(records)), labels, group_ids))
    inner = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=RANDOM_STATE)
    train_sub, val_sub = next(inner.split(np.zeros(len(rest)), labels[rest], group_ids[rest]))

    pick = lambda idx: [records[i] for i in idx]  # noqa: E731
    return pick(rest[train_sub]), pick(rest[val_sub]), pick(test)


def _sessions_in(records) -> dict[str, int]:
    """Number of distinct session groups per class within a fold."""
    per_class: dict[str, set] = defaultdict(set)
    for record in records:
        per_class[record["folder"]].add(record["group"])
    return {folder: len(groups) for folder, groups in sorted(per_class.items())}


# --------------------------------------------------------------------------
# Training
# --------------------------------------------------------------------------


class _LeafDataset:
    def __init__(self, records, class_index, transform):
        self.records, self.class_index, self.transform = records, class_index, transform

    def __len__(self):
        return len(self.records)

    def __getitem__(self, i):
        record = self.records[i]
        with Image.open(record["cache"]) as handle:
            image = handle.convert("RGB")
        return self.transform(image), self.class_index[record["folder"]]


def _freeze(model, trainable_blocks: int) -> None:
    """Freeze all feature blocks except the last `trainable_blocks`."""
    blocks = list(model.features.children())
    cut = len(blocks) - trainable_blocks
    for i, block in enumerate(blocks):
        for param in block.parameters():
            param.requires_grad = i >= cut
    for param in model.classifier.parameters():
        param.requires_grad = True


def _train_mode(model, trainable_blocks: int) -> None:
    """model.train(), but frozen blocks keep BatchNorm in eval mode."""
    import torch.nn as nn

    model.train()
    blocks = list(model.features.children())
    for block in blocks[: len(blocks) - trainable_blocks]:
        for module in block.modules():
            if isinstance(module, nn.BatchNorm2d):
                module.eval()


def _predict(model, loader):
    import torch

    model.eval()
    predictions, truths = [], []
    with torch.no_grad():
        for images, labels in loader:
            predictions.append(model(images).argmax(1).numpy())
            truths.append(labels.numpy())
    return np.concatenate(truths), np.concatenate(predictions)


def _run_phase(name, model, loaders, criterion, trainable_blocks, lr_head, lr_backbone, epochs):
    import torch

    _freeze(model, trainable_blocks)
    head = list(model.classifier.parameters())
    backbone = [p for p in model.features.parameters() if p.requires_grad]
    groups = [{"params": head, "lr": lr_head}]
    if backbone:
        groups.append({"params": backbone, "lr": lr_backbone})
    optimiser = torch.optim.AdamW(groups, weight_decay=1e-4)

    best_f1, best_state, stale = -1.0, None, 0
    for epoch in range(epochs):
        started = time.time()
        _train_mode(model, trainable_blocks)
        for images, labels in loaders["train"]:
            optimiser.zero_grad()
            loss = criterion(model(images), labels)
            loss.backward()
            optimiser.step()

        y_true, y_pred = _predict(model, loaders["val"])
        val_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
        improved = val_f1 > best_f1
        if improved:
            best_f1, stale = val_f1, 0
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        else:
            stale += 1
        print(
            f"  [{name}] epoch {epoch + 1:2d}  val macro-F1 {val_f1:.4f}"
            f"{'  *' if improved else ''}   ({time.time() - started:.0f}s)"
        )
        if stale >= PATIENCE:
            print(f"  [{name}] early stop: no validation gain in {PATIENCE} epochs")
            break

    model.load_state_dict(best_state)
    return best_f1, best_state


def _train(train_records, val_records, classes):
    import torch
    from torch import nn
    from torch.utils.data import DataLoader

    torch.manual_seed(RANDOM_STATE)
    class_index = {name: i for i, name in enumerate(classes)}

    loaders = {
        "train": DataLoader(
            _LeafDataset(train_records, class_index, leaf_train_transform()),
            batch_size=BATCH,
            shuffle=True,
        ),
        "val": DataLoader(
            _LeafDataset(val_records, class_index, leaf_eval_transform()), batch_size=64
        ),
    }

    # Class weights, square-root tempered. Full inverse-frequency weighting on
    # sugarcane (Brown Spot 1,722 vs Pokkah Boeng 297) over-corrects and trades
    # away precision on the large classes; the square root keeps small classes
    # heard without letting them dominate the loss.
    counts = Counter(r["folder"] for r in train_records)
    weights = torch.tensor(
        [(len(train_records) / (len(classes) * counts[c])) ** 0.5 for c in classes],
        dtype=torch.float,
    )
    criterion = nn.CrossEntropyLoss(weight=weights, label_smoothing=0.1)

    model = build_mobilenet_v3(ARCH, len(classes), pretrained=True)

    print("\nPhase A: frozen backbone, classifier head only")
    f1_a, state_a = _run_phase(
        "A", model, loaders, criterion, trainable_blocks=0,
        lr_head=1e-3, lr_backbone=0.0, epochs=PHASE_A_EPOCHS,
    )

    print(f"\nPhase B: unfreeze last {UNFREEZE_LAST_BLOCKS} feature blocks")
    f1_b, state_b = _run_phase(
        "B", model, loaders, criterion, trainable_blocks=UNFREEZE_LAST_BLOCKS,
        lr_head=3e-4, lr_backbone=1e-4, epochs=PHASE_B_EPOCHS,
    )

    if f1_b >= f1_a:
        chosen, state, val_f1 = "B: partial fine-tune", state_b, f1_b
    else:
        chosen, state, val_f1 = "A: frozen backbone", state_a, f1_a
    model.load_state_dict(state)
    print(f"\nSelected on validation: phase {chosen}  (A {f1_a:.4f}, B {f1_b:.4f})")
    return model, chosen, {"phase_a_val_macro_f1": f1_a, "phase_b_val_macro_f1": f1_b, "val_macro_f1": val_f1}


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--crop", required=True, choices=sorted(LEAF_CONDITIONS))
    parser.add_argument("--audit-only", action="store_true", help="index, cache and dedup, then stop")
    args = parser.parse_args()
    crop = args.crop

    report = Report(f"Leaf condition from photo - {crop}")
    print(f"Indexing {crop} images...")
    items = _index(crop)
    print(f"{len(items)} images in {len({f for _, f in items})} classes:")
    for folder, n in sorted(Counter(f for _, f in items).items()):
        print(f"  {folder:26s} {n:5d}")

    print(f"\nPreparing images at {PREP_SIZE}px (lossless cache) and hashing...")
    records = _cache_and_digest(crop, items)
    groups, dedup_stats = _group(records, report, crop)

    train_records, val_records, test_records = _split(groups)
    print(f"\nSplit by group: train {len(train_records)}  val {len(val_records)}  test {len(test_records)}")
    classes = sorted({r["folder"] for g in groups for r in g})
    test_counts = Counter(r["folder"] for r in test_records)
    test_sessions = _sessions_in(test_records)
    print(f"{'class':26s} {'test images':>11s} {'test sessions':>14s}")
    for folder in sorted(test_counts):
        print(f"  {folder:24s} {test_counts[folder]:11d} {test_sessions.get(folder, 0):14d}")
    missing_from_test = sorted(set(LEAF_CONDITIONS[crop]) - set(test_counts))
    if missing_from_test:
        raise SystemExit(f"Classes with no test session - cannot be evaluated: {missing_from_test}")

    if args.audit_only:
        print(report.render().replace("CLEARS ITS BAR", "AUDIT ONLY - NOTHING TRAINED"))
        return

    started = time.time()
    model, chosen, val_scores = _train(train_records, val_records, classes)
    train_minutes = (time.time() - started) / 60

    # Test fold, read once.
    from torch.utils.data import DataLoader

    class_index = {name: i for i, name in enumerate(classes)}
    test_loader = DataLoader(
        _LeafDataset(test_records, class_index, leaf_eval_transform()), batch_size=64
    )
    y_true, y_pred = _predict(model, test_loader)
    true_names = np.array([classes[i] for i in y_true])
    pred_names = np.array([classes[i] for i in y_pred])

    macro_f1 = f1_score(true_names, pred_names, average="macro", zero_division=0)
    accuracy = float((true_names == pred_names).mean())
    recalls = per_class_recall(true_names, pred_names, classes)
    healthy = healthy_folder(crop)
    healthy_precision = (
        float(precision_score(true_names, pred_names, labels=[healthy], average="micro", zero_division=0))
        if healthy
        else None
    )
    majority = Counter(r["folder"] for r in train_records).most_common(1)[0][0]
    baseline = float((true_names == majority).mean())

    healthy_text = f"{healthy_precision:.4f}" if healthy_precision is not None else "n/a (no healthy class)"
    print(f"\nTEST  macro-F1 {macro_f1:.4f}   accuracy {accuracy:.4f}   "
          f"healthy precision {healthy_text}   majority baseline {baseline:.4f}")
    print("\nPer-class recall:")
    for folder, score in recalls.items():
        c = condition_for(crop, folder)
        print(
            f"  {folder:26s} {score:.4f}   images={test_counts[folder]:4d}   "
            f"sessions={test_sessions[folder]:3d}   [{c.category}]"
        )
    print("\n" + classification_report(true_names, pred_names, zero_division=0))
    matrix = confusion_matrix(true_names, pred_names, labels=classes)
    print("Confusion matrix (rows = truth, columns = prediction, order as per-class list above)")
    print(matrix)

    report.check("macro-F1 (test)", BAR_MACRO_F1, float(macro_f1))
    for folder, score in recalls.items():
        report.check(f"recall({folder}) [{test_sessions[folder]} test sessions]", BAR_CLASS_RECALL, score)
    if healthy:
        report.check(f"precision({healthy})", BAR_HEALTHY_PRECISION, healthy_precision)
    elif crop in CONDITIONAL_CROPS:
        excluded = EXCLUDED_FOLDERS.get(crop, {})
        report.note(
            ("healthy folder excluded from training (" + "; ".join(excluded.values()) + ")"
             if excluded else "no healthy class in this dataset")
            + ": the healthy-precision criterion cannot be computed, and a healthy leaf "
            "shown to this model will be named as a disease. Serving must only invoke "
            "it after a symptom is reported."
        )
    else:
        report.note("no healthy class (a grading task): the healthy-precision criterion does not apply")
    report.note(f"majority-class baseline accuracy {baseline:.4f} ({majority})")
    report.note(
        f"selected on validation: phase {chosen}; validation macro-F1 "
        f"{val_scores['val_macro_f1']:.4f} vs test {macro_f1:.4f}"
    )
    report.note(
        "PROVISIONAL regardless of metric: test images share source and capture "
        "conditions with training; field photos from Karnataka farms are a "
        "different distribution, so in-source accuracy overstates field accuracy"
    )
    print(report.render())

    import torch

    paths.ensure_artifacts_dir()
    registry = LEAF_CONDITIONS[crop]
    metrics = {
        "crop": crop,
        "passed_bar": report.passed,
        "selected_phase": chosen,
        **val_scores,
        "test_macro_f1": float(macro_f1),
        "test_accuracy": accuracy,
        "test_healthy_precision": healthy_precision,
        "test_recall": recalls,
        "test_counts": dict(test_counts),
        "test_sessions": test_sessions,
        "majority_baseline": baseline,
        "split_sizes": {"train": len(train_records), "val": len(val_records), "test": len(test_records)},
        "dedup": dedup_stats,
        "confusion_matrix": matrix.tolist(),
        "classes": classes,
        "train_minutes": round(train_minutes, 1),
    }
    torch.save(
        {
            "state_dict": model.state_dict(),
            "architecture": ARCH,
            "classes": classes,
            "condition_keys": [registry[c].key for c in classes],
            "preprocess_version": LEAF_PREPROCESS_VERSION,
            "passed_bar": report.passed,
            "metrics": metrics,
        },
        paths.leaf_condition_model(crop),
    )
    metrics_path = paths.ARTIFACTS_DIR / f"leaf_condition_{paths.crop_slug(crop)}_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(f"\nSaved -> {paths.leaf_condition_model(crop).relative_to(paths.REPO_ROOT)}")
    print(f"Metrics -> {metrics_path.relative_to(paths.REPO_ROOT)}   (trained in {train_minutes:.1f} min)")


if __name__ == "__main__":
    main()
