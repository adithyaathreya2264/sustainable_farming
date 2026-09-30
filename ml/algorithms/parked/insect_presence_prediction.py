"""
ml/algorithms/insect_presence_prediction.py
Same pattern as disease_presence_prediction.py, for armyworm presence.
Same caveat applies: unanswered questions default to "No" — always pass
a fully-answered 30-question checklist, not a partial one.
"""
import os as _os
BASE_DIR = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))  # -> .../ml, works regardless of where this project is placed
import pandas as pd
import joblib

MODEL_PATH = _os.path.join(BASE_DIR, "saved_models/insect_presence_model.pkl")
_bundle = joblib.load(MODEL_PATH)
_model = _bundle["model"]
_features = _bundle["features"]


def predict_insect_presence(answers: dict) -> dict:
    row = pd.DataFrame([{q: 1 if answers.get(q) == "Yes" else 0 for q in _features}])
    prediction = str(_model.predict(row)[0])
    probabilities = dict(zip(_model.classes_, _model.predict_proba(row)[0]))
    return {
        "prediction": prediction,
        "confidence": round(float(probabilities[prediction]), 3),
    }


if __name__ == "__main__":
    sample_answers = {q: "Yes" for q in _features[:10]}
    sample_answers.update({q: "No" for q in _features[10:]})
    print(predict_insect_presence(sample_answers))
