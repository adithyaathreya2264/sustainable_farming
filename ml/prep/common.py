"""Shared helpers for the `ml/prep` cleaners.

Deliberately stdlib-only (`csv`, `json`, `statistics`). The prep layer runs in
the existing backend venv with no extra dependencies — pandas buys nothing for
files this size and would drag a heavyweight dep into a repo that currently
pins none.

Two vocabularies have to be reconciled before any dataset can be seeded:

- **States.** `backend/scripts/seed_data/locations.json` is the canonical
  spelling (36 entries). The raw datasets drift from it in four places, all in
  the market CSV — see `_STATE_ALIASES`.
- **Crops.** Four datasets use four different naming styles for the same
  plants (`Cotton(lint)` / `cotton`, `Ragi( naachnnii)` / `Ragi` / `ragi`,
  `Jowar(Sorghum)` / `Jowar` / `sorghum`). `crop_key()` slugs them and
  `_CROP_ALIASES` folds the known variants together. Crops with no alias entry
  keep their own slug rather than being force-matched — per the plan, features
  key off the crop *name*, not `Crop.id`, so an unseeded crop still works.
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Iterator

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASETS_DIR = REPO_ROOT / "datasets"
SEED_DATA_DIR = REPO_ROOT / "backend" / "scripts" / "seed_data"
LOCATIONS_JSON = SEED_DATA_DIR / "locations.json"


# --------------------------------------------------------------------------
# States
# --------------------------------------------------------------------------

# Raw spelling -> canonical spelling in locations.json. Every entry here was
# found by diffing the datasets' distinct states against locations.json; all
# four come from `market datasets(1)/csv`.
_STATE_ALIASES = {
    "andaman and nicobar": "Andaman and Nicobar Islands",
    "chattisgarh": "Chhattisgarh",
    "pondicherry": "Puducherry",
    "uttrakhand": "Uttarakhand",
    # Common variants not currently present, but cheap to guard against so a
    # refreshed dump doesn't silently drop rows.
    "orissa": "Odisha",
    "uttaranchal": "Uttarakhand",
    "nct of delhi": "Delhi",
}


# Parsed once: normalize_district() consults it per row, and re-reading the
# file for each of the market dump's 2,224 listings is pure waste.
_LOCATIONS: list[dict] = json.loads(LOCATIONS_JSON.read_text(encoding="utf-8"))

# lowercased canonical state name -> canonical spelling
_CANONICAL_STATES = {entry["state"].lower(): entry["state"] for entry in _LOCATIONS}

_PARENTHETICAL = re.compile(r"\([^)]*\)")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_state(raw: str | None) -> str | None:
    """Canonical state spelling, or None if it doesn't resolve.

    Callers must treat None as "drop this row" and count it — a cleaner that
    silently discards a state is how a whole region goes missing from a
    feature without anyone noticing.
    """
    if not raw:
        return None
    key = " ".join(raw.strip().split()).lower()
    if key in _CANONICAL_STATES:
        return _CANONICAL_STATES[key]
    alias = _STATE_ALIASES.get(key)
    if alias:
        return alias
    return None


def canonical_districts(state: str) -> set[str]:
    for entry in _LOCATIONS:
        if entry["state"] == state:
            return set(entry["districts"])
    return set()


# --------------------------------------------------------------------------
# Districts
# --------------------------------------------------------------------------

# The market dump uses pre-rename and pre-split district names throughout, so
# 30% of its listings would be unreachable by a district filter keyed off
# locations.json. Three passes reconcile them: transliteration variants
# (below), then an exact match on a punctuation-stripped slug, then this
# explicit table of renames and respellings.
_TRANSLITERATIONS = (
    ("bengaluru", "bangalore"),
    ("bangaluru", "bangalore"),
    ("mysuru", "mysore"),
    ("tumakuru", "tumkur"),
    ("belagavi", "belgaum"),
    ("kalaburagi", "gulbarga"),
    ("shivamogga", "shimoga"),
    ("ballari", "bellary"),
    ("vijayapura", "bijapur"),
    ("chikkamagaluru", "chikmagalur"),
    ("gurugram", "gurgaon"),
    ("solapur", "sholapur"),
    ("ahmadnagar", "ahmednagar"),
    ("thiruvananthapuram", "trivandrum"),
)

# (state, raw district) -> canonical district in locations.json. Every entry
# is a documented rename or a respelling, not a guess.
_DISTRICT_ALIASES = {
    ("Andhra Pradesh", "chittor"): "Chittoor",
    ("Gujarat", "kachchh"): "Kutch",
    ("Haryana", "mewat"): "Nuh",  # renamed 2016
    ("Jammu and Kashmir", "badgam"): "Budgam",
    ("Kerala", "kasargod"): "Kasaragod",
    ("Kerala", "thirssur"): "Thrissur",
    ("Madhya Pradesh", "anupur"): "Anuppur",
    ("Madhya Pradesh", "badwani"): "Barwani",
    ("Odisha", "nowarangpur"): "Nabarangpur",
    ("Odisha", "sundergarh"): "Sundargarh",
    ("Punjab", "bhatinda"): "Bathinda",
    ("Punjab", "ropar"): "Rupnagar",
    ("Punjab", "tarntaran"): "Tarn Taran",
    ("Uttarakhand", "udhamsinghnagar"): "Udham Singh Nagar",
    ("Tamil Nadu", "kancheepuram"): "Kanchipuram",
    ("Tamil Nadu", "nagercoil"): "Kanyakumari",
    ("Tamil Nadu", "thiruvannamalai"): "Tiruvannamalai",
    ("Tamil Nadu", "villupuram"): "Viluppuram",
    ("Tripura", "south district"): "South Tripura",
    ("Uttar Pradesh", "allahabad"): "Prayagraj",  # renamed 2018
    ("Uttar Pradesh", "bulandshahar"): "Bulandshahr",
    ("Uttar Pradesh", "chitrakut"): "Chitrakoot",
    ("Uttar Pradesh", "farukhabad"): "Farrukhabad",
    ("Uttar Pradesh", "gautam budh nagar"): "Gautam Buddha Nagar",
    ("Uttar Pradesh", "kannuj"): "Kannauj",
    ("Uttar Pradesh", "khiri"): "Lakhimpur Kheri",
    ("Uttar Pradesh", "muradabad"): "Moradabad",
    ("Uttar Pradesh", "raebarelli"): "Raebareli",
    ("Uttarakhand", "dehradoon"): "Dehradun",
    # Bardhaman split into Purba/Paschim in 2017. Bardhaman town — the market
    # this row refers to — falls in Purba, so that is the mapping; the raw
    # name is kept on the row so the choice stays visible.
    ("West Bengal", "burdwan"): "Purba Bardhaman",
    ("West Bengal", "medinipur"): "Paschim Medinipur",  # raw is "Medinipur(W)"
    ("West Bengal", "puruliya"): "Purulia",
    ("West Bengal", "sounth 24 parganas"): "South 24 Parganas",
    # Deliberately absent, and reported as unresolved on every run:
    #   ("Karnataka", "bangalore")  — its one market, Ramanagara, is itself a
    #     district now (split from Bangalore Rural in 2007), so "Bangalore"
    #     maps to neither Bengaluru Urban nor Rural.
    #   ("Uttar Pradesh", "kanpur") — its one market, Rura, cannot be placed
    #     between Kanpur Dehat and Kanpur Nagar from this data alone.
    # Both stay reachable by state; guessing a district would put a real
    # market in the wrong place for the sake of a filter.
}


def _district_slug(value: str) -> str:
    text = _PARENTHETICAL.sub(" ", value).lower()
    text = " ".join(_NON_ALNUM.sub(" ", text).split())
    for canonical, legacy in _TRANSLITERATIONS:
        text = text.replace(canonical, legacy)
    return text


@lru_cache(maxsize=None)
def _district_lookup(state: str) -> dict[str, str]:
    return {_district_slug(name): name for name in canonical_districts(state)}


def normalize_district(state: str, raw: str | None) -> str | None:
    """Canonical district for `state`, or None if it doesn't resolve.

    None is not a failure the caller should drop the row over — a market whose
    district can't be placed is still reachable by state, which is why
    `clean_market_prices` keeps the raw name alongside.
    """
    if not raw or not state:
        return None

    lookup = _district_lookup(state)
    slug = _district_slug(raw)
    if not slug:
        return None

    if slug in lookup:
        return lookup[slug]

    alias = _DISTRICT_ALIASES.get((state, slug))
    if alias:
        return alias

    # A one-sided prefix match catches "Kanpur"/"Kanpur Nagar"-style
    # abbreviations, but only when exactly one canonical district matches —
    # an ambiguous prefix would silently pick the wrong district.
    matches = [
        name
        for key, name in lookup.items()
        if key.startswith(slug) or slug.startswith(key)
    ]
    if len(matches) == 1:
        return matches[0]

    return None


# --------------------------------------------------------------------------
# Crops
# --------------------------------------------------------------------------

# Slug -> canonical slug. Only crops that actually appear under more than one
# name across the datasets, plus the five seeded `Crop` rows, are listed. This
# is not an attempt to unify all ~200 names.
_CROP_ALIASES = {
    # the five seeded crops
    "cotton lint": "cotton",
    "ragi naachnnii": "ragi",
    "ragi finger millet": "ragi",
    "finger millet": "ragi",
    # widely duplicated staples
    "jowar sorghum": "sorghum",
    "jowar": "sorghum",
    "bajra": "pearl millet",
    "barley jav": "barley",
    "chickpeas channa": "chickpea",
    "chickpeas": "chickpea",
    "gram": "chickpea",
    "black gram": "blackgram",
    "urad": "blackgram",
    "mung beans": "mungbean",
    "mung bean": "mungbean",
    "moong green gram": "mungbean",
    "green gram": "mungbean",
    "moth bean matki": "mothbeans",
    "moth bean": "mothbeans",
    "moth": "mothbeans",
    "horse gram kulthi": "horsegram",
    "horse gram": "horsegram",
    "horse-gram": "horsegram",
    "lentils masoor dal": "lentil",
    "masoor": "lentil",
    "pigeon peas toor dal": "pigeonpeas",
    "pigeon peas": "pigeonpeas",
    "arhar tur": "pigeonpeas",
    "kidney beans": "kidneybeans",
    "rajma": "kidneybeans",
    "soyabean": "soybean",
    "ground nut": "groundnut",
    "groundnuts": "groundnut",
    "rapeseed mohri": "rapeseed",
    # NOT merged into "rapeseed": mustard is a distinct oilseed with its own
    # nutrient target (N 100 vs 50 in Fertilizer.csv). crop_yield.csv's
    # "Rapeseed &Mustard" is the government's *combined* reporting category
    # and stays its own key too, rather than being folded into either crop.
    "mustard seeds": "mustard",
    "lady finger": "okra",
    "bhindi ladies finger": "okra",
    "bhindi": "okra",
    "water melon": "watermelon",
    "musk melon": "muskmelon",
    "tapioca suran": "tapioca",
    "cashewnuts": "cashewnut",
    "black pepper": "blackpepper",
    # en-dash is a separator, not a bracket, so "moringa" survives the slug
    "drumstick moringa": "drumstick",
    # Leaf and seed coriander are separate crops with different targets
    # (N 10 vs 90), so they are kept apart rather than collapsed to
    # "coriander". The bare name from crop_yield.csv stays "coriander".
    "coriander seeds": "coriander seed",
    "coriander leaves": "coriander leaf",
    "dry chillies": "chilli",
    "chili": "chilli",
    "sesame seed": "sesamum",
    "sesame": "sesamum",
}

# Crops seeded as real `Crop` rows by backend/scripts/seed_reference_data.py.
# Slug -> the exact seeded `Crop.name`, so a cleaner can mark which of its
# rows will join to a real crop_id and which stay free-text.
SEEDED_CROPS = {
    "rice": "Rice",
    "ragi": "Ragi (Finger Millet)",
    "maize": "Maize",
    "cotton": "Cotton",
    "sugarcane": "Sugarcane",
}

def _slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    # en/em dashes read as separators, not as part of the name
    text = text.replace("–", " ").replace("—", " ")
    return " ".join(_NON_ALNUM.sub(" ", text.lower()).split())


def crop_key(raw: str | None) -> str | None:
    """Slug a crop name so the four datasets' spellings collapse together.

    `Cotton(lint)` -> `cotton`, `Ragi( naachnnii)` -> `ragi`,
    `Moong(Green Gram)` -> `mungbean`, `sweet_potato` -> `sweet potato`.

    The alias table is consulted twice: once against the slug that *keeps*
    the parenthetical as extra words, and once against the slug with the
    parenthetical removed. Many aliases only exist because of what is inside
    the brackets (`Moong(Green Gram)`, `Jowar(Sorghum)`), so stripping first
    and looking up second would silently miss them.
    """
    if not raw:
        return None
    with_parens = _slug(raw)
    without_parens = _slug(_PARENTHETICAL.sub(" ", raw))
    if not without_parens:
        # e.g. a name that is nothing but a bracketed note
        without_parens = with_parens
    if not without_parens:
        return None
    for candidate in (with_parens, without_parens):
        if candidate in _CROP_ALIASES:
            return _CROP_ALIASES[candidate]
    return without_parens


def crop_display_name(key: str) -> str:
    """Title-cased display form of a slug, preferring the seeded crop's own
    name so UI labels match the catalog the farmer already sees."""
    seeded = SEEDED_CROPS.get(key)
    if seeded:
        return seeded
    return key.title()


# --------------------------------------------------------------------------
# Seasons
# --------------------------------------------------------------------------

# crop_yield.csv pads season values (`"Kharif     "`). The disease dataset adds
# Monsoon / Post-Monsoon / Spring, which have no crop_yield equivalent — they
# are kept as-is rather than force-mapped onto Kharif/Rabi.
_KNOWN_SEASONS = {
    "kharif": "Kharif",
    "rabi": "Rabi",
    "summer": "Summer",
    "winter": "Winter",
    "autumn": "Autumn",
    "spring": "Spring",
    "monsoon": "Monsoon",
    "post-monsoon": "Post-Monsoon",
    "post monsoon": "Post-Monsoon",
    "whole year": "Whole Year",
}


def normalize_season(raw: str | None) -> str | None:
    if not raw:
        return None
    key = " ".join(raw.strip().split()).lower()
    return _KNOWN_SEASONS.get(key)


# --------------------------------------------------------------------------
# IO
# --------------------------------------------------------------------------


def read_csv(path: Path, encoding: str = "utf-8-sig") -> Iterator[dict[str, str]]:
    with open(path, newline="", encoding=encoding) as handle:
        yield from csv.DictReader(handle)


def write_seed_json(filename: str, payload: object, *, describe: str) -> Path:
    """Write a cleaned artifact into backend/scripts/seed_data/ and report.

    Artifacts are pretty-printed and versioned in the repo: they are the
    source of truth the seed script reads, so a reviewer can diff them.
    """
    SEED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = SEED_DATA_DIR / filename
    out.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    count = len(payload) if isinstance(payload, (list, dict)) else "?"
    print(f"  wrote {out.relative_to(REPO_ROOT)}  ({count} {describe})")
    return out


def percentile(sorted_values: list[float], fraction: float) -> float:
    """Nearest-rank percentile on an already-sorted list.

    Nearest-rank (not interpolated) so every reported figure is a value that
    actually occurs in the source data — these are shown to farmers as
    "typical", and an interpolated number no real district achieved would be
    a small fabrication.
    """
    if not sorted_values:
        raise ValueError("percentile of empty sequence")
    index = max(0, min(len(sorted_values) - 1, round(fraction * (len(sorted_values) - 1))))
    return sorted_values[index]
