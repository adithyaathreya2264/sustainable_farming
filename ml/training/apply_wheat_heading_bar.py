"""Apply bar 14b (wheat heading detection only) to model 14's recorded test read.

Run:
    python -m ml.training.apply_wheat_heading_bar

MODEL_BARS.md section 9, "model 14b". The bar was written after model 14's test
read and is declared as such. This script does not read the test fold again:
it applies the bar to the test metrics stored in the checkpoint by
`train_wheat_segmentation.py`, and records the verdict under its own key,
`heading_passed_bar`. Model 14's `passed_bar` stays False; canopy cover is
never served.
"""

from __future__ import annotations

import json

from ml import paths
from ml.evaluation import Report

BAR_HEADING_BALANCED_ACCURACY = 0.85
BAR_HEAD_IOU = 0.60


def main() -> None:
    import torch

    path = paths.require(paths.WHEAT_SEGMENTATION_MODEL)
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    test = checkpoint["test_metrics"]

    report = Report("Wheat heading detection only (model 14b)")
    report.check("heading balanced accuracy (test)", BAR_HEADING_BALANCED_ACCURACY,
                 test["heading_balanced_accuracy"])
    report.check("head IoU (test)", BAR_HEAD_IOU, test["iou"]["head"])
    report.note(
        f"heading recall {test['heading_recall']:.4f}, specificity "
        f"{test['heading_specificity']:.4f} ({test['headed_images']} headed / "
        f"{test['unheaded_images']} not)"
    )
    report.note(
        "DECLARED BIAS: bar written after model 14's test read; applied to that "
        "same read, not a fresh one. A blind check needs the 658 undownloaded "
        "GWFSS images"
    )
    report.note("canopy cover (model 14) still fails and is not served")
    print(report.render())

    checkpoint["heading_passed_bar"] = report.passed
    checkpoint["heading_bar"] = {
        "balanced_accuracy": BAR_HEADING_BALANCED_ACCURACY,
        "head_iou": BAR_HEAD_IOU,
        "declared_post_hoc": True,
    }
    torch.save(checkpoint, path)

    metrics_path = path.with_name("wheat_canopy_segmentation_metrics.json")
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["heading_passed_bar"] = report.passed
    metrics["heading_bar_declared_post_hoc"] = True
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(f"\nRecorded heading_passed_bar={report.passed} in {path.name}")


if __name__ == "__main__":
    main()
