"""Models that cleared their bar but are not served until a named check is done.

A held model is unreachable in two places: `/v1/capabilities` reports it as
unavailable (so the app never offers it), and its sidecar route raises
`ModelOnHold` (409 `model_on_hold`), so a direct call cannot bypass the UI.

To enable a held model, do the check, record it in ml/MODEL_RESULTS.md, and
delete its entry here. Nothing else changes.
"""

from __future__ import annotations

# capability name -> (reason code, where the reason is documented)
HELD: dict[str, tuple[str, str]] = {
    "wheat_kernels": (
        "awaiting_lighting_check",
        "ml/MODEL_RESULTS.md section 28: average photo colour alone scores 0.94, "
        "so the pass may reflect capture lighting; check on grain photos taken "
        "under different lighting before serving.",
    ),
}


class ModelOnHold(RuntimeError):
    def __init__(self, capability: str):
        reason, detail = HELD[capability]
        super().__init__(detail)
        self.capability = capability
        self.reason = reason


def check(capability: str) -> None:
    """Raise ModelOnHold if `capability` is held."""
    if capability in HELD:
        raise ModelOnHold(capability)
