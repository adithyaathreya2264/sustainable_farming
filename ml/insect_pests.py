"""What each insect-detector class means for the app.

Same role as `ml/leaf_conditions.py`: the dataset's class names ("white backed
plant hopper") are not fit to be API values, and a bare name does not say which
of the app's crops the pest attacks.

## Host crops are recorded, not inferred, and are unverified

`hosts` lists the app's seeded crops each pest is a known pest of, written from
the pests' standard descriptions. It is conservative: a crop is listed only
where the pest is a recognised pest of it, not wherever it has ever been found.
Every result carries `hosts_verified: False`; nothing here has been reviewed by
an entomologist.

The serving layer uses `hosts` to flag, not to filter. A detection of a pest
that does not attack the farmer's crop is more likely a misidentification than
a discovery, and the farmer should see that it was flagged, not have it
silently removed.

## Rule links are same-pest only

`related_rules` links a class to an agronomic rule in
`backend/scripts/reference-data.json` only when the rule is about the same
pest. Yellow rice borer (*Scirpophaga incertulas*) is the stem borer behind
`RICE_STEM_BORER_SCOUT`. The dataset's generic "army worm" is **not** linked to
`MAIZE_FAW_ETL`: that rule concerns fall armyworm specifically, and the class
does not say which armyworm it shows.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class InsectPest:
    key: str
    display_name: str
    hosts: tuple[str, ...]
    related_rules: tuple[str, ...] = field(default_factory=tuple)

    @property
    def app_relevant(self) -> bool:
        return bool(self.hosts)


# Keyed by the dataset's class name exactly as it appears in data.yaml, in the
# same order as the class indices.
INSECT_PESTS: dict[str, InsectPest] = {
    "army worm": InsectPest("army_worm", "Armyworm", ("maize", "rice")),
    "legume blister beetle": InsectPest("legume_blister_beetle", "Legume Blister Beetle", ()),
    "red spider": InsectPest("red_spider_mite", "Red Spider Mite", ("cotton",)),
    "rice gall midge": InsectPest("rice_gall_midge", "Rice Gall Midge", ("rice",)),
    "rice leaf roller": InsectPest("rice_leaf_roller", "Rice Leaf Roller", ("rice",)),
    "rice leafhopper": InsectPest("rice_leafhopper", "Rice Leafhopper", ("rice",)),
    "rice water weevil": InsectPest("rice_water_weevil", "Rice Water Weevil", ("rice",)),
    # Hosts added 2026-09-26, when wheat became an app crop (MODEL_RESULTS.md section 11).
    "wheat phloeothrips": InsectPest("wheat_thrips", "Wheat Thrips (Phloeothrips)", ("wheat",)),
    "white backed plant hopper": InsectPest("white_backed_planthopper", "White-backed Planthopper", ("rice",)),
    "yellow rice borer": InsectPest("yellow_stem_borer", "Yellow Stem Borer", ("rice",), ("RICE_STEM_BORER_SCOUT",)),
}

APP_RELEVANT_CLASSES = [name for name, pest in INSECT_PESTS.items() if pest.app_relevant]


def pest_for(class_name: str) -> InsectPest:
    try:
        return INSECT_PESTS[class_name]
    except KeyError as exc:
        raise KeyError(
            f"No registry entry for insect class {class_name!r}. Add it to "
            f"ml/insect_pests.py deliberately rather than serving an unlabelled class."
        ) from exc
