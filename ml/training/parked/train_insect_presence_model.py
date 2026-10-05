"""
ml/training/train_insect_presence_model.py

Algorithm: Decision Tree classification — same reasoning as
train_disease_presence_model.py (30 binary checklist questions,
interpretability matters more than ensembling on a 150-row dataset).

Data is SYNTHETIC, modeled around armyworm presence specifically — not
real farmer-reported observations.
"""
import os as _os
BASE_DIR = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))  # -> .../ml, works regardless of where this project is placed
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib

DATA_PATH = _os.path.join(BASE_DIR, "datasets/synthetic_insect_presence_30_questions.csv")
MODEL_PATH = _os.path.join(BASE_DIR, "saved_models/insect_presence_model.pkl")
TARGET = "Insect_Present"


def main():
    df = pd.read_csv(DATA_PATH)
    features = [c for c in df.columns if c != TARGET]

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

    importances = sorted(zip(features, model.feature_importances_), key=lambda kv: -kv[1])
    print("Top questions the model actually uses:")
    for q, imp in importances[:5]:
        if imp > 0:
            print(f"  {imp:.3f}  {q}")

    joblib.dump({"model": model, "features": features}, MODEL_PATH)
    print(f"Saved -> {MODEL_PATH}")


if __name__ == "__main__":
    main()
