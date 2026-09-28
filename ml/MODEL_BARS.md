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

Any change to a bar above must be appended here with a date and the finding
that justified it.

### 2026-09-22 — new bar added: model 4b, crop-scoped disease Q&A retrieval

> *Restored 2026-09-23.* This entry was written on 2026-09-22 and was missing
> when the file was next opened; it had apparently been reverted with the rest
> of the file to its first committed version. It is restored with its original
> wording. Two things are added, both marked as such: this note, and the
> bracketed clarification in the first paragraph below. The inner heading
> "4b." has been demoted one level so later dated entries do not render as
> part of it.

**This does not change bar 4.** Model 4 was measured at recall@3 = 0.5705
against its bar of 0.70 and **failed**. It stays failed, and is recorded as
such in `MODEL_RESULTS.md`. Nothing below rehabilitates it.
*[Clarification added on restoration: 0.5705 was the development-holdout
figure available when this was written. The final held-out measurement
recorded in `MODEL_RESULTS.md` is 0.5447, which fails by a wider margin.]*

**What was learned.** Bar 4 was written for retrieval across the whole 88-pair
index. That is not a mode the app can actually invoke: a disease question
reaches the system through a scouting observation, which is logged against a
planting, which has a `crop_id`. There is no UI flow in which a farmer asks a
crop-less question. So bar 4 measured something we would never serve, and its
failure category is "the bar described the wrong serving mode" — not a data
ceiling and not a technique ceiling.

The right response is a separate model with its own bar, not a reinterpretation
of the old one. **Model 4b is a distinct model: "Disease Q&A retrieval
(crop-scoped)".** Its serving function requires a crop argument, so the mode
that failed above is impossible to invoke by construction.

#### 4b. Disease Q&A retrieval, crop-scoped

Same corpus and same index. The difference is that the candidate set is
restricted to the diseases recorded for the farmer's crop before ranking.

**The chance baseline is completely different and much higher.** The corpus has
exactly 8 diseases for each of its 11 crops. So scoped chance is:

- recall@1 = 1/8 = **0.125**
- recall@3 = 3/8 = **0.375**

against the unscoped 88-pair chance of 0.034. A scoped bar of 0.70 would sit
less than twice chance and would be a weaker requirement than bar 4 was, which
is exactly the trap to avoid.

| | |
|---|---|
| **Metric** | Recall@1 and recall@3 of the correct disease, held-out phrasings, candidates restricted to the queried crop |
| **Bar** | **recall@3 at least 0.75 AND recall@1 at least 0.55** |
| **Baseline** | Chance within a crop: recall@3 = 0.375, recall@1 = 0.125 |

**Why 0.75, derived independently of the measured value.** The alternative to
retrieval here is not "show nothing" — the app knows the crop, so it could
simply list all 8 of that crop's diseases and let the farmer read them. That
fallback has recall 1.0 by construction. Retrieval's only job is to save
reading effort by cutting 8 candidates to 3.

So the question is: how reliable must a 3-of-8 shortlist be before showing it
is better than showing all 8? Discarding 5 candidates is only worth it if the
farmer rarely needs them. At recall@3 = 0.75 a farmer who acts on the shortlist
is wrong one time in four. That is already high for advice someone may spray
pesticide on, and it is set there — rather than higher — only on the condition
below. Below 0.75 the shortlist misleads more often than it saves effort, and
listing all 8 is the better product.

**Shipping condition attached to this bar:** the UI must keep a visible "see all
diseases for this crop" path. The 0.75 threshold is justified *only* while that
escape hatch exists. If the shortlist becomes the only way to reach a diagnosis,
this bar is too low and must be raised before shipping.

recall@1 at least 0.55 is barred separately because the first result is what a
farmer anchors on, and 0.55 is comfortably above the 0.125 scoped chance while
acknowledging that several of these diseases share genuine symptoms.

**Measured corpus property that caps this.** 68 distinct question strings (137
rows, 6.1% of the corpus) are assigned to more than one (crop, disease) pair —
for example identical boll-and-fibre text labelled both cotton and sugarcane.
These are not assumed to be mislabellings with a knowable correct answer; some
are genuine shared symptomatology. They are not deleted. Instead, a query
matching one of them surfaces **both** pairs together, explicitly framed as a
symptom shared across crops, rather than silently resolving to one.

**Output constraint.** Retrieval returns structured keys — matched disease,
remedy identifiers, available languages — never rendered prose. The same rule
applied to fertilizer advice applies here: English strings baked into a model
response cannot be localised, and this app ships 10 locales against a corpus
carrying 3.

### 2026-09-23 — new model 10: leaf condition from photo, sugarcane

**Written before the model was trained.** Disease-from-photo was parked on
2026-09-22 because PlantDoc contains none of rice, ragi, cotton or sugarcane
(`PARKED_MODELS.md` §1). A crop-specific sugarcane dataset has since been
supplied, with a genuine healthy class — the thing PlantDoc's maize-only residue
lacked:

- **Sugarcane — Sugarcane Leaf Image Dataset**: 6,748 images, 11 classes
  (9 disease folders, plus Dried Leaves 343 and Healthy Leaves 430).

This is a new, separate model, not a resumption of the parked one.

**Not every class is a disease.** Dried leaves and banded chlorosis are
abiotic. The model is therefore named "leaf condition", and each class carries
a category (`healthy`, `disease`, `pest_damage`, `abiotic`, `unclassified`) so
the app does not recommend a fungicide for a condition no fungicide treats.
That category mapping is label metadata written from the class names, not
agronomist-reviewed, and ships marked unverified.

**One model per crop, crop required.** Same reasoning as bar 4b: the app always
knows the crop, because a photo arrives through a planting. A combined model
would have to identify the crop first, a problem the app never needs solved.

#### Preconditions — no metric is trusted until these hold

1. **Near-duplicate check, including flips and rotations.** The soil photo set
   turned out 19% duplicated across its shipped split (`DATASETS_STATUS.md`
   §2.7). Every image is hashed under all 8 flips and rotations, and all splits
   are made by duplicate group, so copies cannot straddle a fold boundary.
2. **Split 70/15/15, stratified, by group.** Validation selects the
   architecture, epochs and fine-tuning depth; test is read once.

#### Model 10 bar

| | |
|---|---|
| **Metric** | Macro-F1; recall per class; precision of the healthy class — all on the test fold |
| **Bar** | **Macro-F1 at least 0.85 AND every class recall at least 0.70 AND healthy precision at least 0.90** |
| **Baseline** | Majority class: Brown Spot = 0.255 accuracy |

**Why this is the strictest bar in the file.** This is the only model here
whose output directly prompts a farmer to spray, or not to. When this was
parked, the direction was to set this bar hardest, at a level one would be
comfortable with if a farmer acted on a wrong answer. Each criterion guards a
different way of being wrong:

- **Healthy precision at least 0.90** guards the most dangerous error: telling a
  farmer a diseased plant is fine. The farmer acts on "looks healthy" by doing
  nothing, and the disease spreads. At 0.90, at most one in ten "healthy"
  verdicts hides a problem. Healthy *recall* is not barred as tightly; calling
  a healthy leaf diseased costs a second look, not a crop.
- **Every class recall at least 0.70.** A condition the model catches less than
  70% of the time is missed often enough that a farmer cannot rely on it for
  that condition, and a macro average can hide one badly served class.
- **Macro-F1 at least 0.85** is the headline. Macro, not accuracy, because the
  classes are imbalanced (Brown Spot 1,722 vs Pokkah Boeng 297) and accuracy
  would reward ignoring the small ones.

**Ships provisional regardless of metric.** Test images come from the same
source and capture conditions as training images. A farmer's phone photo in a
Karnataka field is a different distribution — lighting, background, camera,
framing — and in-source test accuracy overstates field accuracy by an unknown
margin. The model also cannot recognise a wrong-crop or non-leaf photo; it will
name one of its classes regardless. The dataset's labels have not been reviewed
by an agronomist here.

### 2026-09-23 (later) — model 10: split by capture session, not by photo

**The bar is unchanged. The evaluation protocol is made stricter.** Written
after a first training run and before the retraining that will be reported.

**What was found.** The model first trained and tested on a split that grouped
exact duplicates, per precondition 1 above. It cleared every bar — macro-F1
0.9807. A scene-level audit (`ml/training/audit_leaf_scene_leakage.py`) then
showed that the duplicate check had not been enough:

- Two different training images of the same class have a median similarity of
  0.652 (untuned ImageNet features). A test image's most similar training image
  has a median of **0.980**, and for **78%** of test images that nearest
  neighbour is within three filenames in the same folder (`image078` beside
  `image080`).
- Every image carries an EXIF capture time, and it shows why. Each class was
  photographed in continuous streams: at a 10-second gap, classes are only
  **8 to 51 sessions**. Consecutive frames of one stream are largely the same
  leaf, light and moment.

So the first run's test fold mostly asked "can the model recognise a moment it
has already seen?", not "does it work on a new photo?". Those numbers are
recorded in `MODEL_RESULTS.md` as the leaky measurement and are **not** the
result.

**Revised preconditions 1 and 2, replacing the originals for model 10:**

- **Group by capture session and by duplicate.** Within each class, images
  whose EXIF capture times are 10 seconds or less apart form one session. Any
  two images in the same session or in the same pixel-verified duplicate
  cluster are in the same group. The split is made by group. 10 seconds is the
  finest defensible unit: coarser thresholds collapse several classes into one
  or two sessions, leaving nothing to split.
- **Split 60/20/20 by group**, stratified by class (`StratifiedGroupKFold`).
  Moving from 70/15/15 puts more sessions into the test fold; with as few as 8
  sessions in a class, 15% would often mean a single session.

**What this does to the reliability of the numbers.** The test fold now
measures performance on capture sessions the model has never seen, which is
the closest proxy this dataset allows to a new farmer's photo. It is also far
thinner than its image count suggests: a class with 8 sessions contributes one
or two to the test fold. Per-class recall is therefore reported with the number
of test *sessions* beside it, and a pass on one or two sessions is weak
evidence, however many images those sessions contain.

The bar stays where it was written. It is not lowered to accommodate the
harder evaluation.

### 2026-09-23 — new model 11: insect pest detection from photo (YOLOv8)

**Written before the model was trained.** Dataset: Roboflow RF100 "insects" v2
(YOLOv8 export, **CC BY 4.0** — the first dataset in this repo with a recorded
licence). 995 images, 10 classes, shipped split 696 / 199 / 100.

**What the data actually is.** Every image is 224x224 with a median of one
insect, cropped tight. In practice it is an identification dataset in
detection format. It does not teach the model to *find* a small insect in a
cluttered field photo, and it contains no insect-free images, so false
detections on empty scenes are untested.

**Relevance.** Eight of the ten classes are pests of the app's crops: six rice
pests (rice gall midge, rice leaf roller, rice leafhopper, rice water weevil,
white-backed planthopper, yellow rice borer — the stem borer behind
`RICE_STEM_BORER_SCOUT`), army worm (maize, rice) and red spider mite (cotton).
Legume blister beetle and wheat phloeothrips attack no seeded crop. They are
trained on, because they are real negatives for the other eight, but are
reported rather than barred.

*Note added 2026-09-26, after the test read:* wheat became an app crop, so
wheat phloeothrips is now app-relevant. Its measured recall (0.8750) clears the
0.70 app-class criterion, so the verdict is unchanged (`MODEL_RESULTS.md` §11).

#### Preconditions

1. **Cross-split duplicates removed.** A pixel-verified check found 16 pairs of
   the same photograph in two splits (11 train/valid, 4 train/test, 1
   valid/test), none with conflicting labels. Copies are removed from train and
   valid; test is kept exactly as shipped.
2. **The shipped split is kept.** The images carry no EXIF capture time, so the
   session split used for model 10 is not possible. Roboflow's source
   filenames do not identify source images either: `100_jpg` appears under five
   different classes, because merged class folders each had their own
   `100.jpg`.
3. Model size (YOLOv8n vs YOLOv8s) is chosen on valid; test is read once.

#### Model 11 bar

| | |
|---|---|
| **Metric** | Identification: the class of the highest-confidence detection in each test image, compared with its label (no detection counts as wrong). Also mAP@0.5. |
| **Bar** | **Identification macro-F1 at least 0.85, AND recall at least 0.70 for each of the 8 app-relevant classes, AND mAP@0.5 at least 0.70** |
| **Baseline** | Always naming the most common class: identification accuracy about 0.17 (army worm, 17 of 100 test images) |

**Why these criteria.** Naming the pest decides the control measure, and
control measures are pest-specific; spraying for leaf roller does nothing for
planthopper. That is the same kind of action as a leaf-disease verdict, so
identification gets the same macro-F1 and per-class recall bars as model 10.
There is no healthy-precision criterion because there is no "no pest" class to
measure. mAP@0.5 is barred at 0.70 as a check that the boxes are real,
so that detection-based uses such as counting insects on a trap photo are not
built on boxes the model never learned to place.

**Measurement resolution.** Test instances per class run 5 to 17. Yellow rice
borer has 5, so a 0.70 recall bar effectively means 4 of 5 (0.80). These
per-class numbers are coarse and are reported with their counts.

**Ships provisional regardless.** Web-sourced tight crops are a different
distribution from a farmer's field photo, and nothing here has been reviewed by
an entomologist.

### 2026-09-23 — new model 12: rice disease type from photo (conditional)

**Written before the model was trained**, after the user chose on 2026-09-23 to
train rice as a conditional model rather than park it.

**Dataset:** `datasets/rice_leafs_disease`, 5,932 images in four classes
(Bacterial blight 1,584, Blast 1,440, Brown spot 1,600, Tungro 1,308). **There is
no healthy class.**

**This is a different and narrower model than 10 and 11.** It answers only
*"given that this rice leaf shows a symptom, which of these four diseases does
it most resemble?"* It is never asked whether a leaf is healthy, because it
cannot answer that. Every rice leaf shown to it, healthy or yellowed by
nitrogen deficiency, will be named as one of the four diseases.

**Serving contract, part of this bar:**

- Invoked only with an explicit `symptom_reported=True`, set by the scouting
  flow after the farmer has reported a problem. Without it the call is refused.
- The response always offers "none of these / something else" as an answer
  for the UI to show, and never says "healthy".
- The most dangerous error for model 10, a diseased leaf called healthy,
  cannot happen here. Its mirror image, a healthy or otherwise-affected leaf
  called diseased, **cannot be measured with this data at all**. That risk is
  managed by the contract above, not by the metric.

#### Preconditions

1. **Duplicate groups, then similarity groups.** The flip/rotation hash with
   pixel verification reduces 5,932 images to **1,094 distinct photos**: the set
   is about 5x pre-augmented. That check cannot see brightened, zoomed or
   recropped copies, and those are plentiful. After it, a photo's nearest
   neighbour (untuned ImageNet MobileNetV3-Large features) sits at median
   similarity 0.966, against 0.623 for two unrelated leaves of the same class,
   and 242 photos have a neighbour at 0.99 or more.
2. **So photos with similarity of at least 0.93 are grouped** (connected
   components). 0.93 sits above the 99th percentile of unrelated same-class
   pairs (0.912). Measured effect: 547 independent groups; the largest holds 17
   photos (no runaway chaining); and **no pair above 0.93 crosses a disease
   label** — good evidence these are copies, not lookalike leaves.
3. **No capture-session split is possible.** Only about 7% of images carry an
   EXIF time. Burst-shot leakage of the kind found in model 10 is
   therefore not ruled out, beyond what similarity grouping catches.
4. **Split 60/20/20 by group** (`StratifiedGroupKFold`); test is read once.

#### Model 12 bar

| | |
|---|---|
| **Metric** | Macro-F1 and recall per class on the test fold |
| **Bar** | **Macro-F1 at least 0.85 AND every class recall at least 0.70** |
| **Baseline** | Majority class (Brown spot) accuracy, computed on the test fold |

The same macro-F1 and recall bars as model 10, for the same reason:
the verdict decides what gets sprayed. The healthy-precision criterion is
omitted only because it cannot be computed without a healthy class. That is a
limit of the data, not a relaxation, and the serving contract carries the
weight instead.

**Ships provisional regardless.** Source and capture conditions are
unrecorded, most images are 300x300, and nothing here has been reviewed by an
agronomist.

### 2026-09-23 (later) — model 12: similarity grouping corrected to compare every image

**The bar and the 0.93 threshold are unchanged.** This corrects the
implementation of model 12's precondition 2, which did not do what that
precondition says.

**What went wrong.** The grouping compared one representative photo per
duplicate cluster. A cluster's first member is stored in an arbitrary
orientation, and ImageNet features are not rotation-invariant, so a brightened
copy stored rotated looked unlike its original and was never grouped with it. A
first training run on that split scored test macro-F1 0.9655. The scene-leakage
audit then showed **223 of 1,186 test images (18.8%) had a training image at
similarity 0.97 or more** — exactly what precondition 2 was written to prevent.
That run is recorded in `MODEL_RESULTS.md` as a leaky measurement and is not the
result.

**Correction.** Every image is embedded and compared, so matching orientations
meet. At the same 0.93 threshold the data forms **302 independent groups**
(Bacterial blight 70, Blast 81, Brown spot 99, Tungro 52), and **still no
grouped pair crosses a disease label**. The earlier figures in precondition 2
(547 groups, largest 17 photos) came from the faulty comparison; the largest
group is now 160 images. That is chaining of related copies, not of unrelated
leaves, as the absence of any cross-label link shows. Each class keeps at least
52 groups, enough for a stratified 60/20/20 split.

### 2026-09-24 — new model 13: pearl millet disease type from photo (conditional)

**Written before the model was trained.** Dataset: `datasets/millets_dataset`,
supplied 2026-09-24. It has three folders: blast 2,926, rust 2,059 and
Healthy 1,326.

**Crop: pearl millet (bajra), not ragi.** The leaves are broad with a clear
midrib, and blast and rust are the two classic pearl millet leaf diseases. The
user confirmed this reading on 2026-09-24. Pearl millet is **not a seeded app
crop**. The model serves `crop_key("pearl millet")` (which `bajra` also maps
to), never ragi, and every response carries `is_seeded_crop: False`. The
disease Q&A corpus has no millet entries, so no class is linked to remedies.

**Healthy is excluded (user decision, 2026-09-24).** The Healthy folder is a
different source from blast and rust:

| | Blast and rust | Healthy |
|---|---|---|
| Image size | 256px | 640px |
| Framing | one leaf across a background | close, full-frame leaves |
| Origin | camera `DSC_####` shots | phone and WhatsApp photos from a Roboflow export |

A model trained on all three could separate healthy from diseased by source.
Its healthy precision would look excellent and mean nothing, and no split can
remove that confound. This is therefore a **conditional "which disease?"
model**, with the same serving contract as model 12 (rice):

- it is called only with `symptom_reported=True`;
- it always offers "none of these";
- it never says "healthy".

#### Preconditions — no metric is trusted until these hold

1. **Pixel-verified, flip- and rotation-invariant duplicate groups**, as for
   every leaf model. 4,985 files are 4,669 distinct.
2. **Group by shot.** Each `DSC_####` number is one photograph, stored as up to
   four crops (`normal0` to `normal3`). All crops of a shot are one group.
   After this step, 2,002 distinct shots remain.
3. **Group consecutive shots into sessions.** There is no EXIF time. Shot
   numbers run sequentially (1-999 blast, 1-1003 rust), and consecutive shots
   are bursts of one leaf:
   - adjacent shots have median similarity **0.95** (untuned ImageNet
     features);
   - shots more than 20 apart have **0.69**.

   Shot *n* and *n+1* are linked when their representatives reach 0.85, which
   96% of adjacent pairs do. That gives **84 sessions, 45 blast and 39 rust**.
   Only adjacent shots are linked. A global similarity threshold would chain
   everything together, because about 1% of distant pairs also exceed 0.93. No
   blast shot and rust shot reach 0.90 similarity, which suggests the classes
   are not copies of each other.
4. **Split 60/20/20 by session**, `StratifiedGroupKFold`: train 2,990, val 998,
   test 997, with **8 test sessions per class**. Selection is on validation,
   and test is read once. After training, the scene-leakage audit is run and
   reported.

#### Model 13 bar

| | |
|---|---|
| **Metric** | Macro-F1 and recall per class on the test fold |
| **Bar** | **Macro-F1 at least 0.85 AND every class recall at least 0.70** |
| **Baseline** | Majority class (blast) accuracy, computed on the test fold |

This is the same bar as models 10 and 12, for the same reason: the verdict
decides what gets sprayed. Healthy precision is omitted only because the
healthy class was excluded.

**Reliability limits, stated before the result.**

- 8 test sessions per class is thin evidence, however many images they hold.
- Non-adjacent revisits of the same leaf are not ruled out by the grouping; the
  post-training audit measures what remains.
- Source and capture conditions are unrecorded.
- **Ships provisional regardless.**

### 2026-09-24 — new model 14: wheat canopy segmentation (heading and cover)

**Written before the model was trained.** Dataset: `datasets/wheat_dataset`,
GlobalWheat **GWFSS v1.0** (Global Wheat Full Semantic Segmentation). The
download is partial: 438 of 1,096 images (40%). Images are 512x512 top-down
canopy photos, each with a pixel mask labelling background, head, stem and
leaf. The shipped split is 350 train and 88 val. Trained at the user's request,
2026-09-24.

**What it is for.** This is not a disease model. Pixel labels support two
farmer-facing outputs:

- **heading detected**: are wheat heads visible? This is a growth-stage signal
  for timing irrigation and sprays.
- **canopy cover**: the plant share of the image, a coarse vigour signal.

Wheat is **not a seeded app crop**. Responses carry `is_seeded_crop: False`,
and nothing in the app reaches the model until wheat is added.

#### Preconditions

1. **The shipped val set (88) is the test fold**, read once and never altered.
   Validation is carved from the 350 train images (80/20).
2. **Near-copy control.** There is no site or session metadata and no EXIF, so
   similarity is the only signal (untuned ImageNet features):
   - Unrelated train pairs have median similarity 0.48 (p99 0.82).
   - Val-to-train nearest neighbours: 0 at >= 0.97, and 4 of 88 at >= 0.93.
   - Train images at >= 0.93 are grouped before the train/validation split.
   - Train images at >= 0.93 to any test image are **removed from train**, so
     the test fold stays as shipped.
3. **Fixed rules, not tuned on test.** An image counts as "headed" when heads
   cover at least 0.5% of its pixels. The same rule applies to the ground truth
   and to the prediction. Canopy cover = 1 - background share.

#### Model 14 bar

| | |
|---|---|
| **Metric** | On the test fold: head IoU; plant-vs-background IoU; canopy-cover MAE per image; heading balanced accuracy per image |
| **Bar** | **head IoU >= 0.60 AND plant IoU >= 0.80 AND cover MAE <= 0.05 AND cover MAE <= 50% of baseline AND heading balanced accuracy >= 0.85** |
| **Baseline** | Cover: predict the train mean for every image. Heading: always "headed" (balanced accuracy 0.50). |

**Why these numbers:**

- **Cover MAE <= 0.05.** A cover figure that is wrong by more than 5 percentage
  points cannot separate a thin stand from a normal one. It must also halve the
  constant-guess error, so a flat prediction cannot pass.
- **Plant IoU >= 0.80.** Cover is only as good as the plant/background
  boundary.
- **Head IoU >= 0.60.** Heading detection rests on head pixels; below this,
  small early heads are lost.
- **Heading balanced accuracy >= 0.85.** Balanced, because only 33 of 88 test
  images fall under the 0.5% head rule. Plain accuracy would reward always
  saying "headed".
- **Leaf, stem and mean IoU are reported but not barred.** Stems are thin and
  3% of pixels, and no output depends on them.

**Ships provisional regardless.**

- The data is a 40% sample of a global dataset.
- Its sites and cameras are unknown relative to Indian fields.
- It covers only top-down canopy photos, and a farmer's side-on phone photo is
  outside what was measured.

### 2026-09-24 — model 14b: wheat heading detection only

**Written after model 14's test read, at the user's request, and declared as
such.** Model 14 does not ship: its joint bar failed on canopy-cover MAE (0.0756
against 0.05). Model 14b is a narrower output of the **same trained model**,
serving `heading_detected` only. Canopy cover is not served in any form.

**Bar.** These are the model 14 criteria that heading depends on, with the
thresholds unchanged:

- heading balanced accuracy >= 0.85, with the same fixed rule: "headed" means
  heads cover at least 0.5% of the image;
- head IoU >= 0.60, so a pass cannot rest on detecting stray pixels.

**Declared bias.** This output was chosen after seeing that heading passed
(0.9848) while cover failed. No fresh test data exists, so the bar is applied to
the existing single test read without retraining. That is a selection on the
test fold. The measurement itself is not optimistic, but the decision to ship
this output was informed by it.

A genuinely blind check is available: the 658 GWFSS images not yet downloaded.
Evaluating heading on those at this bar would remove the bias, and it is the
recommended next step.

**Serving contract.** The response carries `heading_detected` and caveats only.
No cover value, band or mask. `is_seeded_crop: False`.

**Ships provisional regardless**, for the same reasons as model 14.

### 2026-09-24 — new model 15: soybean seed yield from plant traits (all features)

**Written before the model was trained.** Dataset:
`datasets/soybean_dataset/Advanced Soybean Agricultural Dataset.csv`, supplied
2026-09-24. Trained at the user's request with all features, after they were
told the findings below.

**What the data is.**

- **108 unique rows, not 55,450.** Every row appears about 500 times. The
  duplicates are removed before anything else. Training on them would put
  copies of a plot on both sides of every split.
- **One factorial field experiment.** The `Parameters` code `C#S#G#` means 2
  growing conditions x 3 treatments x 6 genotypes, 35 combinations present,
  with 3 replicates in `Random`. The codes are undocumented, so the genotypes
  and treatments are unnamed.
- **Target:** `Seed Yield per Unit Area (SYUA)`. Its unit is not stated.
- **Features:** all 12 other traits, plus C, S and G as categorical.
  - Several traits are **lab-only**: chlorophyll a and b, sugars, protein,
    relative water content.
  - Several are **post-harvest**: pods, seeds per pod, weight of 300 seeds,
    biological weight.
  - Yield is close to pods x seeds per pod x seed weight, so a high score here
    is partly arithmetic, not prediction.
- **Soybean is not a seeded app crop.** No farmer in the app can supply these
  inputs. The model is therefore **not served** even if it clears the bar, until
  an app use is defined.

#### Preconditions

1. De-duplicate to 108 rows.
2. **Split by treatment code** (`Parameters`), so that replicate plots of one
   treatment are never on both sides. Hold out 20% of treatments as the test
   fold, read once. Choose the model family on the remaining treatments with
   grouped 4-fold cross-validation.
3. Baseline: predict the training mean.

#### Model 15 bar

| | |
|---|---|
| **Metric** | On the test fold: R-squared, and MAE relative to the mean baseline |
| **Bar** | **R-squared >= 0.70 AND MAE at least 30% below the mean-baseline MAE** |
| **Baseline** | Training-mean prediction |

**Why stricter than the yield model (model 6, R-squared >= 0.60, MAE 10% below
baseline).** Harvest components nearly determine yield, so clearing a lower bar
would say almost nothing. The bar is still not a claim of usefulness: with
about 22 test rows from 7 treatments of one trial, a pass means "fits this
experiment", nothing more.

### 2026-09-24 — new model 16: sugarcane yield from the synthetic farm CSV

**Written before the model was trained.** Dataset:
`datasets/sugarcane_dataset/FINAL_SUGARCANE_DATASET.csv`: 3,000 rows, 81
columns, one district (Haridwar), 2018-2024. Trained at the user's request
after the evidence below was shown.

**The data is synthetic.** The evidence, measured 2026-09-24:

- **Monthly rainfall is about 1,400 mm in every month**, December included.
- **Sand + silt + clay ranges from 13.5% to 136%**; it should sum to 100.
- **Planting and harvest dates contradict `Crop_Duration_Days`.** For example,
  104 days between the dates against a stated 255, or 3.4 years against 288.
- **Categories are near-perfectly uniform.**
- **Missing values are injected** at about 4% in every column.
- **Yield follows a few rules:**
  - nitrogen, correlation 0.47;
  - potassium;
  - a step in disease severity (low 351, medium 293, high 195 q/acre).
  
  Variety, soil type, irrigation method, season and growth stage have no
  effect.

**Consequence: never served, whatever the score.** A pass measures how well
the model recovers the generator's formula, not anything about sugarcane.
Sugarcane is a seeded app crop, so serving this would give farmers confident
advice built on invented rules, for example that variety and irrigation do not
matter. The artifact records `served: False` and no serving module is written.
Serving would need an explicit, separate decision.

#### Preconditions

1. **Drop what carries no information or identifies a row:**
   - constant columns (State, District, Region, Sugar_Mill);
   - the plot ID (`Khasra_No`);
   - the raw date strings.
2. **Held-out years, as for model 6:** train on 2018-2022 and rows with no
   year; validate on 2023; test on 2024, read once. Model family is chosen on
   validation.
3. **Missing values handled inside the pipeline**, fitted on train only.

#### Model 16 bar

| | |
|---|---|
| **Metric** | On the 2024 test fold: R-squared; MAE against a training-mean baseline |
| **Bar** | **R-squared >= 0.60 AND MAE at least 10% below baseline**: model 6's yield thresholds |
| **Baseline** | Training-mean yield |

### 2026-09-24 — new model 17: tobacco leaf lesion segmentation (severity)

**Written before the model was trained.** Dataset: `datasets/tobacco_dataset`,
a curated 40% subset of Kaggle "Dataset for Tobacco Leaf Disease Segmentation".
It has 1,400 800x800 PNG tiles with binary masks (0 background/healthy, 1
lesion). Lesions average about 2% of pixels. Tobacco is **not a seeded app
crop**, so responses carry `is_seeded_crop: False`.

**What it is for.** The masks do not name a disease, so the only output is
**severity**: the share of the leaf surface covered by lesions. Severity is what
spray thresholds are written against.

#### What the data is, measured 2026-09-24

- **Real tiles: 320**, all in `data1/`.
  - They are cut from **84 photos**, 1 to 12 tiles each; the photo is
    `IMG_YYYYMMDD_HHMMSS` in the file name.
  - They were taken on 14-15 October 2023.
  - **34 photos have tiles in both shipped splits**, so the shipped split leaks.
- **Augmented tiles: 1,080 (77%)**, with no link to their source.
  - The 540 in `data1/` are augmentations of the real tiles: nearest real
    tile at median similarity 0.90, against 0.66 between tiles of different
    photos (p99 0.84).
  - The 540 in `data2/` are augmentations of originals that **are not in the
    dataset**: nearest real tile 0.72, but 0.95 to each other.

#### Preconditions

1. **Evaluate on real tiles only.** The shipped split is discarded. Real tiles
   are grouped by **capture session**: photos 10 seconds or less apart,
   giving 56 sessions. Sessions are split 60/20/20 into train, validation and
   test. Validation and test contain **real tiles only**. Test is read once.
2. **Augmented tiles are training data only, never evaluation data.**
   - A `data1/` augmented tile joins the session of its most similar real tile
     when that similarity is >= 0.84 (the p99 of unrelated real pairs).
   - If that session is in validation or test, the tile is **dropped**.
   - An unlinked `data1/` tile within 0.80 of any validation or test tile is
     also dropped.
   - `data2/` tiles have no source here, so they go to training.
3. After the test read, the scene-leakage check is repeated: the nearest
   training tile of every test tile.

#### Model 17 bar

| | |
|---|---|
| **Metric** | On real test tiles: lesion IoU (pixels pooled); per-tile lesion-share MAE |
| **Bar** | **lesion IoU >= 0.50 AND lesion-share MAE at most 50% of the baseline's** |
| **Baseline** | Predict the training-mean lesion share for every tile |

**Why these numbers.**

- **Lesion IoU of 0.50.** Lesions are small and irregular; below 0.50 the
  predicted spots are not the real spots, and a severity figure built on them
  would be coincidence.
- **Halving the baseline error.** Severity must track each leaf, not the
  average. Halving the constant guess's error is the minimum for the figure to
  separate a clean leaf from a badly spotted one.

**Ships provisional regardless.**

- The data is two days of photos from one source.
- The disease is not named.
- The images are close-up tiles, not whole leaves.

### 2026-09-24 — new model 18: mandi price, 13 weeks ahead (Karnataka), plus seasonal outlook

**Written before anything was trained.** This unparks the market-price model
(`PARKED_MODELS.md`), which was blocked on the lack of a time series. Dataset:
`datasets/historical_price_dataset`, from Agmarknet/data.gov.in daily prices.

- It has 8.87 million market-day rows, continuous from **2023-01-01 to
  2026-09-24**. There are also 13 isolated days of 2020, which are **not used**.
- Prices are in Rs/quintal: minimum, maximum and modal per market,
  commodity, variety and grade.
- The yearly files equal the daily files, so the yearly ones are used.

**User decisions (2026-09-24):**

- **Output:** both a seasonal outlook and a forecast.
- **Level:** weekly, per Karnataka district, with a state fallback.
- **Horizon:** "harvest time" defined as **13 weeks ahead, rolling**.
- **Crops:** paddy (common), rice, ragi, maize, cotton, jaggery (as the
  sugarcane proxy), and the field crops wheat, bajra, jowar, soyabean, arhar
  (tur), groundnut and bengal gram.
- **Not covered:** sugarcane itself. It is sold to mills at the FRP and has no
  mandi series.

#### Data preconditions (fixed now)

1. **Clean.** Remove:
   - duplicate market-day-commodity-variety-grade rows (168,502);
   - rows with min > max, or with modal outside [min, max];
   - rows whose modal differs more than 3x (either way) from that commodity's
     all-India median in the same week. This catches the unit and typo errors,
     such as rice at Rs 61,899 against a median of Rs 3,250.
2. **Weekly series.** Take the median modal price across a district's markets
   in each week. Also build a Karnataka series (the median across all its
   markets).
3. **District rule.**
   - A district-crop series is modelled only if it has a price in **at least
     40% of the weeks in the training period**.
   - Otherwise the crop uses the Karnataka series, and the response says so.
4. **Time split, by the week being forecast** (the target week):
   - test = the last 26 target weeks (to 2026-09), read once;
   - validation = the 26 before that;
   - training = everything earlier.
   
   Features use only prices known at the forecast week.

#### Model 18 bar (the forecast), applied **per crop**

| | |
|---|---|
| **Metric** | On test target weeks: MAE of log price, which is roughly % error; direction accuracy |
| **Bar, per crop** | **MAE at least 10% below persistence AND no worse than seasonal-naive** |
| **Bar, pooled** | **Direction accuracy >= 0.60** on test weeks where the true 13-week move is at least 5%. If this fails, no crop ships. |
| **Baselines** | *Persistence*: the price in 13 weeks equals today's. *Seasonal-naive*: today's price times last year's change over the same 13 weeks. |

Only crops that pass ship; the rest fall back to the seasonal outlook.

**Why these baselines.** Persistence is notoriously hard to beat for commodity
prices. A forecast that cannot beat it by a clear margin would tell a farmer to
hold or sell on noise. Seasonal-naive captures the harvest-glut pattern a
farmer already knows; a model that cannot match it adds nothing. Direction
matters because the decision is "hold or sell". It is measured only on moves
of 5% or more, since smaller moves are within mandi day-to-day noise.

**Honest limits, stated before the result.**

- **The test fold is 26 weeks**, about half a season, so seasonal effects are
  seen once.
- **Training covers about two and a half years.**
- **Weekly target weeks overlap** (13-week horizons), so test points are
  correlated and the effective sample is smaller than the row count.

#### Seasonal outlook (18s): descriptive, not a forecast

For each crop, per district when the district rule holds (else Karnataka):
the median and interquartile range of the weekly modal price for each calendar
month. It is computed from training plus validation weeks only. A month is
reported only if at least 2 different years contribute to it.

It carries no accuracy bar, because it claims only "prices in this month have
typically been in this range". Its coverage on the test weeks (the share of
actual prices inside the IQR, 50% if calibrated) is reported for information.
It ships as the always-available fallback, labelled as historical ranges from
2023-2026.

### 2026-09-24 — new model 19: vegetable variety/size classifier (14 folders)

**Written before the model was trained.** Dataset: `datasets/Vegetables Image
Dataset for Machine Applications`, harvested produce from Pune (see
`DATASETS_STATUS.md` §2.16).

- The published description says 13 classes. The folders give 14: chilli has
  three varieties.
- The user asked on 2026-09-24 for the full-class model. They stated that
  same-named images differ.

**Measured before writing this.** Of the 6,418 file names that appear in more
than one folder:

- **6,331 are byte-identical copies**: the same image under two or more labels.
- **87 genuinely differ.**

The user's statement holds for those 87 and not for the rest.

#### Preconditions

1. **One image, one label.** The standard leaf pipeline applies:
   - flip- and rotation-invariant hash, then pixel verification;
   - a duplicate group whose members carry **more than one label is dropped**,
     since nothing says which label is right;
   - genuinely different images keep their folder label, whatever their name.
2. **Group by source photo and capture burst.**
   - These files have no EXIF. The capture time is parsed from the file name
     (`IMG_YYYYMMDD_HHMMSS`), so every augmented copy of a photo shares a time.
   - Within a class, images 10 seconds or less apart form one session.
   - The split is 60/20/20 by session, stratified. Selection is on validation,
     and test is read once.
3. **No class disappears silently.** A class with too few sessions left to
   appear in the test fold (fewer than 5 sessions after conflict removal) is
   **excluded from training and counted as failing its recall criterion**.

#### Model 19 bar

| | |
|---|---|
| **Metric** | Macro-F1 and recall per class on the test fold |
| **Bar** | **Macro-F1 >= 0.85 AND every one of the 14 classes has recall >= 0.70.** A class that cannot be measured fails. |
| **Baseline** | Majority-class accuracy on the test fold |

**Why the same bar as the leaf models.** The dataset's stated purpose is
grading produce by visual quality, which sets price. A variety or size grade
that is wrong more than 30% of the time misprices produce.

**Not served regardless of verdict** until a use is defined. None of these
vegetables is an app crop, and the app has no produce-grading flow.

### 2026-09-25 — model 5b: soil fertility class, retried on new labelled soil tests

**Written before the model was trained.** Model 5 failed on
`soil_fertility.csv`, which had 39 high-fertility rows and no geography. New
files were supplied on 2026-09-25 in `datasets/soil_dataset/`:

- `karnataka_soil_fertility_dataset.csv`: 1,831 rows, 1,500 fields, 12
  districts.
- `pan_india_soil_fertility_dataset.csv`: 3,805 rows, 10 states, 819 of them
  in Karnataka.
- Two `*_ml_ready.csv` files, which are column subsets of those rows.

The two full files share no sample, field or nutrient row. Combined, they give
**5,636 samples**. Classes: Low 1,982, Medium 2,088, High 1,566.

**Provenance: unverified.** The user states the data is real and declined to
name the source (2026-09-25). Recorded against it:

- The files were created minutes after a message specifying this exact column
  set.
- Nitrogen and organic carbon correlate at 0.90, tighter than typical soils.
- A few rows share exact P, Fe and Mn values across states.

Recorded for it:

- The coordinates fall inside their stated districts.
- Fields are re-tested across 2022-2024.

**The label is a formula of the inputs.** `Fertility_Class` is an exact cut
of `Fertility_Index` (Low < 1.70 <= Medium < 2.35 <= High, identically in both
files), and the index is computed from the nutrients. A shallow tree recovers
the class at about 0.93 grouped CV accuracy. A pass therefore means "the
model reproduces this lab's rating scheme". `Fertility_Index` is **excluded
from the features**: it is the label in numeric form.

The old `soil_fertility.csv` is **not merged**. Its 0/1/2 labels follow a
different, undocumented scheme; for example, class 2 exists although nitrogen
never reaches the Soil Health Card "high" level.

#### Preconditions

1. **Features:** the 12 nutrients only (N, P, K, pH, EC, OC, S, Zn, Fe, Cu, Mn,
   B), which is what a soil-test card gives.
2. **Split 60/20/20 by `Field_ID`** (StratifiedGroupKFold), so repeat tests of
   one field never straddle a fold. Model family is chosen on validation, and
   test is read once.
3. A **Karnataka slice** of the test fold is reported and barred, and a
   **held-out-district** figure is reported: each Karnataka district left out
   in turn, trained on the rest, with no bar.

#### Model 5b bar (model 5's thresholds, plus Karnataka)

| | |
|---|---|
| **Metric** | Macro-F1 and High-class recall on the test fold; macro-F1 on its Karnataka rows |
| **Bar** | **Macro-F1 >= 0.75 AND recall(High) >= 0.50 AND Karnataka-slice macro-F1 >= 0.75** |
| **Baseline** | Majority class |

**Ships provisional regardless**, with `provenance_verified: False` on every
response, until the source is known.

### 2026-09-25 — new models 20-28: seven datasets (coffee, tea, cauliflower, onion, potato, tomato, wheat kernels)

**Written before any of these models was trained.** The datasets were supplied
on 2026-09-25. User decisions:

- train all nine tasks, one after the other, on the full data;
- serve later (none is an app crop except wheat);
- **keep every file**: copies and processed variants are grouped with their
  source photo, never discarded.

**Verified before writing** (read-only audit, 2026-09-25):

- **Coffee:** 3,322 files hold 1,810 distinct contents. 438 images are stored
  2-102 times under different names (byte-identical, 0 px differ).
- **Tea:** every `IMG_####` photo has 11 files: `_result` plus blur 3-9, noise
  2/4 %, grey, binary and rotate +-15. The 3x3 blur differs from `_result` by
  1/255.
  - 1,221 files are HEIC at 300x450, found only in the Fresh and Red Spider
    classes, against 650x650 JPGs elsewhere. That is a possible size/format
    shortcut, checked after training.
- **Tomato:** each image exists as `.jpg` and `.png` under one stem. The
  shipped train/val split leaks 13 identical files, so it is discarded.
- **Potato:** PlantVillage, healthy only 152.
- **Wheat kernels:** 170 photos, 6 cultivars.

#### Models and grouping (leakage control fixed now)

| # | Task key | Classes | Grouping |
|---|---|---|---|
| 20 | `coffee` | healthy, leaf rust, phoma | exact copies + similarity (rule below) |
| 21 | `tea` | fresh, Helopeltis, red spider mite | source id `IMG_####` (all 11 variants together) + EXIF sessions |
| 22 | `cauliflower` (leaves) | Alternaria leaf spot, downy mildew, healthy | similarity |
| 23 | `cauliflower curd` | Alternaria, bacterial soft rot, bacterial spot, black spot, healthy, purple tinge | similarity |
| 24 | `onion` (leaves) | healthy, unhealthy (label from the Healthy/Unhealthy folder level) | EXIF sessions |
| 25 | `onion bulb` | healthy, unhealthy (Mixed ratio folders count as healthy) | EXIF sessions |
| 26 | `potato` (leaves) | early blight, late blight, healthy | similarity |
| 27 | `tomato fruit` | damaged, old, ripe, unripe (grades) | source id (jpg+png stem) + similarity |
| 28 | wheat kernels | damaged, healthy | one photo = one group, stratified by cultivar x label |

- **Similarity rule** (tasks without capture times):
  - threshold = max(0.93, the 99th percentile of random same-class pairs,
    rounded up to 0.01);
  - calibrated on untuned ImageNet features, as for rice;
  - the value is recorded in the results, not chosen by outcome.
- **Split:** 60/20/20 by group, stratified by class. Selection is on
  validation, and test is read once. Models 20-27 use the leaf pipeline (256 px,
  two-phase MobileNetV3-Large). Model 28 uses 384 px crops from 1536 px photos,
  scored over a grid.

#### Bar (the leaf bar, per model)

**Macro-F1 >= 0.85 AND every class recall >= 0.70 AND healthy precision >=
0.90** where the task has a healthy class. For tomato fruit, a grading task
with no healthy class, the first two apply. A class too thin to reach the test
fold fails its recall criterion. The baseline is the majority class.

**Stated before any result.**

- **Cauliflower curd:** Alternaria has 45 images, so its recall rests on a
  handful of test images.
- **Potato:**
  - its healthy precision rests on a small healthy slice (152 in total);
  - PlantVillage photos are lab shots on plain backgrounds, so field transfer
    is unmeasured.
- **Wheat kernels:** about 34 test photos, so the evidence is weak whatever the
  score.
- **Onion:** "unhealthy" names no cause, so the output is a flag, not a
  diagnosis.
- **All:** provisional regardless, since each is one source and capture set.
  Every response carries `is_seeded_crop` (False except wheat).

### 2026-09-25 (later) — models 20-28: calibrated thresholds, empty files, and complete linkage for 23 and 27

**Written after the audits and before any of these models trained.** The bars
are unchanged.

- **Calibrated similarity thresholds**, by the rule above:

  | Task | p99 of random same-class pairs | Threshold |
  |---|---|---|
  | Coffee | 0.864 | 0.93 |
  | Cauliflower leaves | 0.889 | 0.93 |
  | Cauliflower curd | 0.947 | **0.95** |
  | Potato | 0.888 | 0.93 |
  | Tomato fruit | 0.889 | 0.93 |

- **Coffee: 102 empty (0-byte) files** (100 in Health leaves, 2 in leaf rust).
  They contain no image and are skipped, with a count reported. This corrects
  an earlier statement that one image was stored 102 times: those were the empty
  files, which share a hash. Among the 3,220 real files, 437 images are stored
  more than once (up to 24 copies), and one content appears in two classes and
  is dropped.
- **Complete linkage for cauliflower curd (23) and tomato fruit (27).** At audit,
  single-linkage similarity grouping chained whole classes into one group:
  - curd: Healthy was 396 test images in 1 group, Black Spot 69 in 1;
  - tomato: Damaged was 701 in 1 group, Old 1,112 in 1.
  
  No usable split exists with that. These two tasks now group by complete
  linkage, where a group holds only images that are all pairwise at or above
  the threshold. Exact copies and source ids are still merged first. Result:
  - curd: 1,125 groups, 8-66 test groups per class;
  - tomato: 3,998 groups, 67-301 test groups per class.
  
  Complete linkage can leave a near-copy pair on opposite sides where a chain
  would have joined them. The post-training scene-leakage audit measures what
  remains, and it is reported with the result.
- **Sugarcane leaf images are no longer in `datasets/`**, so its audit cannot
  re-run. The model 10 result stands as recorded.

### 2026-09-25 (later) — models 24 and 25 (onion): capped sample

**Written before either onion model trained.** It was prompted by run time,
not by any result. Tea's epochs ran about 7 minutes each, so the full onion data
(about 24,000 images) would have added about 2 hours. The user chose a capped
sample (2026-09-25):

- **1,500 images per class**, drawn at random with seed 42 before caching
  (`MAX_PER_CLASS` in `train_leaf_condition_model.py`);
- that is 3,000 images per model, against about 6,200 for leaves and about
  17,800 for bulbs.

The grouping (pixel-verified duplicates, EXIF capture sessions) and the bar are
unchanged and run on the sample. The unsampled images are not used for
anything, including testing. The results report the sample sizes beside the
metrics.
