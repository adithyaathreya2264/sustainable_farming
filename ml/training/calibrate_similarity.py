"""Calibrate the near-copy similarity threshold for a leaf-pipeline task.

Run:
    python -m ml.training.calibrate_similarity --crop coffee

Applies the rule written in MODEL_BARS.md section 9 (models 20-28) before
training: threshold = max(0.93, 99th percentile of random same-class pairs,
rounded up to 0.01), on untuned ImageNet features, the features the grouping
itself uses. Prints the value to record in `SIMILARITY_GROUPING`; it never
looks at a label outcome or a trained model.
"""

from __future__ import annotations

import argparse
import math
from collections import defaultdict

import numpy as np

from ml.training.train_leaf_condition_model import _cache_and_digest, _embed_records, _index

FLOOR = 0.93
PAIRS_PER_CLASS = 20_000
SEED = 42


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--crop", required=True)
    crop = parser.parse_args().crop

    records = _cache_and_digest(crop, _index(crop))
    embeddings = _embed_records(records)
    by_class = defaultdict(list)
    for i, r in enumerate(records):
        by_class[r["folder"]].append(i)

    rng = np.random.default_rng(SEED)
    sims = []
    for members in by_class.values():
        if len(members) < 2:
            continue
        a = rng.choice(members, PAIRS_PER_CLASS)
        b = rng.choice(members, PAIRS_PER_CLASS)
        keep = a != b
        sims.append(np.einsum("ij,ij->i", embeddings[a[keep]], embeddings[b[keep]]))
    sims = np.concatenate(sims)
    p99 = float(np.percentile(sims, 99))
    threshold = max(FLOOR, math.ceil(p99 * 100) / 100)
    print(f"{crop}: {len(records)} images; random same-class pairs median {np.median(sims):.3f}, "
          f"p99 {p99:.3f} -> threshold {threshold:.2f}")


if __name__ == "__main__":
    main()
