"""What each leaf-photo class means, in terms the app can act on.

The datasets name their classes by folder — `BrownRust`, `smut`,
`Bacterialblight`. Those strings are not fit to be API values: inconsistent casing and
spacing, and no indication of what kind of problem each one is. This registry
gives every class three things:

- a **stable key** (`brown_rust`), so the API and the app's translation files
  never depend on how a dataset author capitalised a folder;
- a **category**, because the right response differs completely by kind of
  problem. Herbicide injury and dried leaves are not diseases, and
  recommending a fungicide for them wastes money and helps nothing;
- a **Q&A corpus link** where one exists, so a photo result can lead directly
  to the documented symptoms and remedies already served by the disease Q&A
  model (`ml/algorithms/disease_info_retrieval.py`).

## The Q&A links are same-disease matches only

A class is linked only when it and the corpus entry are unambiguously the same
disease. Most are identical names; a few are standard synonyms (rice
"Bacterialblight" is "Bacterial Leaf Blight"). Nothing is linked on
resemblance. Sugarcane *Sett Rot* and the corpus's *Red Rot* are
different fungal diseases; *Viral Disease* could be any of several sugarcane
viruses; neither is linked. A wrong link would show a farmer confident,
documented remedies for a disease they do not have.

## The categories are not agronomist-reviewed

They were written from the class names and standard descriptions of these
conditions, and every result carries `category_verified: False`. This matches
the rest of the project: `agronomic-rules-draft.md` is still awaiting KVK/ICAR
review, and so is this.

Uncertain cases are marked `unclassified` rather than guessed.
"""

from __future__ import annotations

from dataclasses import dataclass

HEALTHY = "healthy"
DISEASE = "disease"
PEST_DAMAGE = "pest_damage"
ABIOTIC = "abiotic"
UNCLASSIFIED = "unclassified"
GRADE = "grade"  # produce quality grade (ripeness, damage), not a plant problem


@dataclass(frozen=True)
class LeafCondition:
    key: str
    display_name: str
    category: str
    # Exact disease_name_en in the Q&A corpus, or None when there is no
    # unambiguous match.
    qa_disease: str | None = None


# Keyed by the dataset's own folder name, exactly as it appears on disk.
LEAF_CONDITIONS: dict[str, dict[str, LeafCondition]] = {
    "sugarcane": {
        "Banded Chlorosis": LeafCondition("banded_chlorosis", "Banded Chlorosis", ABIOTIC),
        "Brown Spot": LeafCondition("brown_spot", "Brown Spot", DISEASE),
        "BrownRust": LeafCondition("brown_rust", "Brown Rust", DISEASE),
        "Grassy shoot": LeafCondition("grassy_shoot", "Grassy Shoot", DISEASE, "Grassy Shoot Disease"),
        "Pokkah Boeng": LeafCondition("pokkah_boeng", "Pokkah Boeng", DISEASE, "Pokkah Boeng"),
        "Sett Rot": LeafCondition("sett_rot", "Sett Rot", DISEASE),
        "smut": LeafCondition("smut", "Smut", DISEASE, "Smut"),
        "Viral Disease": LeafCondition("viral_disease", "Viral Disease (unspecified)", DISEASE),
        "Yellow Leaf": LeafCondition("yellow_leaf", "Yellow Leaf", DISEASE, "Yellow Leaf Disease"),
        "Dried Leaves": LeafCondition("dried_leaves", "Dried Leaves", ABIOTIC),
        "Healthy Leaves": LeafCondition("healthy", "Healthy", HEALTHY),
    },
    # No healthy class exists in this dataset - see MODEL_BARS.md section 9.
    "rice": {
        "Bacterialblight": LeafCondition("bacterial_leaf_blight", "Bacterial Leaf Blight", DISEASE, "Bacterial Leaf Blight"),
        "Blast": LeafCondition("blast", "Rice Blast", DISEASE, "Rice Blast"),
        "Brownspot": LeafCondition("brown_spot", "Brown Spot", DISEASE, "Brown Spot"),
        "Tungro": LeafCondition("tungro", "Rice Tungro", DISEASE, "Rice Tungro"),
    },
    # Pearl millet (bajra), keyed as ml/prep/common.py's crop_key returns it.
    # Not a seeded app crop, and not ragi. Conditional like rice: the dataset's
    # Healthy folder is excluded (EXCLUDED_FOLDERS), so there is no healthy
    # class. The Q&A corpus has no millet entries, so nothing is linked.
    "pearl millet": {
        "blast": LeafCondition("blast", "Pearl Millet Blast", DISEASE),
        "rust": LeafCondition("rust", "Pearl Millet Rust", DISEASE),
    },
    # Models 20-27 (MODEL_BARS.md section 9, 2026-09-25). None of these crops is
    # a seeded app crop. Q&A links only where the corpus has the same disease.
    "coffee": {
        "Health leaves": LeafCondition("healthy", "Healthy", HEALTHY),
        "leaf rust": LeafCondition("coffee_leaf_rust", "Coffee Leaf Rust", DISEASE),
        "phoma": LeafCondition("phoma_leaf_spot", "Phoma Leaf Spot", DISEASE),
    },
    "tea": {
        "01-Fresh Leaf-Tea": LeafCondition("healthy", "Healthy (fresh leaf)", HEALTHY),
        "02-Helopeltus-Tea-Disease": LeafCondition("helopeltis_damage", "Tea Mosquito Bug (Helopeltis) Damage", PEST_DAMAGE),
        "03-Red Spider-Tea-Disease": LeafCondition("red_spider_mite_damage", "Red Spider Mite Damage", PEST_DAMAGE),
    },
    "cauliflower": {  # leaves
        "Alternaria Leaf Spot": LeafCondition("alternaria_leaf_spot", "Alternaria Leaf Spot", DISEASE),
        "Downy Mildew": LeafCondition("downy_mildew", "Downy Mildew", DISEASE),
        "Healthy": LeafCondition("healthy", "Healthy", HEALTHY),
    },
    "cauliflower curd": {
        "Alternaria Brassicae": LeafCondition("alternaria_curd", "Alternaria on Curd", DISEASE),
        "Bacterial Soft Rot": LeafCondition("bacterial_soft_rot", "Bacterial Soft Rot", DISEASE),
        "Bacterial Spot": LeafCondition("bacterial_spot", "Bacterial Spot", DISEASE),
        "Black Spot": LeafCondition("black_spot", "Black Spot", DISEASE),
        "Healthy": LeafCondition("healthy", "Healthy", HEALTHY),
        # Purple curd colouring has genetic, cold and sun explanations.
        "Purple Tinges": LeafCondition("purple_tinge", "Purple Tinge", UNCLASSIFIED),
    },
    # Onion labels come from the Healthy/Unhealthy level (LABEL_PATH_LEVEL);
    # the dataset does not name the problem, so "unhealthy" is unclassified.
    "onion": {  # leaves
        "Healthy": LeafCondition("healthy", "Healthy", HEALTHY),
        "Unhealthy": LeafCondition("unhealthy", "Unhealthy (cause not identified)", UNCLASSIFIED),
    },
    "onion bulb": {
        "Healthy": LeafCondition("healthy", "Healthy", HEALTHY),
        "Unhealthy": LeafCondition("unhealthy", "Unhealthy (cause not identified)", UNCLASSIFIED),
    },
    "potato": {  # PlantVillage leaves
        "Potato___Early_blight": LeafCondition("early_blight", "Early Blight", DISEASE, "Early Blight"),
        "Potato___Late_blight": LeafCondition("late_blight", "Late Blight", DISEASE, "Late Blight"),
        "Potato___healthy": LeafCondition("healthy", "Healthy", HEALTHY),
    },
    # Harvested fruit grade, not a disease. No healthy class; served without a
    # symptom gate (not in CONDITIONAL_CROPS).
    "tomato fruit": {
        "Damaged": LeafCondition("damaged", "Damaged", GRADE),
        "Old": LeafCondition("old", "Old / Overripe", GRADE),
        "Ripe": LeafCondition("ripe", "Ripe", GRADE),
        "Unripe": LeafCondition("unripe", "Unripe", GRADE),
    },
}

# Crops whose model has no healthy class and names a disease for any leaf, so
# it may only be asked after a symptom is reported. Explicit rather than
# inferred from a missing healthy class: tomato fruit grading has no healthy
# class either, but a grade is meaningful for every fruit.
CONDITIONAL_CROPS = frozenset({"rice", "pearl millet"})

# Tasks whose class is an ancestor folder, not the folder holding the images:
# the index of the class in the image's path relative to the dataset root.
# Onion: <root>/Healthy/Red Onion/Single/x.jpg -> "Healthy".
LABEL_PATH_LEVEL: dict[str, int] = {"onion": 0, "onion bulb": 0}

# Dataset folders deliberately left out of training, with the reason. A folder
# listed here is skipped; any other unregistered folder still stops the run.
EXCLUDED_FOLDERS: dict[str, dict[str, str]] = {
    "pearl millet": {
        "Healthy": (
            "different source from blast/rust (640px phone photos, Roboflow "
            "export, close framing vs 256px single-leaf camera shots), so a "
            "model could separate classes by source instead of by condition"
        ),
    },
}

SUPPORTED_CROPS = tuple(LEAF_CONDITIONS)


def condition_for(crop: str, folder: str) -> LeafCondition:
    try:
        return LEAF_CONDITIONS[crop][folder]
    except KeyError as exc:
        raise KeyError(
            f"No registry entry for {crop!r} class folder {folder!r}. A dataset "
            f"refresh added or renamed a class; add it to ml/leaf_conditions.py "
            f"deliberately rather than letting it through unlabelled."
        ) from exc


def healthy_folder(crop: str) -> str | None:
    """The crop's healthy class folder, or None if the dataset has none (rice)."""
    return next((f for f, c in LEAF_CONDITIONS[crop].items() if c.category == HEALTHY), None)
