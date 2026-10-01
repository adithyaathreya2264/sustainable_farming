"""Feature extraction shared between training and serving.

Anything in here is imported by both a `ml/training/*` script and its
corresponding `ml/algorithms/*` module. That is the entire reason the package
exists: a feature function defined twice is a feature function that will
eventually be edited once.
"""
