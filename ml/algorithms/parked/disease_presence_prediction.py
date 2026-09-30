"""
ml/algorithms/disease_presence_prediction.py
Takes a dict of {question_text: "Yes"/"No"} answers and returns a
presence prediction — meant for a guided checklist UI (extension officer
or farmer answering questions), not a photo.

IMPORTANT CAVEAT (found while verifying this module): any question you
don't include in `answers` is treated as "No", not as "unknown" — there's
no way to represent "not yet asked" with this encoding. Answering only 3
of the 30 questions, even with strong positive symptoms, can flip the
prediction to "Not Present" because the other 27 default to "No" and the
tree's decision path needs several symptoms together, not just the
single most-important one. In a real UI, don't call this until the
farmer/officer has answered all 30 questions — a partial checklist is
actively misleading here, not just less accurate.
"""
import os as _os
BASE_DIR = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))  # -> .../ml, works regardless of where this project is placed
import pandas as pd
import joblib

MODEL_PATH = _os.path.join(BASE_DIR, "saved_models/disease_presence_model.pkl")
_bundle = joblib.load(MODEL_PATH)
_model = _bundle["model"]
_features = _bundle["features"]


def predict_disease_presence(answers: dict) -> dict:
    """answers: {question: "Yes"/"No"} — missing questions default to "No"."""
    row = pd.DataFrame([{q: 1 if answers.get(q) == "Yes" else 0 for q in _features}])
    prediction = str(_model.predict(row)[0])
    probabilities = dict(zip(_model.classes_, _model.predict_proba(row)[0]))
    return {
        "prediction": prediction,
        "confidence": round(float(probabilities[prediction]), 3),
    }


if __name__ == "__main__":
    # Full checklist answered (see the caveat above for why partial answers mislead)
    sample_answers = {q: "Yes" for q in _features[:10]}  # first 10 symptom questions positive
    sample_answers.update({q: "No" for q in _features[10:]})  # rest explicitly negative
    print(predict_disease_presence(sample_answers))
