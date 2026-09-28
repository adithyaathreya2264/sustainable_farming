# Parked models

Written 2026-09-22, during the training phase, rather than left to be
rediscovered. Same discipline `STATE_OF_THE_SYSTEM.md` applies to every other
deferred item in this project.

Each entry states what is blocking the model and what would unblock it. The
distinction that matters throughout: **a blocked model is not a model that
needs more effort.** The models below are blocked on data that does not
exist, and no amount of retraining, tuning or model-family swapping changes
that. Retrying them without new data would be work that cannot succeed.

Market price prediction and YOLO insect detection were parked here originally.
Both have since been trained and ship (models 18 and 11 in `MODEL_RESULTS.md`),
so they are no longer listed.

Code for these lives under `ml/training/parked/` and `ml/algorithms/parked/`,
kept rather than deleted so the next attempt starts from something.

For what specifically would unblock each one — not just why it is blocked — see `ml/UNBLOCKING_PARKED_MODELS.md`.

---

## 1. Disease from photograph

**Update 2026-09-23 — partly attempted.** A crop-specific sugarcane leaf
dataset arrived, and a new model ("leaf condition from photo", model 10) was
trained against a bar written first. **It failed** once evaluated on capture
sessions it had never seen: macro-F1 0.5248, healthy precision 0.7684. Split by
photo instead, it had scored about 0.98, which was session memorisation. Full
detail in `MODEL_RESULTS.md` §10; the pipeline, class registry and serving
module are built and wait for better data. *(Later on 2026-09-23 a rice dataset
arrived — four diseases, no healthy class — and a conditional rice model plus a
YOLOv8 insect detector were trained; both runs were stopped before their test
reads. The insect detector was resumed on 2026-09-24 and ships, provisional;
rice was retrained the same day and ships, provisional and conditional (symptom
must be reported first). See `MODEL_RESULTS.md` §11-12.)* Ragi, maize and
cotton have no leaf model.

*(2026-09-26: leaf and produce models for coffee, tea, cauliflower, onion, potato and tomato fruit, plus wheat kernel damage, were trained and pass (models 20-28, `MODEL_RESULTS.md` §20-28). None of those crops is in the app's crop list yet. Ragi and maize still have no leaf dataset.)*

The text below is the original 2026-09-22 entry about PlantDoc, kept as written.

**Status (2026-09-22):** not trained this round. Both the CNN and the RandomForest variant.

**Blocker: PlantDoc does not contain four of the five seeded crops.**

Its 28 classes are apple, bell pepper, blueberry, cherry, corn, grape, peach,
potato, raspberry, soybean, squash, strawberry and tomato. There is **zero**
rice, ragi, cotton or sugarcane.

Narrowing to the app's crops, as intended, leaves maize only: three disease
classes (Corn Gray leaf spot 64, Corn leaf blight 179, Corn rust leaf 106 —
349 images) and **no healthy-maize class at all**. Such a model could never
output "your crop looks fine", only "which of these three diseases does this
most resemble", which in the field is worse than useless.

**This is not a technique problem.** Transfer learning, augmentation and class
narrowing were all available and none of them create classes the dataset does
not contain.

**Inherited artifacts are discarded, not trusted:**
- `disease_cnn_model.keras` (1.4 MB) was produced with `SMOKE_TEST = True` —
  2 epochs over roughly 320 images, with the test set doubling as the
  validation set. It is effectively a random classifier over 27 classes.
  Nothing in the file marked it as unusable; only the docstring did.
- `disease_model.pkl` (214 MB) is a 400-tree unconstrained RandomForest over
  55 colour/texture features and about 2,340 samples, at a self-admitted 18.6%
  accuracy. That size on that feature count is a memorisation signature. It was
  nonetheless wired in as the live disease path.

**What would unblock it:** leaf images for rice, ragi, cotton and sugarcane,
with a healthy class per crop. Roughly 150+ images per class before the
question is even worth asking.

---

## 2. Disease presence and insect presence questionnaires

**Status:** not trained. No bar was written for either, because a bar would be
meaningless before the data question is settled.

**Blocker: the data is synthetic and covers the wrong crops.**

- `synthetic_disease_presence_30_questions.csv` — 150 rows, scoped to tomato
  Early Blight.
- `synthetic_insect_presence_30_questions.csv` — 150 rows, scoped to armyworm.

The app's crops are rice, ragi, maize, cotton and sugarcane. **Overlap: none.**

Three further problems, each independent:

1. **150 rows across 30 binary features** describes a 2^30 space. Massively
   underdetermined.
2. **The labels contradict their own gating question.** One row answers "No" to
   *"Is the pest in the image an armyworm?"* and is still labelled `Present`.
3. **"Not asked" is encoded identically to "No."** The inference code was
   `1 if answers.get(q) == "Yes" else 0`, so a farmer who answered 3 of 30
   questions is scored as having answered "No" to the other 27 — a guaranteed
   false negative, with no error raised.

**What would unblock it:** real, non-synthetic presence observations covering
the seeded crops, with an explicit unanswered state distinct from "no". The
app's `scouting_observations` table is already collecting real field data and
is the natural eventual source.

---

## 3. YOLO disease segmentation

**Status:** not trained. The parked script is
`ml/training/parked/train_disease_segmentation_model.py`.

**Blockers:**
- No `data.yaml` exists for `crop_diseases_yolo`, and the dataset itself is not
  in `datasets/`.
- The inherited raw data was roughly 50 images, with most label files 38 bytes
  (a single bounding box apiece).
- The preparation script reads hardcoded POSIX paths (`/tmp/reextract/`),
  leftovers from another machine that fail immediately here.
- No trained weights were ever produced; `disease_segmentation_model/` does not
  exist.

**What would unblock it:** a real annotated disease segmentation or detection
dataset. 50 images is not a starting point.

---

## 4. Soil fertility — failed its bar, distinct from the above

**Update 2026-09-25 — superseded.** Model 5b, trained on new labelled soil tests
(5,636 samples, 1,566 High), clears its bar (`MODEL_RESULTS.md` §5b). The source
of that data was not disclosed, so it ships marked provenance-unverified. The
entry below is kept as written.

Listed here for completeness, but it is a different kind of entry: it was
trained, measured, and **failed**. See `MODEL_RESULTS.md` section 5.

macro-F1 0.6944 against a bar of 0.75. Class 2 is 39 rows total. A validation
sweep across seven model families and three resampling strategies was run
before declaring the ceiling; threshold shifting looked strong on validation
(0.8153) and collapsed on test (0.6944), which is itself the evidence — a
decision tuned on 8 rows fits noise.

Removing it cost nothing, because `fertilizer_recommendation.py` computed its
output and then never used it.

**What would unblock it:** substantially more high-fertility samples, with
geography attached so the distribution question is answerable at all.

---

## Inherited artifacts: all discarded

None of `ml(1)/saved_models/` is served. Every shipped model in
`MODEL_RESULTS.md` was retrained from source in this phase.

This is deliberate beyond the quality problems above. The inherited pickles
were written under scikit-learn 1.8.0 while the inherited `requirements.txt`
pinned only `scikit-learn>=1.3.0`. Tree-ensemble pickles are brittle across
minor versions, so a fresh environment following that file could have loaded
them with silent warnings or failed outright. Retraining from source removes
that hazard entirely, and `ml/requirements.txt` now pins exact versions.
