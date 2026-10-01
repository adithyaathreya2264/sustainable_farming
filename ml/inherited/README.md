# Inherited documentation

Kept from the contributed `ml(1)/` tree as a record of the original work. These
two files are **documentation only** and are not part of the pipeline.

- `index.html` — an interactive, line-by-line guide to all 29 original Python
  files, their algorithms, I/O contracts and dataflows. Genuinely useful for
  understanding the intent behind the code, and worth reading before touching
  anything under `ml/training/parked/`.
- `ORIGINAL-README.md` — the tree's own README, renamed so it does not collide
  with this file.

## What is stale in them

Both were written against a different layout and are no longer accurate:

- They describe a `datasets/` directory living inside the ML package. That
  never existed in this repository, which is why not one of the original
  training scripts would run. See `ml/paths.py`.
- Their links are absolute `file:///e:/major-project-research/ml/...` paths
  from the machine they were authored on, so they will not resolve here.
- `index.html` documents `saved_models/`. **Those artifacts have been
  deleted.** Every shipping model was retrained from source in this repository;
  see `ml/MODEL_RESULTS.md`. The originals were not reproducible — their
  pickles were written under scikit-learn 1.8.0 against a `>=1.3.0` pin, the
  Keras CNN was a 2-epoch smoke test, the disease forest was 214 MB at a
  self-admitted 18.6% accuracy, and the market-price models were trained on a
  dataset that is not present in this repo at all.

`ml/PARKED_MODELS.md` records what each of those models was and why it is not
being carried forward.
