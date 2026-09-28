# Model results

Measured 2026-09-22. Every bar in `MODEL_BARS.md` was written and committed
before any of these numbers existed.

Each model was fitted on a training fold, tuned against a validation fold, and
scored once on a test fold that no tuning decision had seen. Where a test fold
was read more than once, it is stated.

## Summary

| # | Model | Bar | Measured | Verdict |
|---|---|---|---|---|
| 1 | Crop recommendation (N/P/K + weather) | weighted-F1 >= 0.90, seeded-crop recall >= 0.85 | 0.9970, recall 0.90-1.00 | **SHIPS** (provisional) |
| 2 | Crop-from-soil-type | macro-F1 >= 0.75 | 0.9724 | **SHIPS** (provisional) |
| 3 | Fertilizer targets (lookup) | N/P/K constancy assertion passes | passes, 97 crops | **SHIPS** |
| 4 | Disease Q&A retrieval (unscoped) | recall@3 >= 0.70, recall@1 >= 0.50 | 0.5447, 0.4356 | **DOES NOT SHIP** |
| 4b | Disease Q&A retrieval (crop-scoped) | recall@3 >= 0.75, recall@1 >= 0.55 | 0.7614, 0.6220 | **SHIPS** |
| 5 | Soil fertility | macro-F1 >= 0.75, recall(class 2) >= 0.50 | 0.6944, 0.50 | **DOES NOT SHIP** |
| 5b | Soil fertility class, new labelled soil tests (provenance unverified) | macro-F1 >= 0.75, recall(High) >= 0.50, Karnataka macro-F1 >= 0.75 | 0.9808, 0.9776, 0.9743 | **SHIPS** (provisional, provenance unverified) |
| 6 | Yield prediction | MAE beats median baseline by >= 10% (national and Karnataka), R-squared >= 0.60 | +21.9%, +87.5%, 0.9495 | **SHIPS** (percentile output only) |
| 7a | Soil type from photo — classical CV | accuracy >= 0.80, per-class recall >= 0.60 | 0.9178 | clears, but 7b is better |
| 7b | Soil type from photo — MobileNetV3 | same bar | **0.9726** | **SHIPS** (additive) |
| 10 | Leaf condition from photo — sugarcane | macro-F1 >= 0.85, every class recall >= 0.70, healthy precision >= 0.90 | **0.5248**; healthy precision **0.7684** | **DOES NOT SHIP** |
| 11 | Insect pest detection (YOLOv8) | identification macro-F1 >= 0.85, app-class recall >= 0.70, mAP@0.5 >= 0.70 | id macro-F1 0.9005, app-class recall 0.71-1.00, mAP@0.5 0.9384 | **SHIPS** (provisional) |
| 12 | Rice disease type, conditional | macro-F1 >= 0.85, every class recall >= 0.70 | 0.8993; recall 0.80-1.00 | **SHIPS** (provisional, conditional) |
| 13 | Pearl millet disease type, conditional (not an app crop) | macro-F1 >= 0.85, every class recall >= 0.70 | 0.9377; recall 0.91-0.98 | **SHIPS** (provisional, conditional, unseeded crop) |
| 14 | Wheat canopy segmentation (heading + cover; not an app crop) | head IoU >= 0.60, plant IoU >= 0.80, cover MAE <= 0.05 and <= 50% of baseline, heading bal. acc. >= 0.85 | head 0.676, plant 0.827, **cover MAE 0.0756**, heading 0.985 | **DOES NOT SHIP** |
| 14b | Wheat heading detection only (same model; bar declared post hoc) | heading bal. acc. >= 0.85, head IoU >= 0.60 | 0.9848, 0.6759 | **SHIPS** (provisional, heading only, unseeded crop) |
| 15 | Soybean seed yield from plant traits (all features; not an app crop) | R-squared >= 0.70, MAE >= 30% below mean baseline | **R-squared 0.1449, MAE 1.9% worse than baseline** | **DOES NOT SHIP** |
| 16 | Sugarcane yield from the **synthetic** farm CSV | R-squared >= 0.60, MAE >= 10% below baseline | R-squared 0.8937, MAE 71.0% below | clears, **NEVER SERVED** (synthetic data) |
| 17 | Tobacco leaf lesion severity (segmentation; not an app crop) | lesion IoU >= 0.50, lesion-share MAE <= 50% of baseline | 0.5568; 24.8% of baseline | **SHIPS** (provisional, unseeded crop) |
| 18 | Mandi price 13 weeks ahead, Karnataka weekly by district (+ seasonal outlook) | per crop: MAE >= 10% below persistence and <= seasonal-naive; pooled direction >= 0.60 | 8 of 13 crops pass; pooled direction 0.719 | **SHIPS for 8 crops** (provisional); outlook always |
| 19 | Vegetable variety/size classifier (14 folders; produce, not an app crop) | macro-F1 >= 0.85, all 14 class recalls >= 0.70 | **0.6657** over 9 measurable classes; 7 of 14 recalls fail (5 unmeasurable) | **DOES NOT SHIP** (never served) |
| 20 | Coffee leaf (healthy / rust / phoma) | leaf bar | macro-F1 0.9619; recall 0.907-1.000; healthy precision 0.9774 | **SHIPS** (provisional, not an app crop) |
| 21 | Tea leaf (fresh / Helopeltis / red spider) | leaf bar | 0.9909; recall 0.990-0.993; healthy precision 0.9901 | **SHIPS** (provisional, not an app crop) |
| 22 | Cauliflower leaf | leaf bar | 0.9952; recall 0.984-1.000; healthy precision 1.0000 | **SHIPS** (provisional, not an app crop) |
| 23 | Cauliflower curd (6 classes) | leaf bar | 0.9936; recall 0.976-1.000; healthy precision 1.0000 | **SHIPS** (provisional; photos highly alike) |
| 24 | Onion leaf healthy/unhealthy (capped sample) | leaf bar | 0.9684; recall 0.960-0.977; healthy precision 0.9608 | **SHIPS** (provisional; cause not named) |
| 25 | Onion bulb healthy/unhealthy (capped sample) | leaf bar | 0.9933; recall 0.990-0.997; healthy precision 0.9901 | **SHIPS** (provisional; cause not named) |
| 26 | Potato leaf (PlantVillage) | leaf bar | 0.9794; recall 0.967-1.000; healthy precision 0.9355 | **SHIPS** (provisional; lab photos) |
| 27 | Tomato fruit grade (damaged / old / ripe / unripe) | leaf bar, no healthy class | 0.9837; recall 0.971-0.998 | **SHIPS** (provisional, not an app crop) |
| 28 | Wheat kernel sunn-pest damage | leaf bar, 2 classes | 1.0000 on 34 photos | **SHIPS** (provisional; **colour-only baseline 0.94**, see §28) |

Twenty-two ship (18 for 8 of its 13 commodities), seven do not, and one clears its
bar but is never served because its data is synthetic (16). Models 10-12 were
added 2026-09-23; 11 and 12 were stopped at the user's request before their test
reads, then finished on 2026-09-24 (11 resumed from its checkpoint, 12 retrained
from the start). Models 13-19 were added and trained 2026-09-24; 14b ships 14's
heading output alone, under a bar written after its test read. Model 5b (2026-09-25)
replaces the failed model 5. Models 20-28 (2026-09-25/26) cover seven new datasets;
all nine pass, and none is reachable in the app until its crop is added.

---

## 1. Crop recommendation — SHIPS, provisional

Split: stratified 60/20/20 (train 3,957 / val 1,319 / test 1,320).

| Metric | Bar | Measured |
|---|---|---|
| weighted-F1 (test) | 0.90 | **0.9970** |
| recall(rice) | 0.85 | 0.9000 |
| recall(ragi) | 0.85 | 1.0000 |
| recall(maize) | 0.85 | 1.0000 |
| recall(cotton) | 0.85 | 1.0000 |
| majority-class baseline | — | 0.0697 |

Validation weighted-F1 was 0.9953 against a test of 0.9970 — no overfitting gap.
Macro-F1 across all 51 classes was 0.9961, reported but not barred, because 14
classes have under 50 rows and one has 7.

**What this score does not mean.** `merged_crop_dataset.csv` is synthetically
sampled from per-crop distributions and is highly separable. 0.997 is evidence
the pipeline is wired correctly, not evidence the model knows what to plant on
a particular acre. Nothing here has been agronomist-reviewed. Ships provisional.

**Structural gap.** Sugarcane is absent from all 51 labels, so this model can
never recommend one of the app's five seeded crops. `unreachable_seeded_crops()`
reports this at runtime rather than leaving a caller to infer it.

## 2. Crop-from-soil-type — SHIPS, provisional

Split: stratified 60/20/20 (train 1,860 / val 620 / test 620).

macro-F1 **0.9724** against a bar of 0.75; majority-class baseline 0.0323.

`soil_type_vocab` is now computed on the training split only. The inherited
version computed it over the full dataframe, so the artifact advertised
categories the model may never have been fitted on — metadata rather than a
scoring leak, but the metadata is exactly what a caller consults to ask "does
this model know my soil type?"

**Caveat.** Exactly 100 rows per class across 31 classes is a
synthetic-generation signature; real crop distributions are not uniform. This
overstates performance on observed data.

Unlike model 1, this dataset **does** contain sugarcane (F1 0.80), so it
reaches a seeded crop model 1 cannot.

## 3. Fertilizer targets — SHIPS

Not a model. 1,843 rows collapse to 97 crops. The N/P/K constancy assertion
**passed for every crop**, including after crop-alias merging — which
independently validates `ml/prep/common.py`'s alias table, since a bad merge
would have produced conflicting targets and failed the build.

**Gap:** no sugarcane row exists in `Fertilizer.csv`. Seeded crops covered:
cotton, maize, ragi, rice.

## 4. Disease Q&A retrieval (unscoped) — DOES NOT SHIP

| Metric | Bar | Measured |
|---|---|---|
| recall@3 | 0.70 | **0.5447** |
| recall@1 | 0.50 | **0.4356** |
| chance baseline (88 pairs) | — | 0.0341 |

**Failure category: the bar described a serving mode that does not exist.**
Not a data ceiling and not a technique ceiling.

Bar 4 assumed retrieval across all 88 (crop, disease) pairs. The app cannot
invoke that: a disease question arrives through a scouting observation, which
belongs to a planting, which has a `crop_id`. There is no crop-less query path.

This result is recorded as a failure and stays one. It was **not** reinterpreted
into a pass. A separate model with its own independently justified bar was
written instead — see 4b and `MODEL_BARS.md` section 9.

## 4b. Disease Q&A retrieval (crop-scoped) — SHIPS

| Metric | Bar | Measured |
|---|---|---|
| recall@3 | 0.75 | **0.7614** |
| recall@1 | 0.55 | **0.6220** |
| chance baseline (~8 diseases/crop) | — | 0.3750 |

**Evidence the bar was not fitted to the result:** bar 4b was written at 0.75
while the only measurement in hand was an English-only 0.7295, which *fails*
it. The clean all-language measurement then came in at 0.7614.

**Technique change.** Character n-grams (`char_wb`, 2-5, sublinear) replace the
inherited word-level vectorizer, selected on a separate dev holdout (seed 7) so
the reported seed-42 holdout stayed clean: 0.4811 to 0.5705 on that dev split.
The gap is mostly Devanagari — sklearn's default word token pattern handles
Hindi and Marathi poorly, and two thirds of this corpus is in those scripts.
Per-language indices were tried and did not help (0.5553).

**Shipping condition.** 0.75 is justified only while the UI keeps a visible
"see all diseases for this crop" path. The fallback to retrieval is listing all
8 of that crop's diseases, which has recall 1.0 by construction; the shortlist
only earns its place if the farmer rarely needs to go past it. If the shortlist
becomes the sole route to a diagnosis, this bar must be raised before shipping.

**New corpus finding — 68 questions belong to multiple crop-disease pairs.**
68 distinct question strings, across 137 rows (6.1% of the corpus), are recorded
against more than one (crop, disease) pair. Example: identical bacterial-ooze
text under both Tomato/Bacterial Wilt and sugarcane/Grassy Shoot Disease;
identical boll-and-fibre text under both cotton and sugarcane.

This was **verified not to be a bug in our pairing code** — the raw CSV really
does carry these assignments, and a direct check confirmed 0 mispaired rows in
the long-form transformation.

These are not treated as mislabellings with a knowable correct answer. Some are
genuine shared symptomatology; bacterial wilt does present alike across crops.
They are kept, not deleted, and a query matching one surfaces **both** pairs
together flagged `shared_symptom`, rather than silently resolving to one. Also
recorded in `DATASETS_STATUS.md`.

Other corpus properties: 50 rows have `remedy_hi` identical to `remedy_en` (the
Hindi column silently falls back to English), flagged per result as
`hindi_is_english_fallback`; there is **no ragi coverage** (4 of 5 seeded
crops); only en/hi/mr against the app's 10 locales.

## 5. Soil fertility — DOES NOT SHIP

| Metric | Bar | Untuned | Tuned |
|---|---|---|---|
| macro-F1 (test) | 0.75 | 0.6995 | **0.6944** |
| recall(class 2) | 0.50 | 0.2500 | **0.5000** |
| accuracy (not barred) | — | 0.8807 | 0.8407 |
| majority baseline | — | 0.50 accuracy / 0.22 macro-F1 | |

**Failure category: data ceiling.**

Class 2 (high fertility) is 39 rows total — 23 train, 8 validation, 8 test.

A genuine technique attempt was made rather than declaring a ceiling on
inspection. A validation-only sweep covered `balanced_subsample`, depth limits,
leaf-size limits, ExtraTrees, GradientBoosting, logistic regression, class-2
oversampling at 3x/6x/10x, and decision-threshold shifting. Threshold shifting
was clearly best on validation (macro-F1 0.8153, class-2 recall 0.875) and was
adopted.

**On test it collapsed to 0.6944 / 0.50.** A validation-to-test gap of 0.12
macro-F1 is the finding: a threshold selected on 8 validation rows fits noise.
The threshold bought class-2 recall by destroying class-2 precision (0.24), so
macro-F1 got marginally *worse* than the untuned model.

Note the test fold was read twice — once for the untuned model, once for the
tuned one. Both readings are reported above.

**Accuracy was 0.8807 untuned.** Under an accuracy bar this model would have
shipped looking excellent while detecting 2 of 8 high-fertility samples. That
is what the macro-F1-plus-minority-recall bar was written to catch.

**Second, independent reason it could not have shipped unqualified.**
`soil_fertility.csv` has no state, district, date or provenance column. Whether
its 880 samples resemble Karnataka farmland is unverifiable by construction.

**Consequence: none.** `fertilizer_recommendation.py` computed this model's
output and then ignored it — the advice came entirely from `target - current`
arithmetic. The failing model was decorative, so removing it cost the feature
nothing.

**What would unblock it:** substantially more high-fertility samples, with
geography attached.

## 5b. Soil fertility, new labelled soil tests — SHIPS, provisional

Trained 2026-09-25 against a bar written first (`MODEL_BARS.md` §9, model 5b).

**Data.** `datasets/soil_dataset/` holds a Karnataka file (1,831 rows) and a
pan-India file (3,805 rows, 10 states). The two are disjoint. Combined there
are **5,636 samples** from 4,605 fields: Low 1,982, Medium 2,088, High 1,566.

**Provenance: unverified.** The user states the data is real and declined to
name the source. The evidence on both sides is in the bar.

**Split and model.** The features are the 12 soil-test values; the index the
label is cut from is excluded. The split is 60/20/20 by field (train 3,381,
val 1,127, test 1,128). Validation macro-F1: logistic 0.840, random forest
0.942, **gradient boosting 0.963** (chosen).

| Metric | Bar | Measured |
|---|---|---|
| Macro-F1 (test) | >= 0.75 | 0.9808 |
| Recall(High) | >= 0.50 | 0.9776 |
| Karnataka slice macro-F1 (n=500) | >= 0.75 | 0.9743 |

Majority baseline 0.3706. Leave-one-Karnataka-district-out
macro-F1 (not barred): Ballari 0.972, Belagavi 0.966, Chikkamagaluru 0.936, Davanagere 0.986, Dharwad 0.985, Hassan 0.982, Mandya 0.977, Mysuru 0.980, Raichur 0.944, Shivamogga 0.933, Tumakuru 0.995, Vijayapura 0.970.

**It clears its bar, and what that means is narrow.** `Fertility_Class` is an
exact cut of a nutrient index computed from the same 12 values, so the model
learns that rating formula; its near-perfect score is expected. It answers
"what class would this lab scheme give these values", nothing about yield or
fertiliser need.

**Why it passes where model 5 failed.** The data changed, not the technique:

- 1,566 High samples against 39;
- a documented class boundary (the index thresholds) against undocumented 0/1/2
  labels.

**Serving.** `predict_soil_fertility` in
`ml/algorithms/soil_fertility_prediction.py` returns the class, a categorical
confidence, `provenance_verified: False` and caveats, and flags missing
inputs (verified). Served from 2026-09-25 as `POST /v1/soil-fertility` in the
sidecar and `GET /api/v1/ml/fields/:id/soil-fertility` in the app; see
`ML_SERVING_INTEGRATION.md` §3-§4 (soil fertility) and §8.

## 6. Yield prediction — SHIPS, percentile output only

Split: **held-out years** — train 1997-2014 (14,324), validate 2015-2017
(3,090), test 2018-2020 (2,163). 112 rows with non-positive yield or area
dropped. Weather join matched 19,577/19,577.

| Scope | n | MAE | R-squared | scale-free median error |
|---|---|---|---|---|
| model, national | 2,163 | **13.05** | 0.9495 | 0.2508 |
| median baseline, national | 2,163 | 16.71 | 0.9189 | 0.2571 |
| model, Karnataka | 135 | **6.12** | 0.9981 | 0.2717 |
| median baseline, Karnataka | 135 | 48.88 | 0.8286 | 0.2342 |

MAE improvement over baseline: **+21.9% national, +87.5% Karnataka**. Both
clear the 10% bar.

### Correction to an earlier assumption

The inherited script's R-squared = 0.9501 from a random split was assumed to be
panel memorisation. **That assumption was tested and was wrong.** On held-out
years the same model scores 0.9495 — essentially unchanged. The random split
was not inflating R-squared.

The real problem was different and the baseline comparison is what exposed it.
Crop identity alone explains nearly all variance, because crops sit on wildly
different scales (coconut median 8,466, rice 2.2). **The median lookup alone
scores R-squared 0.9189.** So 0.95 sounds excellent while being barely
distinguishable from a table lookup.

Measured against that lookup, the inherited configuration was **19% worse than
doing nothing**, with a scale-free median error of 0.99 against the lookup's
0.26.

**The R-squared bar of 0.60 was therefore mis-specified — far too lenient.** It
was set expecting temporal generalisation to be hard, without anticipating that
between-crop variance would dominate. It is left unchanged rather than
retrofitted; the MAE-vs-baseline bar did the discriminating work and is the one
that matters. Noted here so the next person does not reuse an R-squared bar on
data with this structure.

### The fix

Squared error on the raw target is dominated by large-scale crops: one coconut
row outweighs thousands of rice rows. Absolute error on a `log1p` target fixes
both halves. Selected on validation:

| target / objective | MAE vs baseline (validation) |
|---|---|
| raw, squared error (inherited) | **-17.6%** |
| log1p, squared error | -3.0% |
| **log1p, absolute error** | **+24.3%** |
| ratio-to-crop-median | -125.7% |

Test was read twice: once with the raw target, once with the fixed one. Both
are reported.

### Output constraint

Served output is `percentile_within_crop`, never a number. `unit` is `null` and
`unit_note` travels with every response. The raw value is retained as
`_raw_model_output` with `_raw_not_for_display: true` and **must not be
forwarded past the serving boundary**.

The year problem is now reported rather than hidden: a call for 2026 returns
`year_in_training_range: false` and two caveats — that tree models cannot
extrapolate past 2014 so this is effectively the 2014 answer, and that no
weather observations exist for 2026 so a state mean was substituted. The
inherited code did both silently, on every call.

## 7. Soil type from photo — SHIPS (MobileNetV3), additive

**The leakage check found real leakage.** 56 of 295 training images (19%) were
near-duplicates of test images. They were removed from training before fitting.

A second leakage path surfaced during the run: validation accuracy came out at
exactly 1.0000, which turned out to be duplicates *within* the training
directory straddling the fit/validation boundary. The 239 remaining training
images are only **183 distinct photographs**. Splitting was changed to operate
on digest groups so copies cannot separate.

That fix cost the classical model 4 points of apparent accuracy — 0.9589 before,
0.9178 after. That 4 points was leakage.

| Candidate | Test accuracy | Alluvial | Black | Red | Cinder (not barred) |
|---|---|---|---|---|---|
| (a) classical CV + RF | 0.9178 | 0.9744 | 0.9231 | 0.9333 | 0.5000 |
| **(b) MobileNetV3** | **0.9726** | 1.0000 | 0.9231 | 1.0000 | 0.8333 |
| majority baseline | 0.5342 | | | | |

Both clear the bar; **(b) ships**. Its validation accuracy was 0.8980 against a
test of 0.9726, a normal gap for a 49-image validation fold.

Candidate (a) was not a fallback. The inherited script chose classical CV only
because its environment could not reach `storage.googleapis.com` for pretrained
weights. That was verified not to apply here before either model was trained,
so (a) competed on merit and lost.

**Caveats.** 183 distinct training images and 73 test images is a small,
duplicate-ridden sample. Cinder has 6 test images, so its recall resolution is
0.167 — reported, never barred. Cinder is also the one class
`soil_to_crop_bridge.py` cannot map into the crop model's vocabulary.

**Additive, never a replacement.** The farmer already gets a soil type from
their district via `soilLookup.js`. Disagreement between the two is information
for the caller to present, not something resolved here.

---

## 10. Leaf condition from photo — sugarcane — DOES NOT SHIP

Measured 2026-09-23 against a bar written that morning, before the model was
trained (`MODEL_BARS.md` §9). Dataset and its defects: `DATASETS_STATUS.md`
§2.8. Architecture: MobileNetV3-Large, ImageNet-pretrained, two-phase transfer
learning (frozen head, then the last 5 feature blocks unfrozen), phase chosen on
validation.

### The first run passed. It was measuring memory.

A first run split by pixel-verified duplicate group, 70/15/15, and cleared every
criterion: test macro-F1 0.9807, healthy precision 0.9688, validation macro-F1
0.9918. **These numbers are recorded here as the leaky measurement and are not
the result.**

A validation score of 0.99, on a dataset already shown to hold 614
conflicting-label duplicates, prompted a scene-level audit
(`ml/training/audit_leaf_scene_leakage.py`). With untuned ImageNet features, two
different training images of the same class had median similarity 0.652. A
test image's nearest training image had **0.980**, and for **78%** of test
images that neighbour sat within three filenames of it in the same folder.

Every photo carries an EXIF capture time, and it explains the pattern: each
class was shot in continuous streams. The 5,316 distinct photos are only **216
capture sessions** at a 10-second gap. Consecutive frames of a stream share
leaf, light, background and moment. A test fold that shares sessions with
training asks "have I seen this moment?", not "can I read a new photo?".

The protocol was revised — in `MODEL_BARS.md` §9, before retraining, with the
bar left unchanged — to split 60/20/20 by capture session using
`StratifiedGroupKFold`. The numbers below come from that split. Test was read
once.

### Result — misses broadly

Session groups: train 3,608 / val 1,288 / test 1,238. **Phase A selected**
(validation 0.5266 against phase B's 0.5043). Fine-tuning deeper did not help,
so model capacity is not the constraint.

| Metric | Bar | Measured |
|---|---|---|
| macro-F1 | 0.85 | **0.5248** |
| healthy precision | 0.90 | **0.7684** |
| accuracy (not barred) | — | 0.5880 |
| majority baseline | — | 0.2763 |

| Class | Category | Test images | Test sessions | Recall |
|---|---|---|---|---|
| Banded Chlorosis | abiotic | 74 | 3 | 0.9730 |
| Brown Spot | disease | 342 | 11 | **0.6053** |
| BrownRust | disease | 43 | 3 | **0.1163** |
| Dried Leaves | abiotic | 86 | **1** | **0.1628** |
| Grassy shoot | disease | 58 | 2 | 0.9655 |
| Healthy Leaves | healthy | 88 | 3 | 0.8295 |
| Pokkah Boeng | disease | 43 | 2 | **0.0698** |
| Sett Rot | disease | 131 | 4 | 0.9771 |
| Viral Disease | disease | 115 | 5 | 0.7391 |
| Yellow Leaf | disease | 232 | 6 | **0.3190** |
| smut | disease | 26 | 3 | **0.4231** |

**Healthy precision 0.7684 is the most serious number here.** About one in four
"healthy" verdicts would be wrong, which is the exact error the strictest
criterion was written to prevent.

Largest confusions: Dried Leaves called Banded Chlorosis (64 of 86); Yellow Leaf
called Dried Leaves (84 of 232); Pokkah Boeng called Brown Spot (33 of 43);
Brown Spot called Yellow Leaf (55 of 342).

**Cause category: data ceiling, compounded by label noise.** Validation (0.527)
and test (0.525) agree, so the failure is consistent, not a noisy fold. Several
of the confused pairs are pairs that were already shown to share identical,
cross-labelled photographs (`DATASETS_STATUS.md` §2.8), which fits label noise in
the non-duplicate images too. That fit is suggestive, not proof. No technique
change was attempted, so a technique ceiling is not ruled out.

### Enforcement

The artifact records `passed_bar: False`, and
`ml/algorithms/leaf_condition_prediction.py` raises `ModelDidNotShip` for it.
Verified. The serving module, registry and training pipeline stay in place for
the next attempt.

---

## 11. Insect pest detection (YOLOv8) — SHIPS, provisional

Dataset arrived 2026-09-23; bar written first (`MODEL_BARS.md` §9, model 11).
Training was stopped on 2026-09-23 at the user's request, with YOLOv8n finished
and YOLOv8s at epoch 56. On 2026-09-24 YOLOv8s was resumed from its epoch-56
checkpoint (`--resume`, which reuses finished runs and resumes interrupted
ones), and the selection and single test read ran as the protocol specifies.

- **Data:** Roboflow RF100 "insects" v2, CC BY 4.0, 995 images, 10 classes, 5 to
  17 test instances per class. 16 photos appeared in two shipped splits; the
  copies were removed from train and valid, leaving 681 / 198 / 100 (test as
  shipped). Details: `DATASETS_STATUS.md` §2.9.
- **Candidates, chosen on valid mAP@0.5:** YOLOv8n **0.9189** (100 epochs,
  52.7 min) vs YOLOv8s 0.9168 (100 epochs across the interruption, 106.5 min).
  **YOLOv8n chosen** — also the cheaper model to serve.
- **Test, read once:**

| Metric | Bar | Measured |
|---|---|---|
| Identification macro-F1 (top box at conf 0.25; no box = wrong) | >= 0.85 | **0.9005** |
| mAP@0.5 | >= 0.70 | **0.9384** |
| mAP@0.5:0.95 | — | 0.6446 |
| Identification accuracy | — | 0.8900 (majority baseline 0.1700) |
| No detection | — | 3 / 100 |

| Class | n | Id recall | AP@0.5 | App-relevant |
|---|---|---|---|---|
| army worm | 17 | 0.8824 | 0.9059 | yes |
| legume blister beetle | 11 | 0.7273 | 0.8522 | no |
| red spider | 7 | 1.0000 | 0.9950 | yes |
| rice gall midge | 9 | 0.8889 | 0.9675 | yes |
| rice leaf roller | 9 | 1.0000 | 0.9750 | yes |
| rice leafhopper | 11 | 1.0000 | 0.9667 | yes |
| rice water weevil | 16 | 0.9375 | 0.9275 | yes |
| wheat phloeothrips | 8 | 0.8750 | 0.9550 | yes (since 2026-09-26) |
| white backed plant hopper | 7 | **0.7143** | 0.9530 | yes |
| yellow rice borer | 5 | 0.8000 | 0.8859 | yes |

**Clears every part of its bar.** Two cautions travel with the pass:

- **Thin per-class evidence.** Class recalls rest on 5 to 17 test images.
  White-backed planthopper passes at 5 of 7 (0.7143 against 0.70); one more
  miss would have failed the bar. Yellow rice borer, the one class linked to
  an agronomic rule (`RICE_STEM_BORER_SCOUT`), is 4 of 5.
- **Provisional regardless of metric.** Every image is a tight 224px crop with
  one insect. The model has never seen a field photo, several insects at once,
  or an insect-free image, so an empty result is reported as `no_detection`,
  not "no insect". Host-crop links in `ml/insect_pests.py` are unverified.

**Wheat thrips became app-relevant on 2026-09-26**, when wheat was added as an
app crop. `ml/insect_pests.py` now lists wheat as its host, so wheat plantings
are offered the insect check. This changes which classes count as
app-relevant, not the model or its test read. The class was measured in the
same single read (recall 0.8750 on 8 images), so the app-class recall
criterion still holds (0.71-1.00). The relabelling was decided after that read
and is stated here as such. Army worm still lists only maize and rice; the
class does not say which armyworm it shows.

Serving verified: `detect_insects(<test image>, "rice")` loads the artifact
through its `passed_bar` gate and returns structured detections with the
caveats above.

---

## 12. Rice disease type (conditional) — SHIPS, provisional

Dataset arrived 2026-09-23; bar written first (`MODEL_BARS.md` §9, model 12).
Training was stopped at the user's request on 2026-09-23 before the test read.
On 2026-09-24 it was **retrained from the start** on the corrected split. The
script keeps its best weights only in memory, so there was no checkpoint to
resume from.

### Final run, 2026-09-24

Corrected split, with all images compared: 5,932 files, 1,094 distinct photos,
302 independent groups, and train / val / test 3,559 / 1,185 / 1,188. The
"sessions" in the per-class table are those groups. Training took 18.0 minutes.
Phase A reached a validation macro-F1 of 0.9543, and phase B reached 0.9570 at
epoch 4 (early stop at epoch 7). **Phase B was selected on validation.**

| Class | Test images | Groups | Recall | Precision |
|---|---|---|---|---|
| Bacterial blight | 318 | 14 | **0.8019** | 0.99 |
| Blast | 288 | 17 | 0.9028 | 0.83 |
| Brown spot | 320 | 21 | 0.9094 | 0.91 |
| Tungro | 262 | 8 | 1.0000 | 0.88 |

**Test macro-F1 0.8993** (bar 0.85), accuracy 0.8990, majority baseline 0.2694.
Every class recall is at or above 0.80 (bar 0.70). **Clears its bar.**

**Scene audit after the run:** **0** test images are near-copies of a training
image (similarity >= 0.97). The leaky run had 223. Accuracy on the 1,170 test
images with no close training neighbour is 0.8974, so the score does not rest on
copies. As the audit itself says, this does not rule out shared lighting or
background within a source.

Cautions that travel with the pass:

- **The validation-to-test gap is 0.058** (0.9570 against 0.8993). That is
  larger than for the other leaf models and says the 302 groups are not uniform.
  Expect field accuracy below 0.90.
- **Errors concentrate in two pairs:**
  - Bacterial blight is called Tungro 36 times and Blast 27 times, so its recall
    is the lowest of the four.
  - Blast and Brown spot are confused both ways (28 and 27).
- **Tungro rests on 8 groups.** Its 1.0000 recall is thin evidence.
- **Conditional only.** There is no healthy class, so the model is served only
  with `symptom_reported=True`, and the response always offers "none of these".
  This was verified: without the flag the call returns `symptom_required`.

The leaky first run and the stopped retrain are recorded below as history.

### History: leaky first run and stopped retrain (2026-09-23)

**First run: leaky, recorded, not the result.** It trained on a split whose
similarity grouping compared one representative photo per duplicate cluster.
Because those representatives sit in arbitrary orientations, rotated,
brightened copies escaped grouping. The run scored test macro-F1 **0.9655**
(recall: Bacterial blight 0.924, Blast 0.979, Brown spot 0.966, Tungro 1.000).
The scene audit then found **223 of 1,186 test images (18.8%) had a training
image at similarity 0.97 or more** — the leakage precondition 2 existed to
prevent. Accuracy on the 792 test images with no close training neighbour was
0.9508. That is encouraging, but it is not a clean measurement.

**Correction:** compare every image (`MODEL_BARS.md` §9, the later model 12
entry). At the same 0.93 threshold this yields 302 independent groups, still
with no grouped pair crossing a disease label.

**Corrected retrain: stopped before its test read.** Phase A reached validation
macro-F1 0.9543 and phase B 0.9578 (epoch 4). It stopped at phase B epoch 6,
one epoch before early stopping would have ended it. Validation on the corrected
split is essentially the same as on the leaky one, which suggests the copies
were not carrying the score, but **only a test read can say that**.

**Safety at the time:** the leaky artifact was rewritten with `passed_bar: False`
and an `invalidated` note so serving refused it. The 2026-09-24 run overwrote
it with the clean artifact above (`passed_bar: True`, no `invalidated` note).

---

## 13. Pearl millet disease type (conditional) — SHIPS, provisional

Dataset `datasets/millets_dataset`, supplied 2026-09-24; bar written first
(`MODEL_BARS.md` §9, model 13). **Pearl millet (bajra), not ragi**, and not a
seeded app crop: responses carry `is_seeded_crop: False`, and a ragi photo gets
`no_model_for_crop`. The Healthy folder was **excluded** because it comes from a
different source (see the bar), so this is a conditional blast-vs-rust model
with the same serving contract as rice.

Grouping: 4,985 files are 4,669 distinct photos in 2,002 camera shots. Linking
consecutive shots at similarity >= 0.85 turns them into **84 sessions**. The
split is train 2,990 / val 998 / test 997, with 8 test sessions per class.
Phase A (frozen backbone) was selected on validation: 0.9432 against phase B's
0.9423. Training took 15.1 minutes.

| Class | Test images | Sessions | Recall | Precision |
|---|---|---|---|---|
| Blast | 586 | 8 | 0.9130 | 0.98 |
| Rust | 411 | 8 | 0.9757 | 0.89 |

**Test macro-F1 0.9377** (bar 0.85), accuracy 0.9388, majority baseline 0.5878.
Both recalls clear 0.70. **Clears its bar.** Validation (0.9432) and test agree.

**Scene audit after the run:**

- 23 test images (2.3%) have a training near-copy at similarity >= 0.97. These
  are likely revisits of the same leaf, which the adjacent-shot grouping cannot
  see. Accuracy on them is 0.913, no higher than elsewhere, so the score does
  not lean on them.
- On the 725 test images (72.7%) with no close training neighbour, accuracy is
  **0.9310**.

Errors: blast called rust 51 times, rust called blast 10 times.

Cautions that travel with the pass:

- **8 test sessions per class** is thin evidence.
- **One source, one camera.** Field photos from a farmer's phone are a
  different distribution.
- **No remedies link.** The Q&A corpus has no millet entries, so `qa_disease`
  is `None` for both classes.
- **Conditional only.** A healthy leaf would be named blast or rust, so the
  model is served only with `symptom_reported=True`, and "none of these" is
  always offered. Verified.
- **Not usable in the app until pearl millet is added as a crop.** Until then
  the model exists but no planting can reach it.

---

## 14. Wheat canopy segmentation — DOES NOT SHIP

Dataset `datasets/wheat_dataset`, GlobalWheat GWFSS v1.0, a 40% download (438
of 1,096). The bar was written first (`MODEL_BARS.md` §9, model 14). Not a disease model:
it labels head, stem, leaf and background pixels to derive **heading detected**
and **canopy cover**. Wheat is not a seeded app crop.

Setup:

- **Folds.** The shipped val set (88) is the test fold. 4 train images at
  similarity >= 0.93 to a test image were removed from train. The remaining 346
  form 345 groups: one link, so the data is essentially free of near-copies.
  The split is train 277 / val 69 / test 88.
- **Model.** LR-ASPP with a MobileNetV3-Large backbone, starting from COCO/VOC
  segmentation weights with 4-class heads. Random 320px crops, flips and
  90-degree rotations; square-root-inverse class weights.
- **Training.** Selected on validation mIoU (0.5514 at epoch 21). It ran 25
  epochs, the configured maximum, in 18.4 minutes.

| Criterion | Bar | Measured |
|---|---|---|
| Head IoU | >= 0.60 | 0.6759 |
| Plant-vs-background IoU | >= 0.80 | 0.8271 |
| **Canopy cover MAE** | **<= 0.05** | **0.0756 — FAIL** |
| Cover MAE / constant baseline (0.1817) | <= 0.50 | 0.4162 |
| Heading balanced accuracy | >= 0.85 | 0.9848 (recall 1.000, specificity 0.970; 55 headed / 33 not) |

Not barred: background IoU 0.6069, leaf 0.7280, stem 0.1528, mean IoU 0.5409.

**Failure: canopy cover is off by 7.6 percentage points on average.** That is
far better than guessing the mean (18.2 points), but it misses the 5-point
bar. The weak class is background (IoU 0.61): soil and litter seen between
leaves are confused with leaf, and cover depends directly on that boundary.

**Heading detection passed by a wide margin.** It found heads in all 55 headed
test images and wrongly reported heads in 1 of 33 unheaded ones. The bar is
joint, so this does not ship on its own. Shipping heading alone would need a
new bar written first, declared as chosen after seeing this result, as was done
for bar 4b.

**Cause category: data ceiling, most likely.** The validation curve was still
rising slowly when training stopped: mean IoU went from 0.53 to 0.55 over the
last 10 epochs, while cover MAE fluctuated between 0.07 and 0.09. And 60% of
the source dataset was not downloaded. The obvious next attempt is the full
1,096 images at the same bar. No tuning was done against the test fold.

The artifact records `passed_bar: False`. Canopy cover is not served in any
form.

### 14b. Heading detection only — SHIPS, provisional, bar declared post hoc

At the user's request (2026-09-24), the heading output of the same trained
model ships alone under bar 14b (`MODEL_BARS.md` §9). The bar keeps model 14's
thresholds for what heading depends on: balanced accuracy >= 0.85 and head IoU
>= 0.60. It was **written after model 14's test read**. It is applied to that
same read, not a fresh one, by `ml/training/apply_wheat_heading_bar.py`, which
re-reads nothing.

| Criterion | Bar | Measured |
|---|---|---|
| Heading balanced accuracy | >= 0.85 | 0.9848 (recall 1.000, specificity 0.970) |
| Head IoU | >= 0.60 | 0.6759 |

**Clears bar 14b.** The checkpoint records `heading_passed_bar: True` beside
model 14's `passed_bar: False`. `ml/algorithms/wheat_canopy_segmentation.py`
gates on `heading_passed_bar` and returns only `heading_detected` and caveats
(`detect_wheat_heading`; verified). No cover value, band or mask is served.

**Cautions:**

- **Selection bias.** This output was picked because it passed. A blind check
  on the 658 GWFSS images not yet downloaded would remove the bias, and is the
  recommended next step.
- **Thin evidence on the negative side.** Only 33 unheaded test images, and 1
  of them was wrongly called headed.
- **Scope.** Top-down research-site canopy photos only. Wheat is not an app
  crop, so nothing reaches the model until it is added.

---

## 15. Soybean seed yield from plant traits — DOES NOT SHIP

Dataset `datasets/soybean_dataset`, supplied 2026-09-24. Trained with all
features at the user's request. The bar was written first (`MODEL_BARS.md` §9,
model 15).

- **Data.** 55,450 rows are **108 unique plots**. The 55,342 exact duplicates
  were removed before anything else. The plots come from one factorial trial
  with 35 condition x treatment x genotype codes.
- **Split by treatment code.** The pool is 87 rows (28 treatments) and the test
  fold is 21 rows (7 treatments), read once.
- **Model family, chosen by grouped 4-fold CV on the pool:**
  - random forest: MAE 953.8, R-squared 0.231;
  - ridge: MAE 1013.8, R-squared 0.037.

| Metric | Bar | Measured |
|---|---|---|
| R-squared (test) | >= 0.70 | **0.1449** |
| MAE vs training-mean baseline | >= 30% better | **1.9% worse** (690.2 vs 677.2) |

**It fails outright.** Even with post-harvest yield components as inputs, it is
no better than predicting the average.

**Why.** Diagnostic on the de-duplicated data, not used for any modelling
choice:

- **Yield is set by the treatment combination.** 93% of yield variance lies
  between treatment codes. Replicate plots of one treatment agree closely
  (within-treatment SD 235 against 1,257 overall).
- **The plant traits track yield only loosely.** Pods x seeds per pod x seed
  weight correlates just 0.57 with recorded yield, so yield here is not the
  simple product of its components.

Predicting an unseen treatment combination from 28 others is the real task, and
this data is too small for it. A row-level split would have put replicates of
every treatment on both sides and scored well by memorising treatments. The
treatment split prevents that.

**Cause category: data ceiling.** The data is one trial of 108 plots with
undocumented codes. The artifact records `passed_bar: False` and `served:
False`. No serving module exists: no app input corresponds to these features.

---

## 16. Sugarcane yield, synthetic farm CSV — clears its bar, NEVER SERVED

Dataset `datasets/sugarcane_dataset/FINAL_SUGARCANE_DATASET.csv`, supplied
2026-09-24: 3,000 rows, 81 columns, Haridwar, 2018-2024. **The data is
synthetic.** The evidence is in `MODEL_BARS.md` §9 (model 16) and
`DATASETS_STATUS.md` §2.13. Trained at the user's request after the evidence
was shown, with the bar written first.

- **Split by year:** train 2,182 (2018-2022 plus rows with no year), validation
  415 (2023), test 403 (2024), read once.
- **Chosen on validation: ridge regression** (MAE 22.54, R-squared 0.913)
  against gradient boosting (MAE 23.53, R-squared 0.908).

| Metric | Bar | Measured |
|---|---|---|
| R-squared (2024) | >= 0.60 | 0.8937 |
| MAE vs training-mean baseline | >= 10% better | 71.0% better (24.78 vs 85.42 q/acre) |

**It clears its bar, and that says nothing about sugarcane.** A plain linear
model winning is itself evidence: the target was produced by a largely linear
formula of a few columns (nitrogen, potassium, disease severity, temperature),
and the model recovered it. On real sugarcane, variety, irrigation and soil
matter; in this data they have no effect.

**Never served.** The artifact records `served: False` and `synthetic_data:
True`, and no serving module exists. Sugarcane is an app crop, so serving
this would present an invented formula as agronomic advice. Changing that
would need an explicit decision, not a retrain.

---

## 17. Tobacco leaf lesion severity — SHIPS, provisional

Dataset `datasets/tobacco_dataset`: a 40% subset of Kaggle "Dataset for
Tobacco Leaf Disease Segmentation", 1,400 tiles with binary lesion masks. The
bar was written first (`MODEL_BARS.md` §9, model 17). The output is **lesion
area %** only, because no disease is named. Tobacco is not a seeded app crop.

**The shipped split was discarded.** The 320 real tiles come from 84 photos,
and 34 of those photos straddled it. The rebuilt folds:

- **Sessions.** Real tiles were grouped into 56 capture sessions from the
  filename timestamps and split 60/20/20 by session.
- **Evaluation data.** Validation (86 tiles) and test (60 tiles) hold **real
  tiles only**.
- **Augmented tiles.**
  - 408 `data1/` augmented tiles were linked to their real source tile
    (similarity >= 0.84).
  - 218 were **dropped** as copies of validation or test photos.
  - Training kept 174 real and 862 augmented tiles; the `data2/` tiles come
    from originals absent here.
- **Model and run.** LR-ASPP on MobileNetV3-Large, weighted cross-entropy, 480
  sampled crops per epoch. Selected at epoch 9 (validation lesion IoU 0.6734)
  and early-stopped at 13, in 18.5 minutes.

| Metric (60 real test tiles) | Bar | Measured |
|---|---|---|
| Lesion IoU | >= 0.50 | 0.5568 |
| Lesion-share MAE / training-mean baseline | <= 0.50 | 0.248 (0.0044 vs 0.0179) |

**Clears its bar.** Post-test leakage check: no test tile has a training tile at
similarity >= 0.93, and the maximum is 0.902. By comparison, augmented copies
of a photo sit at about 0.90 and different tiles of one photo at about 0.75.

Cautions that travel with the pass:

- **Validation-to-test drop.** Lesion IoU fell from 0.673 to 0.557. The test
  fold is 60 tiles from about 11 sessions, and the gap says the sessions differ.
- **Over-estimation.** Mean predicted lesion share is 1.26% against a true
  0.95%, about a third too high. Per-tile error (0.44 points) is small in
  absolute terms because lesions are small.
- **Narrow data.** Two days of photos (14-15 October 2023) from one source,
  close-up tiles only. The disease is not identified.

Serving: `measure_tobacco_lesions` in
`ml/algorithms/tobacco_lesion_segmentation.py` returns `lesion_area_percent`,
`is_seeded_crop: False` and caveats (verified). A non-tobacco crop gets
`no_model_for_crop`.

---

## 18. Mandi price 13 weeks ahead (Karnataka) — SHIPS for 8 crops, provisional

This unparks market price. Dataset: `datasets/historical_price_dataset`,
Agmarknet daily prices from 2023-01-01 to 2026-09-24. The bar was written first
(`MODEL_BARS.md` §9, model 18). The design choices were made by the user:

- both outputs (outlook and forecast);
- weekly, per Karnataka district with a state fallback;
- 13 weeks ahead;
- the six app-crop commodities plus common field crops.

**Data.** 1,604,891 rows of the 13 commodities were read (all India). The
cleaning removed:

- 38,478 duplicates;
- 10,484 inconsistent rows (min > max, or modal outside [min, max]);
- 1,520 outliers, more than 3x from the all-India weekly median.

That leaves 57,497 Karnataka rows, forming 196 weekly periods. **136 series**
are modelled: 123 district series meeting the 40% rule, plus 13 state series.

**Split by target week.** Training rows 11,051. Validation: 836 rows, targets
from 2025-09-29. Test: 1,382 rows, targets 2026-03-30 to 2026-09-21, read once.
Gradient boosting (median loss) predicts the log change over 13 weeks. The
"shallow" setting was chosen on validation.

**Pooled test result:**

- MAE 0.1324 against persistence 0.1522, and against
  seasonal-naive 0.1515 on the 283 rows where
  it exists;
- **direction accuracy 0.719** on 1094 moves of 5%
  or more (bar 0.60).

**Per crop** (MAE in log price, which is roughly fractional error; the bar is
ratio <= 0.90 and model <= seasonal-naive):

| Crop | Test rows | MAE | Persistence | Ratio | Model vs seasonal-naive (shared rows) | Direction | Verdict |
|---|---|---|---|---|---|---|---|
| bajra | 107 | 0.1030 | 0.1201 | 0.858 | 0.0637 vs 0.0898 | 0.767 | **ships** |
| bengal_gram | 198 | 0.0842 | 0.0969 | 0.868 | 0.0803 vs 0.1360 | 0.800 | **ships** |
| cotton | 85 | 0.1555 | 0.1769 | 0.879 | 0.1195 vs 0.1275 | 0.575 | **ships** |
| groundnut | 169 | 0.1425 | 0.1681 | 0.848 | 0.1379 vs 0.1686 | 0.779 | **ships** |
| jaggery | 60 | 0.0942 | 0.1015 | 0.929 | 0.0934 vs 0.1598 | 0.659 | fails |
| jowar | 142 | 0.1606 | 0.1913 | 0.840 | 0.1246 vs 0.1983 | 0.701 | **ships** |
| maize | 293 | 0.1302 | 0.1600 | 0.814 | 0.1188 vs 0.1428 | 0.804 | **ships** |
| rice | 121 | 0.1501 | 0.1710 | 0.878 | 0.1165 vs 0.1883 | 0.680 | **ships** |
| soyabean | 112 | 0.1833 | 0.1750 | 1.048 | 0.1976 vs 0.1304 | 0.442 | fails |
| wheat | 95 | 0.1337 | 0.1525 | 0.876 | 0.1074 vs 0.1780 | 0.757 | **ships** |

**Ships:** bajra, bengal gram, cotton, groundnut, jowar, maize, rice and wheat.

**Does not ship:**

- **Jaggery** fails: ratio 0.929.
- **Soyabean** fails: it is worse than persistence, and direction is 0.442.
- **Paddy, ragi and arhar have no verdict.** Their Karnataka markets report no
  prices in the test target months (April-September), so they have no test rows.
  Paddy and ragi are app crops; for them, only the seasonal outlook is served.

**Cautions that travel with the pass:**

- **Validation disagrees with test.** On the validation half-season (targets
  October 2025 to March 2026), the chosen model had MAE 0.1477 against
  persistence 0.1502, only 1.7% better, and direction
  0.590. Both would **fail** the bar. The pass rests on
  a single half-season, April-September 2026, that suited the model. This is
  the limit stated in the bar, and it shows.
- **"Rice" is milled rice.** Paddy, which farmers sell, has no verdict.
- **Test points are correlated.** The 13-week horizons overlap, so the
  effective sample is much smaller than 1,382.
- **Seasonal-naive rests on fewer rows.** Its comparison uses only the
  283 test rows where last year's prices were observed.

**Seasonal outlook (18s).** It covers every modelled series, from training and
validation weeks. On the test weeks, **35.6%** of
actual prices fell inside the historical IQR, against 50% if calibrated. The
2026 prices moved outside their 2023-25 ranges, so the outlook is served as
"historical ranges", never as an expectation.

**Serving:** `price_outlook(commodity, district)` in
`ml/algorithms/price_forecast.py`.

- It always returns the seasonal outlook.
- It returns a forecast only for the 8 shipped commodities:
  - the current price, the expected price in 13 weeks, and a range of plus or
    minus that crop's test MAE;
  - a direction (up, down, or flat within 5%);
  - the origin week, and caveats.
- It falls back to Karnataka when the district has no modelled series.
- No sell/hold recommendation is made.

Verified: maize in Davangere gets a district forecast; an unknown district
falls back to state; paddy and soyabean get the outlook only; tomato is
refused.

**Staleness.** Forecasts start from the dataset's last week (2026-09-21).
Serving newer forecasts needs the dataset refreshed and the script re-run.
Re-running also re-reads a new test fold, so each refresh is a fresh verdict.

---

## 19. Vegetable variety/size classifier — DOES NOT SHIP

Dataset `datasets/Vegetables Image Dataset for Machine Applications`, with 14
folders of harvested produce (`DATASETS_STATUS.md` §2.16). Trained at the
user's request as the full-class model; the bar was written first
(`MODEL_BARS.md` §9, model 19). The user states that same-named images differ.

**Measured.**

- Of the 6,418 file names found in more than one folder, **6,331 are
  byte-identical** (same size, same SHA-256, 0 differing pixels) and 87
  genuinely differ.
- Examples, each shown to the user with its hash:
  - `IMG_20250406_152930_aug_238.jpg` in Beans Long and Beans Short;
  - `IMG_20250406_160735_aug_40.jpg`, a tomato, in Okra Long and Tomato
    Regular;
  - `IMG_20250406_152450_aug_583.jpg` in Chili Jipoor and Chili Sitara.

**Pipeline.** The standard leaf pipeline was used:

- 22,804 images collapse to 12,445 distinct;
- **6,329 duplicate groups (16,623 images) carrying more than one label were
  dropped**, while the 87 genuinely different images kept their labels;
- sessions come from the capture time in the file name: 116 groups.

**Unmeasurable classes.** Five classes were left with fewer than 5 sessions:
Beans Long (10 images), Chili Sitara (6), Chili Jipoor (13), Potato small (13)
and Tomato Regular (0). They were excluded from training and fail their recall
criterion, as the bar states.

**Run.** Nine classes were trained, with split train 3,348 / val 1,401 / test
1,390. Phase B was selected (validation macro-F1 0.6994).

| Metric | Bar | Measured |
|---|---|---|
| Macro-F1 (9 measurable classes) | >= 0.85 | **0.6657** |
| Class recall >= 0.70 | all 14 | 7 of 14 pass |

- **Pass:** Beans Short 0.986, Chili Jwala 0.957, Cucumber Gaavran 0.819,
  Cucumber Regular 0.958, Okra Long 0.793, Potato Large 1.000, Potato medium
  0.752.
- **Fail:** Okra Short and Tomato Gaavran have 3 test images each, and both
  score 0. The five unmeasurable classes also fail.
- **Other figures:** accuracy 0.892 (majority baseline 0.390); vegetable-type
  accuracy 0.955.

**Cause category: data (labels).** Once one-image-one-label is enforced, the
dataset no longer supports half its classes. The artifact records `passed_bar:
False` and `served: False`, and there is no serving module.

---

## 20-28. Seven datasets supplied 2026-09-25 — all nine clear their bars, provisional

The bars and every grouping rule were written first (`MODEL_BARS.md` §9, three
2026-09-25 entries: the models, the calibration corrections, and the onion
cap). Models 20-27 use the leaf pipeline (256 px, two-phase MobileNetV3-Large,
60/20/20 by group). **Phase B was selected on validation for all eight.** Model
28 has its own script, using 384 px crops from 1,536 px photos scored over a
grid. The user decisions were:

- train all nine, one after the other;
- serve later;
- keep every file, grouping copies and variants with their source;
- cap onion at 1,500 images per class to save CPU time.

**None of these crops is a seeded app crop except wheat.** Every response
carries `is_seeded_crop`. The models serve through the existing
`diagnose_leaf` / `/v1/images/leaf` path (and `assess_wheat_kernels` for 28).
Since 2026-09-26 the six crops are app crops and models 20-27 are served
(`ML_SERVING_INTEGRATION.md` §3 and §4). **Model 28 is held** from serving by
`ml/serving/holds.py` until the lighting check below is done.

| # | Task | Test images | Val → test macro-F1 | Test macro-F1 | Healthy precision | Train min |
|---|---|---|---|---|---|---|
| 20 | coffee | 641 | 0.983 → 0.962 | 0.9619 | 0.9774 | 10.6 |
| 21 | tea | 7,029 | 0.994 → 0.991 | 0.9909 | 0.9901 | 117.1 |
| 22 | cauliflower leaf | 204 | 0.995 → 0.995 | 0.9952 | 1.0000 | 2.8 |
| 23 | cauliflower curd | 332 | 0.989 → 0.994 | 0.9936 | 1.0000 | 5.1 |
| 24 | onion leaf (capped) | 601 | 0.927 → 0.968 | 0.9684 | 0.9608 | 11.8 |
| 25 | onion bulb (capped) | 600 | 0.997 → 0.993 | 0.9933 | 0.9901 | 10.2 |
| 26 | potato | 430 | 0.994 → 0.979 | 0.9794 | 0.9355 | 5.3 |
| 27 | tomato fruit | 1,446 | 0.983 → 0.984 | 0.9837 | n/a | 26.8 |
| 28 | wheat kernels | 34 | 1.000 → 1.000 | 1.0000 | 1.0000 | about 25 |

Every class recall clears 0.70; the lowest is coffee leaf rust at 0.907.

**Leakage audit after the runs** (`audit_leaf_scene_leakage.py`, nearest
training image of each test image on untuned ImageNet features):

| Task | Near-copy (>= 0.97) | Accuracy on test images with no close training neighbour (< 0.92) |
|---|---|---|
| coffee | 0 | 0.960 (94.2% of test) |
| tea | 0 | 0.991 (94.1%) |
| cauliflower leaf | 0 | 0.994 (87.3%) |
| cauliflower curd | 11 (3.3%) | 0.972 (**only 21.4%**) |
| onion leaf | 0 | 0.968 (97.2%) |
| onion bulb | 0 | 0.993 (97.8%) |
| potato | 0 | 0.990 (96.5%) |
| tomato fruit | 3 (0.2%) | 0.986 (53.9%) |

**No model depends on near-copies.**

**Per-model cautions:**

- **Tea: HEIC format is not a shortcut.** The 1,221 HEIC files are 300x450 and
  appear only in Fresh and Red Spider. On the 6,721 JPG test images, which
  cover all three classes, accuracy is 0.9905. The 308 HEIC test images score
  1.000, but they cover two classes, so format cannot separate them. Of 35,299
  files, 25,653 are distinct. They come from 3,097 source photos (each with up
  to 11 processed variants, grouped together), forming 2,000 capture sessions.
  One content filed under two labels was dropped (151 files).
- **Coffee.** 102 files are empty (0 bytes) and were skipped. 437 images are
  stored 2-24 times and are grouped. One content in both leaf rust and phoma
  was dropped (18 files). The main confusion is rust called phoma (15 of 204).
- **Cauliflower curd.** The photos are very alike: random same-class pairs have
  median similarity 0.795. Only 71 test images lack a close training neighbour,
  though accuracy on them is 0.972. It was grouped by complete linkage at 0.95,
  because single linkage chained whole classes. Alternaria has 9 test images.
- **Tomato fruit.** Each image is saved as both jpg and png; the pairs are
  merged by stem. The shipped split, which leaked, was discarded. It was
  grouped by complete linkage at 0.93. The main confusion is Old vs Damaged.
  Grades are served without the symptom gate.
- **Onion (24, 25).**
  - Both train on capped samples of 3,000 images, from 6,172 leaf and 17,828
    bulb images.
  - "Unhealthy" names no cause.
  - Onion leaf has only 15-16 test sessions per class, and its validation score
    (0.927) sits below test.
- **Potato.** PlantVillage lab photos. Healthy precision is 0.9355 (29 of 31)
  on 30 healthy test images. Early and late blight link to the Q&A corpus.
- **Wheat kernels (28): the pass cannot be attributed to damage detection.**
  - Photos from the same cultivar and label are much more alike (0.912) than
    across labels (0.811).
  - **Average photo colour alone (3 numbers per photo) classifies the same 34
    test photos at 0.941**, and at 0.959 in 5-fold cross-validation. Damaged
    photos average RGB (140, 126, 114) against (129, 112, 96) for healthy.
  - That may be a real symptom, since sunn-pest damage leaves kernels paler,
    or a capture-lighting artefact. This data cannot separate the two.
  - The bar (written first, against a majority baseline) is passed and not
    moved. **Before this model is served, it should be checked on grain photos
    taken under different lighting.**

---

## Enforcement

A failed bar is enforced mechanically, not by documentation. Training records
`passed_bar` in every artifact, and `ml/algorithms/_loader.py` raises
`ModelDidNotShip` rather than returning one that failed. Serving a failed model
requires deleting that check, which is a conversation rather than an oversight.
