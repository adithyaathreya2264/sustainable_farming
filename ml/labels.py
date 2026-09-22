"""The boundary between what a model computes and what the app is allowed to say.

Two separate jobs, both of which exist because a raw model output is not a
safe thing to hand to a farmer.

## 1. Confidence must not be a number

`backend/plan/phase4-part2.txt` line 33 directs that numeric confidence be
dropped in favour of a categorical badge, "rather than a numeric score that
implies false precision." A random forest reporting 0.87 is reporting the
fraction of its trees that voted a particular way on synthetic training data;
rendering that as "87% confident" tells a farmer something the model never
established.

So the float is mapped to a label *here*, inside the ML layer, and only the
label is returned. It is deliberately not returned alongside the float for the
caller to discard, because that arrangement only holds until someone forgets.

The three labels match vocabulary already in the codebase: `unverified` mirrors
`ruleEngine.js`'s `UNVERIFIED_PREFIX`, and `provisional` mirrors
`schemeMatcher.js`'s `match_confidence`.

## 2. Model labels must be translated into the app's crop vocabulary

Four datasets spell the same plant four ways (`Cotton(lint)`, `cotton`,
`Ragi( naachnnii)`, `Jowar(Sorghum)`). `ml/prep/common.py` already reconciles
all of them, and its alias table has caught two real bugs in this repo —
coriander leaf vs seed, and mustard vs rapeseed being wrongly merged. This
module reuses that table rather than starting a second one, because two crop
vocabularies that drift apart is a worse failure than either one being
imperfect.

`is_seeded_crop` is carried on every result because a recommendation the app
cannot act on is a different thing from one it can: only five crops
(Rice, Ragi, Maize, Cotton, Sugarcane) exist in the `crops` table, so a model
confidently returning "jute" has produced something the UI has no planting flow
for. The caller decides what to do about that; this module makes it visible.
"""

from __future__ import annotations

from ml.prep.common import SEEDED_CROPS, crop_display_name, crop_key

# --------------------------------------------------------------------------
# Confidence
# --------------------------------------------------------------------------

# Thresholds are justified per model in ml/MODEL_BARS.md. They are intentionally
# coarse: the underlying probabilities are not calibrated, so finer bands would
# imply a resolution the numbers do not have.
VERIFIED = "verified"
PROVISIONAL = "provisional"
UNVERIFIED = "unverified"

_DEFAULT_PROVISIONAL_AT = 0.45
_DEFAULT_VERIFIED_AT = 0.75


def confidence_label(
    probability: float,
    *,
    provisional_at: float = _DEFAULT_PROVISIONAL_AT,
    verified_at: float = _DEFAULT_VERIFIED_AT,
    allow_verified: bool = False,
) -> str:
    """Map a model probability to a categorical label. The float stops here.

    `allow_verified` defaults to False on purpose. "Verified" in this codebase
    means a human domain expert signed the guidance off — `agronomic-rules-draft.md`
    is still awaiting KVK/ICAR review, and no model output has been reviewed by
    anyone. A model cannot promote itself to verified by being confident; only a
    caller that knows a human checked its output may pass True.
    """
    if probability >= verified_at:
        return VERIFIED if allow_verified else PROVISIONAL
    if probability >= provisional_at:
        return PROVISIONAL
    return UNVERIFIED


# --------------------------------------------------------------------------
# Crop vocabulary
# --------------------------------------------------------------------------


def describe_crop(raw_label: str) -> dict:
    """Translate a model's raw class label into the app's crop vocabulary.

    Returns the canonical slug, the name the farmer already sees elsewhere in
    the app, and whether the app actually has this crop seeded.
    """
    key = crop_key(raw_label)
    if key is None:
        # crop_key only returns None for empty/punctuation-only input. Surface
        # the raw label rather than inventing a slug for it.
        return {
            "crop_key": None,
            "display_name": str(raw_label),
            "is_seeded_crop": False,
            "raw_label": str(raw_label),
        }
    return {
        "crop_key": key,
        "display_name": crop_display_name(key),
        "is_seeded_crop": key in SEEDED_CROPS,
        "raw_label": str(raw_label),
    }


def rank_predictions(
    classes, probabilities, *, top_k: int = 4, allow_verified: bool = False
) -> list[dict]:
    """Rank a classifier's classes by probability, in the app's vocabulary.

    Each entry carries a categorical `confidence_label` and never the
    underlying probability.
    """
    ranked = sorted(zip(classes, probabilities), key=lambda kv: kv[1], reverse=True)
    return [
        {
            **describe_crop(str(label)),
            "confidence_label": confidence_label(
                float(probability), allow_verified=allow_verified
            ),
        }
        for label, probability in ranked[:top_k]
    ]
