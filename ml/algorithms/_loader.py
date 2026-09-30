"""Lazy, cached artifact loading, with a ship/hold gate.

## Why lazy

Every inherited `algorithms/*.py` called `joblib.load` at module scope. That
made importing a module an expensive, failing operation: `import
disease_prediction` deserialised a 214 MB pickle before the caller had decided
whether to use it, and any module whose artifact was missing raised at import
time, taking down anything that merely imported it transitively.

Artifacts load on first use and are cached thereafter. `market_price_prediction`
in the inherited tree already did this correctly; this generalises its pattern.

## Why there is a gate

`MODEL_BARS.md` says a model that misses its bar does not ship — "not shipping
with a warning label, not shipping behind a flag". A rule enforced only by
documentation is a rule that gets forgotten during integration, when someone
wires up an artifact that happens to be sitting in `ml/artifacts/` because the
training script writes one regardless of outcome.

So the check is mechanical. Training records `passed_bar` in every artifact,
and `load_model` refuses to return one that failed, naming the model and
pointing at the results file. To serve a failed model someone has to delete
this code, which is a conversation rather than an oversight.
"""

from __future__ import annotations

import threading
from pathlib import Path

import joblib

_cache: dict[Path, object] = {}
_lock = threading.Lock()


class ModelDidNotShip(RuntimeError):
    """Raised when code tries to serve an artifact that missed its bar."""


def load_artifact(path: Path, *, enforce_bar: bool = True) -> dict:
    """Load and cache an artifact bundle, refusing ones that failed their bar."""
    with _lock:
        bundle = _cache.get(path)
        if bundle is None:
            if not path.exists():
                raise FileNotFoundError(
                    f"Model artifact not found: {path.name}\n"
                    f"  Artifacts are build outputs and are not committed. Run the "
                    f"matching script under ml/training/ to produce it."
                )
            bundle = joblib.load(path)
            _cache[path] = bundle

    if enforce_bar and isinstance(bundle, dict) and bundle.get("passed_bar") is False:
        raise ModelDidNotShip(
            f"{path.name} did not clear its acceptance bar and must not be served.\n"
            f"  See ml/MODEL_RESULTS.md for the measured values and the reason.\n"
            f"  Serving it anyway requires changing ml/MODEL_BARS.md first."
        )
    return bundle


def clear_cache() -> None:
    """Drop cached artifacts. For tests and for reloading after a retrain."""
    with _lock:
        _cache.clear()
