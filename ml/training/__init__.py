"""Offline training scripts. Each is run as a module from the repo root:

    python -m ml.training.train_crop_recommendation_model

Every script writes its artifact to ml/artifacts/ and prints a verdict against
the bar in ml/MODEL_BARS.md. Scripts under parked/ are not part of the active
pipeline - see ml/PARKED_MODELS.md for why each is there.
"""
