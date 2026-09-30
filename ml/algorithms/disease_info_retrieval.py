"""Crop-scoped retrieval over the disease Q&A corpus.

## The crop argument is required, on purpose

Unscoped retrieval over all 88 (crop, disease) pairs was measured at recall@3 =
0.5447 against a bar of 0.70 and **failed** (`MODEL_BARS.md` section 4). Scoped
to the farmer's crop it reaches 0.7614 and clears a separate, higher bar
written for that mode (section 4b).

Those are two different models, and only the scoped one ships. Making `crop` a
required positional argument is what keeps that true: the failing mode is not
reachable by forgetting a keyword.

This costs nothing, because the app always knows the crop. A disease question
arrives through a scouting observation, which belongs to a planting, which has
a `crop_id`.

## Shared symptoms are surfaced, not silently resolved

68 distinct question strings (137 rows, 6.1% of the corpus) are recorded
against more than one (crop, disease) pair — for instance identical
bacterial-ooze text under both Tomato/Bacterial Wilt and sugarcane/Grassy
Shoot. These are not assumed to be mistakes with a knowable correct answer;
bacterial wilt genuinely does present alike across crops.

So when a match lands on one of them, `also_seen_in` lists the other pairs and
the result is flagged `shared_symptom`. Picking one silently would present a
guess as a finding.

## Structured output only

Returns matched disease identifiers, remedy text keyed by language, and the
languages actually available — never a rendered sentence. The corpus carries
en/hi/mr; the app ships 10 locales, so any prose composed here would be
unlocalisable for 7 of them. `remedy_hi` is additionally unreliable: 50 rows
hold the English string verbatim, and those are flagged per result.

## No similarity scores cross the boundary

Cosine similarity is mapped to a categorical label in `ml/labels.py`, like
every other model's confidence. `LOW_CONFIDENCE_THRESHOLD` is kept at the
inherited 0.15 — it was never measured, and lowering or raising it on intuition
is exactly what `MODEL_BARS.md` exists to prevent.
"""

from __future__ import annotations

from ml import paths
from ml.algorithms._loader import load_artifact
from ml.labels import confidence_label
from ml.prep.common import crop_key

# Inherited, unmeasured. Below this a match is treated as "nothing close in the
# knowledge base", which is a better answer than an irrelevant remedy.
LOW_CONFIDENCE_THRESHOLD = 0.15

TOP_K = 3


def _index() -> dict:
    return load_artifact(paths.DISEASE_QA_INDEX)


def known_crops() -> list[str]:
    """Crops this corpus has disease coverage for.

    Note ragi is absent: 4 of the app's 5 seeded crops are covered.
    """
    bundle = _index()
    return sorted(bundle["source_df"]["crop_name_en"].astype(str).str.strip().unique())


def _shared_lookup(bundle: dict, question: str) -> list:
    normalised = question.strip().lower().rstrip(".")
    return bundle.get("shared_symptom_questions", {}).get(normalised, [])


def find_disease_info(query: str, crop: str, top_k: int = TOP_K) -> dict:
    """Find diseases of `crop` matching a free-text symptom description.

    `crop` is required - see the module docstring. Matching is over stored
    phrasings in English, Hindi and Marathi at once, so a query in any of the
    three can match phrasings recorded in the others.
    """
    from sklearn.metrics.pairwise import cosine_similarity

    bundle = _index()
    source = bundle["source_df"]
    questions = bundle["questions_df"]

    key = crop_key(crop)
    crops_in_corpus = source["crop_name_en"].astype(str).str.strip()
    mask = crops_in_corpus.map(lambda name: crop_key(name) == key)
    if not mask.any():
        return {
            "matches": [],
            "crop": crop,
            "crop_key": key,
            "reason": "no_coverage_for_crop",
            "detail": (
                f"This corpus has no disease records for {crop!r}. "
                f"Covered crops: {known_crops()}"
            ),
        }

    # Restrict candidates to phrasings belonging to this crop before ranking.
    allowed_rows = set(source.index[mask])
    candidate_positions = [
        position
        for position, row_idx in enumerate(questions["row_idx"].to_numpy())
        if row_idx in allowed_rows
    ]

    similarities = cosine_similarity(
        bundle["vectorizer"].transform([query]), bundle["tfidf_matrix"]
    )[0]

    ranked = sorted(candidate_positions, key=lambda p: similarities[p], reverse=True)

    matches = []
    seen: set = set()
    for position in ranked:
        score = float(similarities[position])
        if score < LOW_CONFIDENCE_THRESHOLD:
            break
        row_idx = questions.iloc[position]["row_idx"]
        row = source.loc[row_idx]
        identity = (str(row["crop_name_en"]).strip(), str(row["disease_name_en"]).strip())
        if identity in seen:
            continue
        seen.add(identity)

        matched_question = questions.iloc[position]["question"]
        also_seen_in = [
            {"crop": c, "disease": d}
            for c, d in _shared_lookup(bundle, str(row["question_en"]))
            if (c, d) != identity
        ]

        remedies = {
            "en": row.get("remedy_en"),
            "hi": row.get("remedy_hi"),
            "mr": row.get("remedy_mr"),
        }
        matches.append(
            {
                "crop": identity[0],
                "crop_key": crop_key(identity[0]),
                "disease": identity[1],
                "disease_type": row.get("disease_type"),
                "severity": row.get("severity_level"),
                "cause": row.get("cause"),
                "affected_plant_part": row.get("affected_plant_part"),
                "matched_question": matched_question,
                "matched_question_lang": questions.iloc[position]["lang"],
                "confidence_label": confidence_label(score),
                "remedies": {k: v for k, v in remedies.items() if v is not None},
                "available_languages": [k for k, v in remedies.items() if v is not None],
                # 50 rows hold the English string verbatim in the Hindi column.
                "hindi_is_english_fallback": bool(
                    remedies.get("hi") is not None
                    and str(remedies["hi"]) == str(remedies.get("en"))
                ),
                "shared_symptom": bool(also_seen_in),
                "also_seen_in": also_seen_in,
            }
        )
        if len(matches) >= top_k:
            break

    if not matches:
        return {
            "matches": [],
            "crop": crop,
            "crop_key": key,
            "reason": "no_close_match",
            "detail": (
                "Nothing in the knowledge base resembles this description "
                "closely enough to be worth showing."
            ),
        }

    return {
        "matches": matches,
        "crop": crop,
        "crop_key": key,
        "scope": "crop_scoped",
        "note": (
            "Retrieval over a corpus with unrecorded provenance, covering "
            "en/hi/mr only. Results are documented remedies from that corpus, "
            "not a diagnosis."
        ),
    }


def _crop_rows(crop: str):
    bundle = _index()
    source = bundle["source_df"]
    key = crop_key(crop)
    mask = source["crop_name_en"].astype(str).str.strip().map(lambda name: crop_key(name) == key)
    return source[mask], key


def list_diseases(crop: str) -> dict:
    """Every disease the corpus records for `crop`.

    This is the "see all diseases for this crop" path that bar 4b's shipping
    condition depends on (MODEL_RESULTS.md section 4b): it has recall 1.0 by
    construction, so the ranked shortlist is never the only way to a diagnosis.
    """
    rows, key = _crop_rows(crop)
    if rows.empty:
        return {"crop": crop, "crop_key": key, "diseases": [], "reason": "no_coverage_for_crop"}
    diseases = []
    for name, group in rows.groupby(rows["disease_name_en"].astype(str).str.strip(), sort=True):
        diseases.append(
            {
                "disease": name,
                "disease_type": group["disease_type"].mode().iloc[0],
                "affected_plant_parts": sorted(
                    group["affected_plant_part"].dropna().astype(str).str.strip().unique()
                ),
            }
        )
    return {"crop": crop, "crop_key": key, "diseases": diseases}


def disease_detail(crop: str, disease: str, max_remedies: int = 5) -> dict:
    """Stable facts plus the distinct documented remedies for one disease.

    `cause` and `disease_type` are stable per pair; remedies vary row to row
    (DATASETS_STATUS.md), so several distinct ones are returned rather than an
    arbitrary single row.
    """
    rows, key = _crop_rows(crop)
    rows = rows[rows["disease_name_en"].astype(str).str.strip().str.lower() == disease.strip().lower()]
    if rows.empty:
        return {"crop": crop, "crop_key": key, "disease": disease, "reason": "unknown_disease"}

    remedies, seen = [], set()
    for _, row in rows.iterrows():
        en = row.get("remedy_en")
        if en is None or str(en) in seen:
            continue
        seen.add(str(en))
        hi = row.get("remedy_hi")
        remedies.append(
            {
                "en": en,
                "hi": hi,
                "mr": row.get("remedy_mr"),
                "hindi_is_english_fallback": bool(hi is not None and str(hi) == str(en)),
            }
        )
        if len(remedies) >= max_remedies:
            break

    first = rows.iloc[0]
    return {
        "crop": str(first["crop_name_en"]).strip(),
        "crop_key": key,
        "disease": str(first["disease_name_en"]).strip(),
        "disease_type": first.get("disease_type"),
        "cause": first.get("cause"),
        "affected_plant_parts": sorted(rows["affected_plant_part"].dropna().astype(str).str.strip().unique()),
        "severity_levels": sorted(rows["severity_level"].dropna().astype(str).str.strip().unique()),
        "remedies": remedies,
        "confidence_label": "unverified",
        "note": (
            "Documented remedies from a corpus with unrecorded provenance, "
            "covering en/hi/mr only. Not agronomist-reviewed."
        ),
    }
