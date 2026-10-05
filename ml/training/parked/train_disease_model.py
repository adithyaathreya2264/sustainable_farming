"""
ml/training/train_disease_model.py

Algorithm: same color/texture-feature + Random Forest approach as
train_soil_type_model.py, for the same reason — this sandbox can't reach
storage.googleapis.com to download pretrained CNN weights.

IMPORTANT HONESTY NOTE (read before trusting this model's accuracy):
unlike soil type, plant disease identification across 26 species/disease
combinations is NOT primarily a color problem — many diseases look like
"leaf with a slightly different spot pattern", which color histograms
don't capture well. Expect meaningfully lower accuracy here than the
soil-type model. This script exists to give you a real, honest baseline
number rather than skip the exercise — treat a low score as a genuine
signal that this problem needs a real CNN (transfer learning on
MobileNet/ResNet/EfficientNet with ImageNet weights), not as a bug to fix
in this script. Run the CNN version on a GPU machine with normal internet
access (Colab) for production accuracy.

"Tomato two spotted spider mites leaf" is excluded: only 2 training images
and 0 test images exist for it in the source dataset — not enough to
train or evaluate.
"""
import os as _os
BASE_DIR = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))  # -> .../ml, works regardless of where this project is placed
import numpy as np
from PIL import Image
import glob
import os
from scipy import ndimage
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score
import joblib

TRAIN_DIR = _os.path.join(BASE_DIR, "datasets", "plantdoc", "train")
TEST_DIR = _os.path.join(BASE_DIR, "datasets", "plantdoc", "test")
MODEL_PATH = _os.path.join(BASE_DIR, "saved_models/disease_model.pkl")
EXCLUDE_CLASSES = {"Tomato two spotted spider mites leaf"}

IMG_SIZE = (96, 96)  # smaller than the soil model — more images, need faster extraction


def extract_features(path: str) -> np.ndarray:
    img = Image.open(path).convert("RGB").resize(IMG_SIZE)
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

    return np.array(features)


def load_dataset(directory: str):
    X, y = [], []
    class_names = sorted(d for d in os.listdir(directory) if d not in EXCLUDE_CLASSES)
    for label in class_names:
        for path in glob.glob(f"{directory}/{label}/*"):
            try:
                X.append(extract_features(path))
                y.append(label)
            except Exception:
                continue
    return np.array(X), np.array(y), class_names


def main():
    print("Extracting features from training images (this takes a few minutes)...")
    X_train, y_train, class_names = load_dataset(TRAIN_DIR)
    print(f"Train: {X_train.shape[0]} images, {len(class_names)} classes")

    print("Extracting features from test images...")
    X_test, y_test, _ = load_dataset(TEST_DIR)
    print(f"Test: {X_test.shape[0]} images")

    model = RandomForestClassifier(n_estimators=400, class_weight="balanced", random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    acc = accuracy_score(y_test, preds)
    print(f"\nTest accuracy: {acc:.3f}")
    print(classification_report(y_test, preds, zero_division=0))

    joblib.dump({"model": model, "class_names": class_names, "img_size": IMG_SIZE}, MODEL_PATH)
    print(f"Saved -> {MODEL_PATH}")


if __name__ == "__main__":
    main()
