"""
ml/training/train_disease_cnn_model.py

Algorithm: Convolutional Neural Network, trained FROM SCRATCH (small
architecture) with data augmentation.

WHY FROM SCRATCH INSTEAD OF TRANSFER LEARNING: transfer learning
(MobileNet/ResNet + ImageNet weights) would very likely do meaningfully
better than this, and is what you should actually use for production —
but it requires downloading pretrained weights from
storage.googleapis.com, which this sandbox's network blocks (403
Forbidden, confirmed in train_soil_type_model.py's revision history).
This script is written to run correctly wherever that isn't blocked
(Colab, your own machine, most cloud VMs) — just uncomment the transfer
learning block below and it'll use pretrained weights automatically.

WHAT WAS ACTUALLY VERIFIED HERE: this script was run on a REDUCED subset
(see SMOKE_TEST below) purely to confirm the code has no bugs and the
training loop completes — not to produce a usable model. This sandbox has
1 CPU core and no GPU; full training (all 2,340 images, 15-30 epochs)
would take a very long time here. Run the full version on a GPU (Colab's
free tier, ~15 min for this dataset size) for a real, usable model.

Excludes "Tomato two spotted spider mites leaf" — only 2 training images,
0 test images in the source data.
"""
import os as _os
BASE_DIR = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))  # -> .../ml, works regardless of where this project is placed
import tensorflow as tf
from tensorflow.keras import layers, models
import json
import os

TRAIN_DIR = _os.path.join(BASE_DIR, "datasets", "plantdoc", "train")
TEST_DIR = _os.path.join(BASE_DIR, "datasets", "plantdoc", "test")
MODEL_PATH = _os.path.join(BASE_DIR, "saved_models/disease_cnn_model.keras")
LABELS_PATH = _os.path.join(BASE_DIR, "saved_models/disease_cnn_labels.json")

IMG_SIZE = (96, 96)
BATCH_SIZE = 32

# --- Set this to False for a real production run (all data, more epochs) ---
SMOKE_TEST = True
EPOCHS = 2 if SMOKE_TEST else 25


def build_model(num_classes):
    # --- FROM-SCRATCH small CNN (works with no internet access) ---
    inputs = layers.Input(shape=IMG_SIZE + (3,))
    x = layers.Rescaling(1.0 / 255)(inputs)
    x = layers.RandomFlip("horizontal")(x)
    x = layers.RandomRotation(0.1)(x)
    for filters in (32, 64, 128):
        x = layers.Conv2D(filters, 3, activation="relu", padding="same")(x)
        x = layers.MaxPooling2D()(x)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dense(128, activation="relu")(x)
    x = layers.Dropout(0.4)(x)
    outputs = layers.Dense(num_classes, activation="softmax")(x)
    return models.Model(inputs, outputs)

    # --- TRANSFER LEARNING version — uncomment for a real run with internet access ---
    # base = tf.keras.applications.MobileNetV2(
    #     input_shape=IMG_SIZE + (3,), include_top=False, weights="imagenet")
    # base.trainable = False
    # inputs = layers.Input(shape=IMG_SIZE + (3,))
    # x = tf.keras.applications.mobilenet_v2.preprocess_input(inputs)
    # x = base(x, training=False)
    # x = layers.GlobalAveragePooling2D()(x)
    # x = layers.Dropout(0.3)(x)
    # outputs = layers.Dense(num_classes, activation="softmax")(x)
    # return models.Model(inputs, outputs)


def main():
    train_ds = tf.keras.utils.image_dataset_from_directory(
        TRAIN_DIR, image_size=IMG_SIZE, batch_size=BATCH_SIZE,
        label_mode="categorical", seed=42,
        class_names=sorted(d for d in os.listdir(TRAIN_DIR)
                            if d != "Tomato two spotted spider mites leaf"),
    )
    test_ds = tf.keras.utils.image_dataset_from_directory(
        TEST_DIR, image_size=IMG_SIZE, batch_size=BATCH_SIZE,
        label_mode="categorical", seed=42,
        class_names=sorted(d for d in os.listdir(TRAIN_DIR)
                            if d != "Tomato two spotted spider mites leaf"),
    )
    class_names = train_ds.class_names
    print(f"{len(class_names)} classes")

    if SMOKE_TEST:
        print("SMOKE_TEST=True — using a small subset and 2 epochs just to verify correctness.")
        train_ds = train_ds.take(10)   # ~320 images instead of 2340
        test_ds = test_ds.take(3)

    train_ds = train_ds.prefetch(tf.data.AUTOTUNE)
    test_ds = test_ds.prefetch(tf.data.AUTOTUNE)

    model = build_model(len(class_names))
    model.compile(optimizer="adam", loss="categorical_crossentropy", metrics=["accuracy"])
    model.fit(train_ds, validation_data=test_ds, epochs=EPOCHS)

    test_loss, test_acc = model.evaluate(test_ds)
    print(f"Test accuracy: {test_acc:.3f}" + ("  (SMOKE TEST — not a real result)" if SMOKE_TEST else ""))

    model.save(MODEL_PATH)
    with open(LABELS_PATH, "w") as f:
        json.dump(class_names, f)
    print(f"Saved -> {MODEL_PATH}")


if __name__ == "__main__":
    main()
