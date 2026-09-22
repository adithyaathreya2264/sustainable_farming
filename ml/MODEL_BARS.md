# Model acceptance bars

**Written before any model in this phase was trained, and committed before
`MODEL_RESULTS.md` exists.** That ordering is the point of this file: a bar
chosen after seeing the result is not a bar. Git history is the evidence — if
this file's first commit does not predate the first commit of
`MODEL_RESULTS.md`, the bars below are worthless and should be treated as such.

A bar may be revised later only by adding a dated entry to §9 explaining what
was learned that justified the change. Silent edits defeat the file.

## How to read a bar

Each model has:

- **Metric** — what is measured, and on which split.
- **Bar** — the minimum to ship.
- **Baseline** — the trivial alternative it must beat. A high score on an easy
  or synthetic problem proves nothing; beating the thing you would do without a
  model is the real test. Several of these datasets are synthetic and highly
  separable, so the baseline comparison carries more weight here than the
  absolute number.
- **Why this number** — what makes it the threshold for acting on real land.

Everything is measured on a **test fold touched exactly once**, after all
tuning is finished on a separate validation fold.

---

## 1. Crop recommendation (N/P/K + weather to crop)

`merged_crop_dataset.csv`, 6,596 rows, 51 classes.

**Measured class imbalance:** class sizes run 7 to 461 (mean 129, median 100).
Fourteen classes have under 50 rows; `pumpkin` has 7. Macro-F1 over all 51
classes is therefore dominated by classes too small to learn or to measure, and
is reported but **not** used as the bar.

| | |
|---|---|
| **Metric** | Recall per seeded crop (rice, ragi, maize, cotton) on the test fold |
| **Bar** | **at least 0.85 recall for each of the four**, and weighted-F1 at least 0.90 overall |
| **Baseline** | Majority class = 0.070 accuracy. Must beat by a wide margin. |

**Why this number.** The four seeded crops have 100/293/100/100 rows — enough to
learn and enough to measure, unlike the long tail. This output drives seed and
input purchase, so being wrong about one of the four crops the app can actually
plant is the failure that costs a farmer money. 0.85 means at most about one in
seven such recommendations is wrong; below that the feature is not worth
shipping over an agronomist's rule of thumb.

The dataset is synthetically sampled from per-crop distributions and is known to
be highly separable, so a high score here is **evidence the pipeline works, not
evidence the model is good in a field.** Ships labeled provisional.

**Also required:** sugarcane is absent from all 51 labels, so this model can
never recommend one of the five seeded crops. This must be stated in
`MODEL_RESULTS.md`, not silently worked around.

---

## 2. Crop-from-soil-type (soil type + weather to crop)

`crop_soil_type_dataset.csv`, 3,100 rows, 31 classes, exactly 100 per class.

| | |
|---|---|
| **Metric** | Macro-F1 on the test fold (classes are perfectly balanced, so macro is fair here) |
| **Bar** | **at least 0.75** |
| **Baseline** | Majority class = 0.032 accuracy |

**Why this number.** Lower than model 1 because this model has strictly less
information: no N/P/K, just a soil-type string plus four weather values. 0.75
is the point at which the top-3 alternatives list is likely to contain the right
answer even when the top-1 is wrong, which is how this output is meant to be
used — as a shortlist, not a verdict.

**Exactly 100 rows per class across 31 classes is a synthetic-generation
signature.** Real crop distributions are not uniform. A good score here
overstates real-world performance and must be reported with that caveat.

---

## 3. Fertilizer targets (crop to N/P/K + pH range)

Not a model — a lookup built from `Fertilizer.csv`. There is no metric because
there is nothing to learn: N/P/K are constant per crop and only pH is jittered.

| | |
|---|---|
| **Bar** | The N/P/K-constancy assertion passes for all 97 crops, and the build fails loudly if it does not |
| **Baseline** | not applicable |

**Why.** Collapsing 19 near-duplicate rows per crop into one is only valid
because N/P/K genuinely do not vary within a crop. If a refreshed dump ever
breaks that, collapsing would fabricate a nutrient target, so the assertion is
the bar. This same assertion previously caught two real crop-alias bugs in this
repo (coriander leaf vs seed; mustard vs rapeseed).

**Also required:** sugarcane has no row in `Fertilizer.csv`. One of five seeded
crops therefore has no nutrient target. State it in the results.

---

## 4. Disease Q&A retrieval (free text to known disease + remedy)

`Indian_Crop_Disease_Dataset_Hindi_and_Marathi_NLP.csv`, 2,231 rows over 88
distinct (crop, disease) pairs, about 25 phrasings each, in EN/HI/MR.

Retrieval, not classification — so accuracy is the wrong frame. Evaluation is by
**held-out phrasing**: remove some phrasings of a pair from the index entirely,
use each as a query, and check whether the correct (crop, disease) pair is
returned. This is objective and needs no manual labelling, because the corpus
already tells us which pair each phrasing belongs to.

| | |
|---|---|
| **Metric** | Recall@3 of the correct (crop, disease) pair, on held-out phrasings |
| **Bar** | **at least 0.70 recall@3**, and **at least 0.50 recall@1** |
| **Baseline** | Random over 88 pairs = 0.034 recall@3 |

**Why these numbers.** Three results are shown, so recall@3 is what the farmer
actually experiences. At 0.70, roughly two in three searches surface the right
problem somewhere in the list; below that the farmer is reading irrelevant
remedies more often than useful ones, which is worse than telling them plainly
that we have no match. recall@1 is barred separately because a correct answer
ranked third next to two wrong ones still asks the farmer to adjudicate.

This model is **lower risk than the diagnostic models** — it surfaces remedies
already written in the corpus rather than inventing a diagnosis — so it ships
with ordinary caveats rather than the heavier gating.

**Known corpus defects to report:** some `remedy_hi` values are the English
string verbatim; `season` and `state` vary per phrasing and are noise, not
signal; coverage is 4 of 5 seeded crops (no ragi) and 3 of the app's 10 locales.

---

## 5. Soil fertility (12 soil chemistry features to class 0/1/2)

`soil_fertility.csv`, 880 rows. Class distribution 0: 45.6%, 1: 50.0%,
**2: 4.4% (39 rows)**.

| | |
|---|---|
| **Metric** | Macro-F1, and recall for class 2 specifically, on the test fold |
| **Bar** | **Macro-F1 at least 0.75 AND recall(class 2) at least 0.50** |
| **Baseline** | Majority class = 0.500 accuracy but only about 0.22 macro-F1 |

**Why these numbers.** Accuracy is barred against explicitly because a model
that ignores class 2 entirely still scores well on the other two classes and
looks excellent. Class 2 is high-fertility soil: failing to detect it tells a
farmer to apply fertiliser to land that does not need it, which costs money and
leaches nutrients. Half is a low bar in absolute terms and is set there only
because 39 samples cannot support a higher one — with a test fold of roughly 8
class-2 rows, recall has a resolution of about 0.12, so anything finer would be
measuring noise.

**This model ships labeled provisional regardless of its metric, or not at
all.** `soil_fertility.csv` has no state, district, date or provenance column.
Whether its distribution resembles Karnataka farmland is **unverifiable by
construction** — not merely unverified. A statistically valid model on an
unknown population is still an unknown model for our users, the same caution
already applied to the non-Karnataka land-unit conversions.

---

## 6. Yield prediction

`crop_yield.csv` (19,689 rows, 1997-2020) joined to `state_weather_data_1997_2020.csv`.

Evaluated on a **held-out-years** split, not a random one. The inherited script's
random split reported R-squared = 0.9501, which is memorisation of
state-by-crop-by-year panel cells rather than a generalisation estimate.

| | |
|---|---|
| **Metric** | MAE and R-squared on held-out years; plus a Karnataka-only slice reported separately |
| **Bar** | **Beat the per-(crop, state, season) median baseline on MAE by at least 10%**, and **R-squared at least 0.60** on held-out years |
| **Baseline** | Per-(crop, state, season) median from the training years — i.e. exactly what `ml/prep/clean_crop_yield.py` already computes |

**Why this framing.** The baseline is not a straw man: the repo already has a
working percentile-band lookup over this same data. If a gradient-boosted model
cannot beat a median lookup by a clear margin on unseen years, then it adds
complexity, a serving dependency and a failure mode in exchange for nothing, and
**the correct decision is to ship the lookup and drop the model.** 10% is the
margin at which the added machinery starts paying for itself.

R-squared at least 0.60 on held-out years is set far below the 0.95 the random
split reported, because that number was not real. Genuine temporal
generalisation on agricultural panel data is a materially harder problem.

**Karnataka slice.** Karnataka is the best-represented state (1,432 rows, all
five seeded crops present: rice 69, ragi 69, maize 69, cotton 36, sugarcane 21).
It is reported separately because a national average can hide poor performance
in the one region whose farmers actually use this app. **The Karnataka MAE must
also beat the Karnataka baseline** — a model that wins nationally while losing
locally does not ship.

**Output constraint, independent of metric.** `DATASETS_STATUS.md` §2.1
established that the `yield` column is not production divided by area
(disagrees in 69% of rows) and has no single unit across crops. The served
output is a percentile within that crop's own distribution. No response may
attach a unit to a yield value, and no absolute figure is presented to a
farmer, whatever the model scores.

---

## 7. Soil type from photo — two candidates, one bar

295 train / 73 test images, 4 classes. **Measured distribution is heavily
imbalanced:** train Alluvial 156, Red 60, Black 55, Cinder 24; test Alluvial 39,
Red 15, Black 13, **Cinder 6**.

Two candidates are trained and scored on the same untouched test set:
- **(a)** HSV histogram + texture into a RandomForest, tuned and depth-constrained
- **(b)** MobileNetV3 transfer learning + augmentation

| | |
|---|---|
| **Metric** | Overall accuracy, and per-class recall, on the 73-image test set |
| **Bar** | **Accuracy at least 0.80 AND per-class recall at least 0.60 for Alluvial, Black and Red** |
| **Baseline** | Majority class (Alluvial) = 0.534 accuracy |

**Why these numbers.** This feature is **additive to the existing region-based
`soilLookup.js`, never a replacement** — the farmer already gets a soil type
from their district. A photo model therefore has to be clearly better than the
default it is layered on, not merely better than chance; 0.80 against a 0.534
majority baseline is that margin.

**Cinder is deliberately excluded from the per-class bar.** Six test images give
a recall resolution of 0.167, so any threshold on it would be measuring noise
rather than the model. Cinder recall is reported, never barred. This is also
the class that `soil_to_crop_bridge.py` cannot map to the crop model's
vocabulary at all, so its practical value is limited regardless.

**Whichever candidate clears the bar and scores higher ships; if neither clears
it, neither ships** and the region-based lookup stands alone, which is the
current behaviour and is not a regression.

**Leakage check required before either number is trusted.** At 295 images,
near-duplicate frames spanning the train/test boundary can manufacture apparent
accuracy on their own. A duplicate check is run and its result recorded
alongside the metrics; if duplicates are found they are removed and the model
retrained, not noted and ignored.

---

## 8. Applies to every model

- Reported on a test fold used **once**, after tuning on a separate validation fold.
- Preprocessing fitted on training data only.
- No model output crosses the API boundary as a probability. Confidence is a
  categorical label (`ml/labels.py`), per `backend/plan/phase4-part2.txt` line 33.
- No model may self-promote to `verified`. That label means a human domain
  expert signed the guidance off; none of this has been reviewed by anyone.
- Provenance and licensing for every dataset here is unrecorded
  (`DATASETS_STATUS.md` §2.5), so everything ships with an unverified or
  provisional caveat regardless of metric.
- **Missing the bar means not shipping.** Not shipping with a warning label, not
  shipping behind a flag. The miss is recorded in `MODEL_RESULTS.md` with a
  cause category — data ceiling, technique, or wrong model family — so the next
  attempt does not blindly repeat this one.

---

## 9. Revisions

None. Any change to a bar above must be appended here with a date and the
finding that justified it.
