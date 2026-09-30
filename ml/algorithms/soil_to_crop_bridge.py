"""Photograph your soil, get a crop shortlist. The two models barely share a
vocabulary, and this is honest about where that breaks.

## The import bug this file used to have

It read `from ml.algorithms.soil_type_prediction import ...` while living in a
directory named `ml(1)`. `ml(1)` is not a valid Python identifier, so that
package could never be imported — and on this machine the name `ml` resolved to
a *different*, unrelated sibling package containing the dataset cleaners. The
module was dead code. The merge into `ml/` fixes it, and this is the only file
that had the problem, since every other module used path-based loading.

## The vocabulary mismatch, kept from the inherited docstring because it stands

The photo classifier knows 4 classes: Alluvial, Black, Cinder, Red. The
crop-from-soil-type model was fitted on soil-type strings from a dataset with
26 distinct values (Sandy loam, Laterite, Clay loam, Arid and Desert, ...), of
which only 3 overlap — and "Cinder" is not among them.

So roughly one in four things the camera can recognise has nowhere to go. This
bridge maps what genuinely maps and **fails loudly** for what does not, rather
than substituting a "close enough" soil type the crop model never saw. A wrong
soil type produces a confident, wrong crop recommendation, which is worse than
no answer.

Cinder soil is also volcanic/ashy ground that is marginal for the field crops
this app covers, so the gap matters less in practice than the 1-in-4 figure
suggests. But it is a real hole and it is reported, not smoothed over.
"""

from __future__ import annotations

from ml.algorithms.crop_recommendation import recommend_crop_from_soil_type
from ml.algorithms.soil_type_prediction import predict_soil_type
from ml.features.soil_image import ImageSource

# Image-classifier label -> the crop model's training vocabulary. Only genuine,
# direct matches. Cinder Soil is absent because the crop model has no such
# category, not because the mapping was overlooked.
SOIL_TYPE_BRIDGE = {
    "Alluvial Soil": "Alluvial",
    "Black Soil": "Black",
    "Red Soil": "Red",
}


def recommend_crop_from_photo(
    source: ImageSource,
    temperature: float,
    humidity: float,
    ph: float,
    rainfall: float,
) -> dict:
    """Classify a soil photo, then recommend crops for that soil type.

    Returns a result carrying both stages, or an explanatory failure when the
    detected soil type has no counterpart in the crop model's vocabulary.
    """
    detected = predict_soil_type(source)
    soil_type = detected["predicted_soil_type"]
    mapped = SOIL_TYPE_BRIDGE.get(soil_type)

    if mapped is None:
        return {
            "soil_type_detected": soil_type,
            "soil_type_confidence_label": detected["confidence_label"],
            "recommended": None,
            "alternatives": [],
            "error": "soil_type_not_in_crop_model_vocabulary",
            "detail": (
                f"The photo was classified as {soil_type!r}, but the crop "
                f"recommendation model was never trained on that category. It "
                f"knows {sorted(SOIL_TYPE_BRIDGE.values())} plus other types no "
                f"photo classifier can currently produce. Ask the farmer to "
                f"select their soil type manually instead."
            ),
        }

    recommendation = recommend_crop_from_soil_type(
        soil_type=mapped,
        temperature=temperature,
        humidity=humidity,
        ph=ph,
        rainfall=rainfall,
    )
    return {
        "soil_type_detected": soil_type,
        "soil_type_mapped_to": mapped,
        "soil_type_confidence_label": detected["confidence_label"],
        **recommendation,
    }
