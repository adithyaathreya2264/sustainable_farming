"""datasets/market datasets(1)/csv -> market_prices.json

Mandi (wholesale market) prices. Two things about this source constrain how
it may be used:

- **It is a single day.** Every row carries arrival_date 04/03/2019 — this is
  one snapshot, not a series, so no trend, average or "price is rising" claim
  can be drawn from it. It answers "what did this commodity fetch at these
  markets on that date", nothing more.
- **It is years stale.** Consumers must show the snapshot date next to any
  price. The service seam is shaped so a live Agmarknet feed can replace the
  seeded rows later without the callers changing.

Prices are rupees per quintal (100 kg) in the Agmarknet convention this dump
follows. Unlike the yield dataset that unit *is* documented upstream and
consistent, so it is recorded explicitly rather than left null.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime

from ml.prep.common import (
    DATASETS_DIR,
    crop_key,
    normalize_district,
    normalize_state,
    read_csv,
    write_seed_json,
)

SOURCE = DATASETS_DIR / "market datasets(1)" / "csv"

PRICE_UNIT = "INR per quintal"


def _parse_date(raw: str) -> date:
    return datetime.strptime(raw.strip(), "%d/%m/%Y").date()


def build() -> tuple[list[dict], dict]:
    # (state, district, market, commodity, variety) -> row. The dump has one
    # arrival date, so a repeat of this tuple is a duplicate line rather than
    # a second day's quote; last one wins and the count is reported.
    seen: dict[tuple[str, str, str, str, str], dict] = {}
    duplicates = 0
    dropped_state: set[str] = set()
    dropped_price = 0
    dates: set[date] = set()

    for raw in read_csv(SOURCE):
        state = normalize_state(raw["state"])
        if state is None:
            dropped_state.add(raw["state"])
            continue

        try:
            minimum = int(float(raw["min_price"]))
            maximum = int(float(raw["max_price"]))
            modal = int(float(raw["modal_price"]))
        except (TypeError, ValueError):
            dropped_price += 1
            continue
        if modal <= 0:
            dropped_price += 1
            continue

        arrival = _parse_date(raw["arrival_date"])
        dates.add(arrival)

        commodity = raw["commodity"].strip()
        variety = raw["variety"].strip()
        district_raw = raw["district"].strip()
        identity = (
            state,
            district_raw,
            raw["market"].strip(),
            commodity,
            variety,
        )
        if identity in seen:
            duplicates += 1

        seen[identity] = {
            "state": state,
            # Raw name kept for display (it is what the mandi is called
            # locally); the canonical name is what a district filter joins on.
            "district": district_raw,
            "district_canonical": normalize_district(state, district_raw),
            "market": raw["market"].strip(),
            "commodity": commodity,
            # Slugged so a planting's crop can be matched to a mandi listing
            # without the caller knowing either vocabulary.
            "commodity_key": crop_key(commodity),
            "variety": variety,
            "min_price": minimum,
            "max_price": maximum,
            "modal_price": modal,
            "arrival_date": arrival.isoformat(),
        }

    rows = sorted(
        seen.values(),
        key=lambda row: (row["state"], row["district"], row["market"], row["commodity"]),
    )

    by_state: dict[str, int] = defaultdict(int)
    for row in rows:
        by_state[row["state"]] += 1

    meta = {
        "price_unit": PRICE_UNIT,
        "source": "datasets/market datasets(1)/csv",
        "snapshot_dates": sorted(day.isoformat() for day in dates),
        "is_live": False,
        "note": (
            "Static snapshot from the dates listed above, not a live feed. "
            "Always display the snapshot date alongside any price. No trend "
            "or average may be derived: the dump covers a single day."
        ),
    }

    placed = sum(1 for row in rows if row["district_canonical"])
    unplaced = sorted(
        {(row["state"], row["district"]) for row in rows if not row["district_canonical"]}
    )

    print(
        f"  {len(rows)} unique listings across {len(by_state)} states "
        f"({duplicates} duplicate identity rows collapsed, "
        f"{dropped_price} unusable prices dropped)"
    )
    print(
        f"  {placed}/{len(rows)} listings placed in a locations.json district "
        f"({len(unplaced)} district name(s) unresolved, still reachable by state)"
    )
    if unplaced:
        print(f"  unresolved districts: {unplaced}")
    if dropped_state:
        print(f"  NOTE: unresolved states dropped: {sorted(dropped_state)}")
    print(f"  snapshot dates: {meta['snapshot_dates']}")
    return rows, meta


def main() -> None:
    print(f"cleaning market prices")
    rows, meta = build()
    write_seed_json("market_prices.json", rows, describe="listings")
    write_seed_json("market_prices_meta.json", meta, describe="metadata keys")


if __name__ == "__main__":
    main()
