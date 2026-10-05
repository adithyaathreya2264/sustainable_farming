"""
ml/training/train_disease_presence_model.py

Algorithm: Decision Tree classification.
Why Decision Tree specifically (not Random Forest/XGBoost, which
everything else in this project uses): every one of the 30 input features
is a plain Yes/No answer to an extension-officer-style symptom question
("Is there a yellow halo around the spots?"). A single decision tree on
binary features is directly readable as a diagnostic checklist a
non-technical field officer could follow by hand — that interpretability
is worth more here than a marginal accuracy gain from ensembling, given
the small dataset (150 rows) and the fact this is meant to mirror how a
human would actually reason through the questions.

Data is SYNTHETIC (per the filename) — generated to look like Early
Blight-vs-not-Early-Blight in tomato, not from real farmer-reported
observations. Treat this as a working proof of concept for the checklist
pattern, not as validated on real cases.
"""
import os as _os
BASE_DIR = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))  # -> .../ml, works regardless of where this project is placed
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import LabelEncoder
import joblib

DATA_PATH = _os.path.join(BASE_DIR, "datasets/synthetic_disease_presence_30_questions.csv")
MODEL_PATH = _os.path.join(BASE_DIR, "saved_models/disease_presence_model.pkl")
TARGET = "Disease_Present"


def main():
    df = pd.read_csv(DATA_PATH)
    features = [c for c in df.columns if c != TARGET]

    # Encode Yes/No -> 1/0 for every question column
    X = df[features].apply(lambda col: (col == "Yes").astype(int))
    y = df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = DecisionTreeClassifier(max_depth=5, class_weight="balanced", random_state=42)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    print(f"Accuracy: {accuracy_score(y_test, preds):.3f}  (n={len(df)} — small dataset, treat cautiously)")
    print(classification_report(y_test, preds, zero_division=0))

    # Show which questions the tree actually uses — this IS the diagnostic checklist
    importances = sorted(zip(features, model.feature_importances_), key=lambda kv: -kv[1])
    print("Top questions the model actually uses:")
    for q, imp in importances[:5]:
        if imp > 0:
            print(f"  {imp:.3f}  {q}")

    joblib.dump({"model": model, "features": features}, MODEL_PATH)
    print(f"Saved -> {MODEL_PATH}")


if __name__ == "__main__":
    main()
