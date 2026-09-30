"""
ml/algorithms/disease_prediction.py
Uses the classical color/texture model (18.6% accuracy — see
train_disease_model.py's honesty note). This is wired up as the working
reference implementation; swap MODEL_PATH for disease_cnn_model.keras
once you've trained that properly on a GPU machine, and this file's
predict_disease() signature can stay the same for the backend layer.
"""
import os as _os
BASE_DIR = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))  # -> .../ml, works regardless of where this project is placed
import numpy as np
from PIL import Image
from scipy import ndimage
import joblib

MODEL_PATH = _os.path.join(BASE_DIR, "saved_models/disease_model.pkl")
_bundle = joblib.load(MODEL_PATH)
_model = _bundle["model"]
_img_size = _bundle["img_size"]


def _extract_features(path: str) -> np.ndarray:
    img = Image.open(path).convert("RGB").resize(_img_size)
    rgb = np.array(img) / 255.0
    hsv = np.array(img.convert("HSV")) / 255.0

    features = []
    for channel in range(3):
        hist, _ = np.histogram(hsv[:, :, channel], bins=12, range=(0, 1))
        features.extend(hist / hist.sum())

    gray = np.array(img.convert("L")) / 255.0
    local_var = ndimage.generic_filter(gray, np.var, size=5)
    features.append(local_var.mean())
    features.append(local_var.std())
    features.extend([rgb[:, :, i].mean() for i in range(3)])
    features.extend([rgb[:, :, i].std() for i in range(3)])

    return np.array(features).reshape(1, -1)


def predict_disease(image_path: str) -> dict:
    features = _extract_features(image_path)
    prediction = str(_model.predict(features)[0])
    probabilities = dict(zip(_model.classes_, _model.predict_proba(features)[0]))
    top3 = sorted(probabilities.items(), key=lambda kv: kv[1], reverse=True)[:3]
    return {
        "predicted_class": prediction,
        "confidence": round(float(probabilities[prediction]), 3),
        "top_3": [{"class": str(c), "confidence": round(float(p), 3)} for c, p in top3],
        "warning": "This model is only 18.6% accurate (classical CV features, "
                   "not a CNN — see train_disease_model.py). Do not treat this "
                   "as production-reliable; train the CNN version on a GPU for real use.",
    }


if __name__ == "__main__":
    import glob
    sample = glob.glob(_os.path.join(BASE_DIR, "datasets", "plantdoc", "test", "Tomato leaf late blight", "*"))[0]
    print(predict_disease(sample))
