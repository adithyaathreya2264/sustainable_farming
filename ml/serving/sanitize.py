"""The serving-boundary filter every response passes through.

`ml/README.md` rule 1 (no probability crosses the API) and rule 3 (yield is a
percentile, never a number) are enforced inside each algorithm module, but a
module can still return debug keys meant to stop at this boundary. Stripping
them here, once, means a new endpoint cannot forget to.
"""

from __future__ import annotations

import math
from typing import Any

# A key with one of these names carrying a number is a probability leaking out.
FORBIDDEN_KEYS = frozenset({"probability", "probabilities", "proba", "score", "scores", "similarity"})


class LeakedProbability(AssertionError):
    pass


def public(value: Any) -> Any:
    """Drop `_`-prefixed keys recursively; refuse probability-like keys; make JSON-safe."""
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            key = str(key) if not isinstance(key, str) else key
            if key.startswith("_"):
                continue
            if key.lower() in FORBIDDEN_KEYS:
                raise LeakedProbability(f"response key {key!r} must not cross the serving boundary")
            out[key] = public(item)
        return out
    if isinstance(value, (list, tuple)):
        return [public(item) for item in value]
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    # numpy / pandas scalars -> plain Python
    if hasattr(value, "item") and callable(value.item) and not isinstance(value, (str, bytes)):
        try:
            return public(value.item())
        except (ValueError, TypeError):
            return str(value)
    return value
