"""Run every cleaner, raw datasets/ -> backend/scripts/seed_data/.

Usage (from repo root, backend venv active):
    python -m ml.prep.run_all

Re-runnable and deterministic: given the same raw files it writes byte-identical
artifacts, which is what lets `seed_reference_data.py` stay idempotent.
"""

from __future__ import annotations

from ml.prep import (
    clean_crop_diseases,
    clean_crop_yield,
    clean_fertilizer_targets,
    clean_market_prices,
    clean_state_climate,
    clean_state_soil,
)

CLEANERS = (
    clean_state_soil,
    clean_state_climate,
    clean_fertilizer_targets,
    clean_crop_yield,
    clean_market_prices,
    clean_crop_diseases,
)


def main() -> None:
    for module in CLEANERS:
        module.main()
        print()
    print("all cleaners finished")


if __name__ == "__main__":
    main()
