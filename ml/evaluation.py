"""Splitting and reporting shared by every training script.

## Why a three-way split, everywhere

The inherited scripts used a single `train_test_split` and then reported the
score on that same held-out fold *after* using it to judge feature importance
and settle hyperparameters. Once a fold has informed a decision it is no longer
held out, and the number it produces is no longer a generalisation estimate.
`train_yield_model.py` did exactly this and reported R-squared = 0.9501.

So: fit on train, make every decision against validation, and touch test once
at the very end to produce the number that goes in `MODEL_RESULTS.md`.

## Why a baseline is mandatory

Several of these datasets are synthetic and highly separable — one has exactly
100 rows per class across 31 classes. A high accuracy on such data says more
about the data than the model. `MODEL_BARS.md` therefore bars every model
against the trivial alternative, and this module computes those baselines so
the comparison is done the same way each time rather than eyeballed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np
from sklearn.model_selection import train_test_split

RANDOM_STATE = 42


@dataclass
class Split:
    """A train/validation/test partition, with the sizes recorded for the report."""

    X_train: object
    X_val: object
    X_test: object
    y_train: object
    y_val: object
    y_test: object
    strategy: str

    def sizes(self) -> str:
        return (
            f"train={len(self.y_train)} val={len(self.y_val)} test={len(self.y_test)}"
        )


def three_way_split(
    X,
    y,
    *,
    test_size: float = 0.2,
    val_size: float = 0.2,
    stratify: bool = True,
    random_state: int = RANDOM_STATE,
) -> Split:
    """Split into train/val/test, stratifying when every class can support it.

    Stratification is silently dropped for classes too small to appear in all
    three folds — `merged_crop_dataset.csv` has a class with 7 rows, and
    sklearn raises rather than splitting it. Dropping stratification is the
    lesser evil versus excluding those classes entirely, but it is reported so
    the consequence is visible in the results rather than discovered later.
    """
    strategy = "stratified 3-way (60/20/20)"
    stratify_all = y if stratify else None

    if stratify:
        _, counts = np.unique(np.asarray(y), return_counts=True)
        smallest = int(counts.min())
        # Needs at least one row per fold; sklearn requires >= 2 per split call.
        if smallest < 3:
            stratify_all = None
            strategy = (
                f"unstratified 3-way (60/20/20) - smallest class has {smallest} "
                f"rows, too few to stratify across three folds"
            )

    X_rest, X_test, y_rest, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=stratify_all
    )

    stratify_rest = y_rest if stratify_all is not None else None
    if stratify_rest is not None:
        _, counts = np.unique(np.asarray(y_rest), return_counts=True)
        if int(counts.min()) < 2:
            stratify_rest = None

    # val_size is a fraction of the whole, so rescale against what is left.
    relative_val = val_size / (1.0 - test_size)
    X_train, X_val, y_train, y_val = train_test_split(
        X_rest,
        y_rest,
        test_size=relative_val,
        random_state=random_state,
        stratify=stratify_rest,
    )

    return Split(X_train, X_val, X_test, y_train, y_val, y_test, strategy)


def majority_class_baseline(y_train, y_test) -> float:
    """Accuracy from always predicting the training set's most common class."""
    values, counts = np.unique(np.asarray(y_train), return_counts=True)
    majority = values[counts.argmax()]
    return float((np.asarray(y_test) == majority).mean())


def macro_f1_of_majority_baseline(y_train, y_test) -> float:
    """Macro-F1 of the majority-class predictor.

    Worth reporting next to its accuracy: on `soil_fertility.csv` the majority
    predictor scores 0.50 accuracy but only about 0.22 macro-F1, which is the
    whole reason that model is barred on macro-F1 rather than accuracy.
    """
    from sklearn.metrics import f1_score

    values, counts = np.unique(np.asarray(y_train), return_counts=True)
    majority = values[counts.argmax()]
    predicted = np.full(len(np.asarray(y_test)), majority)
    return float(f1_score(y_test, predicted, average="macro", zero_division=0))


@dataclass
class BarCheck:
    """One `MODEL_BARS.md` criterion and whether the measured value met it."""

    name: str
    bar: float
    actual: float
    higher_is_better: bool = True

    @property
    def passed(self) -> bool:
        return (
            self.actual >= self.bar if self.higher_is_better else self.actual <= self.bar
        )

    def line(self) -> str:
        mark = "PASS" if self.passed else "FAIL"
        return f"  [{mark}] {self.name}: {self.actual:.4f} (bar {self.bar:.4f})"


@dataclass
class Report:
    """Collected bar checks for one model, printed as a verdict at the end."""

    model: str
    checks: list[BarCheck] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def check(self, name: str, bar: float, actual: float, *, higher_is_better=True):
        self.checks.append(BarCheck(name, bar, actual, higher_is_better))

    def note(self, text: str) -> None:
        self.notes.append(text)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def render(self) -> str:
        lines = [f"\n{'=' * 64}", f"VERDICT: {self.model}", "=" * 64]
        lines.extend(c.line() for c in self.checks)
        if self.notes:
            lines.append("  notes:")
            lines.extend(f"    - {n}" for n in self.notes)
        lines.append(
            f"  => {'CLEARS ITS BAR' if self.passed else 'MISSES ITS BAR - DOES NOT SHIP'}"
        )
        return "\n".join(lines)


def per_class_recall(y_true, y_pred, labels: Sequence) -> dict:
    """Recall for each named label, for bars that target specific classes."""
    from sklearn.metrics import recall_score

    scores = recall_score(
        y_true, y_pred, labels=list(labels), average=None, zero_division=0
    )
    return {str(label): float(score) for label, score in zip(labels, scores)}
