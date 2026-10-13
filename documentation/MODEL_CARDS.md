# Model cards

One card per shipped model. Numbers come from [`ml/MODEL_RESULTS.md`](../ml/MODEL_RESULTS.md), which is the source of truth; the acceptance bars were written before training and are in [`ml/MODEL_BARS.md`](../ml/MODEL_BARS.md). Read this file together with [DISCLAIMER.md](../DISCLAIMER.md).

## Read this first

- **Every model is provisional.** No model has been reviewed by an agronomist. The serving layer cannot label any output `verified`; that label would mean a human expert signed it off.
- **Confidence is shown as a label** (`unverified`, `provisional`, `verified`), never as a percentage. No probability crosses the API.
- **Models never write prose or product names.** Fertilizer products and dosages come from the `agri_catalog` table.
- **A model that fails its bar cannot be served.** The loader raises `ModelDidNotShip` (HTTP 409).
- **Each shipped model was scored once on a test set that no tuning decision had seen**, except where a card says otherwise.
- **Training data provenance and licences are mostly unverified** (see [`DATASETS_STATUS.md`](../DATASETS_STATUS.md)). Only the insect dataset (model 11) has a recorded licence, CC BY 4.0.
- **Lab or curated photos** underlie most image models. Accuracy on real field photos has not been measured.

**Status key.** *Served* means reachable through the app today. *Held* means it cleared its bar but is blocked in code. `ml/MODEL_RESULTS.md` lists model 28 as "ships"; the serving layer holds it (see its card). 21 of the 22 models that cleared their bars are served.

| # | Model | Kind | Status |
|---|---|---|---|
| 1 | Crop recommendation | tabular | served |
| 2 | Crop from soil type | tabular | served |
| 3 | Fertilizer targets | lookup | served |
| 4b | Disease Q&A, crop-scoped | retrieval | served |
| 5b | Soil fertility class | tabular | served |
| 6 | Yield outlook | tabular | served |
| 7b | Soil type from photo | image | served |
| 11 | Insect detection | image | served |
| 12 | Rice disease type | image | served |
| 13 | Pearl millet disease type | image | served |
| 14b | Wheat heading | image | served |
| 17 | Tobacco lesion severity | image | served |
| 18 | Mandi price outlook | tabular | served (8 crops) |
| 20-27 | Leaf, curd, bulb and fruit classifiers | image | served |
| 28 | Wheat kernel damage | image | **held** |

---

## 1. Crop recommendation

- **Task:** suggest crops from soil N, P, K and weather.
- **Training data:** `merged_crop_dataset.csv`, 6,596 rows, 51 crop classes. Synthetic and highly separable; source unrecorded. Stratified 60/20/20 split.
- **Intended use:** a shortlist of crops to consider when adding a planting.
- **Bar and result (test):** weighted-F1 at least 0.90 → **0.9970**; recall at least 0.85 for the seeded crops → 0.90 to 1.00. Majority baseline 0.0697.
- **Limitations:** the near-perfect score shows the pipeline works, not agronomic skill. Sugarcane is not among the 51 labels, so this model can never recommend it. Some classes have under 50 rows (pumpkin has 7).
- **Out of scope:** recommending sugarcane; any decision about what to plant without local advice.
- **App shows:** crop fit labels in the add-planting screen, with a note saying whether a soil test, the soil type or estimated averages were used.

## 2. Crop from soil type

- **Task:** suggest crops from soil type plus weather.
- **Training data:** `crop_soil_type_dataset.csv`, 3,100 rows, 31 crops, exactly 100 per class (a sign of synthetic generation). 60/20/20 split.
- **Intended use:** a top-3 shortlist, not a verdict. It can reach sugarcane, which model 1 cannot.
- **Bar and result (test):** macro-F1 at least 0.75 → **0.9724**. Majority baseline 0.0323.
- **Limitations:** the score overstates real performance because the data is uniform and synthetic.
- **Out of scope:** definitive crop choice.

## 3. Fertilizer targets

- **Task:** look up target N, P, K and a pH range for a crop. This is a lookup table, not a trained model.
- **Training data:** `Fertilizer.csv`, 1,843 rows collapsing to 97 crops (N, P, K are constant per crop). The file is synthetically expanded.
- **Bar and result:** the check that N, P, K are constant per crop passes for all 97 crops.
- **Limitations:** no sugarcane row. Only cotton, maize, ragi and rice of the originally seeded crops are covered. Where a soil test is missing, the app falls back to a state average and says so.
- **Out of scope:** product choice or dosage (those come from `agri_catalog`).
- **App shows:** a "Nutrient check" with its basis (soil test or state average).

## 4b. Disease Q&A, crop-scoped

- **Task:** retrieve documented diseases and remedies for a crop from a symptom description (character n-gram retrieval).
- **Training data:** the Indian Crop Disease Hindi and Marathi NLP CSV: 2,231 rows, 88 crop and disease pairs, 11 crops, text in English, Hindi and Marathi.
- **Bar and result (test):** recall@3 at least 0.75 → **0.7614**; recall@1 at least 0.55 → **0.6220**. Chance within a crop is 0.375 and 0.125.
- **Shipping condition:** the app must always offer the full list of diseases for the crop. If the shortlist ever becomes the only route, the bar must be raised first. The diseases screen keeps that list visible.
- **Limitations:** 6.1% of question texts belong to more than one disease pair (flagged `shared_symptom`). Some Hindi remedies are English fallbacks. No ragi coverage. Only three languages exist against the app's ten.
- **Companion model 4 (unscoped)** failed its bar (0.5447 / 0.4356) and is not served.

## 5b. Soil fertility class

- **Task:** rate soil as Low, Medium or High fertility from the 12 soil-card values (N, P, K, pH, EC, organic carbon, S, Zn, Fe, Cu, Mn, B).
- **Training data:** a Karnataka file (1,831 rows) and a pan-India file (3,805 rows), 5,636 samples from 4,605 fields, split by field. **Provenance is unverified.**
- **Bar and result (test):** macro-F1 at least 0.75 → **0.9808**; recall(High) at least 0.50 → 0.9776; Karnataka slice → 0.9743. Majority baseline 0.3706.
- **Limitations:** the class is an exact cut of a nutrient index computed from the same values, so the model learns the rating formula and the near-perfect score is expected. It says what a lab-style rating would be, not what to apply or what yield to expect. All 12 values are required; missing ones are named in the response.
- **Out of scope:** fertilizer recommendation; yield prediction.
- **App shows:** the class, with "The rating a soil lab would give these values. It is not a fertilizer recommendation." and a note that the training data's source is unverified.
- **Replaces model 5**, which failed its bar (0.6944).

## 6. Yield outlook

- **Task:** place a crop's expected yield as a percentile band against past records.
- **Training data:** `crop_yield.csv` (19,689 rows, 1997-2020) joined with state weather. Split by year: train 1997-2014, validation 2015-17, test 2018-20.
- **Bar and result (test):** MAE at least 10% better than a median baseline → national **+21.9%**, Karnataka **+87.5%**; R² at least 0.60 → 0.9495. The test fold was read twice (raw, then after a fix).
- **Limitations:** the `yield` column has no unit that applies across crops, so **no number is ever shown**, only "Above / Around / Below / Well below typical". Records end in 2014 for training; later years use average weather. Logged inputs are not used; typical rates are. The R² bar was too lenient (the baseline alone reaches 0.9189); the MAE bar did the real work.
- **Out of scope:** tonnes-per-hectare forecasts; this-season weather effects.

## 7b. Soil type from photo

- **Task:** classify a soil photo as Alluvial, Black, Red or Cinder.
- **Model:** MobileNetV3 transfer learning (7a, a classical-CV model, also cleared the bar but is not used).
- **Training data:** a soil image set, 295 train and 73 test images. 56 training images (19%) were near-duplicates of test images and were removed; about 183 distinct training photographs remain.
- **Bar and result (test):** accuracy at least 0.80 and recall at least 0.60 for Alluvial, Black and Red → **accuracy 0.9726**. Majority baseline 0.5342.
- **Limitations:** Cinder has only 6 test images, so its recall is poorly measured. Cinder cannot be mapped to the crop model's vocabulary.
- **Intended use:** to prefill the soil-type picker. It never replaces the district lookup.
- **App shows:** "Photo suggests: {soil}", or asks the farmer to choose manually.

## 11. Insect pest detection

- **Task:** detect and name a pest in a close-up insect photo (YOLOv8n).
- **Training data:** Roboflow RF100 "insects" v2, **CC BY 4.0**, 995 images, 10 classes, tight 224 px crops of about one insect each. Split 681 / 198 / 100.
- **Bar and result (test, read once):** identification macro-F1 at least 0.85 → **0.9005**; per-class recall at least 0.70 for the app's classes → 0.71 to 1.00; mAP@0.5 at least 0.70 → **0.9384**.
- **Limitations:** 5 to 17 test images per class; planthopper passed at 5 of 7. The model has never seen field photos, several insects at once, or photos with no insect. An empty result means "no detection", not "no insect". The links between pests and host crops are unverified.
- **Crops offered:** rice, maize, cotton (red spider) and wheat (thrips).
- **Out of scope:** wide field photos; counting insects on traps.
- **App shows:** boxes, a pest name and a confidence label; the hint "Photograph one insect, close up."

## 12. Rice disease type (conditional)

- **Task:** name the disease on a rice leaf: bacterial blight, blast, brown spot or tungro.
- **Training data:** 5,932 images that are about 1,094 distinct photos. Split by similarity group.
- **Bar and result (test):** macro-F1 at least 0.85 → **0.8993**; every class recall at least 0.70 → 0.80 to 1.00.
- **History:** a first run scored 0.9655 but 18.8% of its test images had near-copies in training; it was retrained on a corrected split and 0.9655 is not the result.
- **Limitations:** **there is no healthy class.** A healthy leaf would be named as one of the four diseases, so the app only runs it after the farmer ticks "I can see disease symptoms" and always offers "None of these match". Validation to test gap of 0.058: expect field accuracy below 0.90. Tungro rests on 8 groups.
- **Out of scope:** telling whether a leaf is healthy.

## 13. Pearl millet (bajra) disease type (conditional)

- **Task:** blast versus rust on pearl millet leaves.
- **Training data:** 4,985 files, about 4,669 distinct photos from 84 sessions. The Healthy folder was excluded because it comes from a different source.
- **Bar and result (test):** macro-F1 at least 0.85 → **0.9377**; recall Blast 0.9130, Rust 0.9757.
- **Limitations:** 8 test sessions per class; one source and one camera. No disease Q&A entries exist for millet. Same symptom gate as rice. This is pearl millet, **not ragi**.

## 14b. Wheat heading detection

- **Task:** say whether wheat heads are visible in a top-down canopy photo (LR-ASPP segmentation; only the heading output is used).
- **Training data:** a 40% download of GlobalWheat GWFSS (438 images), 277 / 69 / 88 split.
- **Bar and result (test):** heading balanced accuracy at least 0.85 → **0.9848**; head IoU at least 0.60 → 0.6759.
- **Limitations:** **the bar was written after the test set was read**, so this has a declared selection bias. Only 33 unheaded test images. The joint model (14) failed on canopy cover (MAE 0.0756 against a 0.05 bar), so cover is never shown.
- **Out of scope:** canopy cover; side-on phone photos.
- **App shows:** "Heads are visible" or "No heads found. This does not prove heading has not started."

## 17. Tobacco leaf lesion severity

- **Task:** estimate the share of a leaf covered by lesions (segmentation). It names no disease.
- **Training data:** a 40% subset of a Kaggle tobacco leaf segmentation set, 1,400 tiles from 84 photos, rebuilt into folds by capture session (56 sessions) after the shipped split leaked.
- **Bar and result (test):** lesion IoU at least 0.50 → **0.5568**; lesion-share error at most 50% of baseline → 24.8%.
- **Limitations:** validation IoU was 0.673, test 0.557. It over-estimates lesion share by about a third. Photos come from two days and one source.
- **App shows:** "About n% of the leaf shows lesions" with the over-estimate warning.

## 18. Mandi price outlook (Karnataka)

- **Task:** 13-week-ahead price direction and range per commodity, plus an always-on seasonal outlook.
- **Training data:** Agmarknet daily prices, 2023-01 to 2026-09; 57,497 Karnataka rows after cleaning, 136 weekly series.
- **Bar:** per commodity, MAE at least 10% below "price stays the same" and no worse than seasonal-naive; pooled direction at least 0.60.
- **Result (test):** **8 of 13 commodities pass** (bajra, bengal gram, cotton, groundnut, jowar, maize, rice, wheat); jaggery and soyabean fail; paddy, ragi and arhar have no test rows. Pooled direction accuracy 0.719.
- **Limitations:** validation disagreed with test (validation MAE only 1.7% better than persistence, direction 0.590, which would fail); the pass rests on one half-season. "Rice" is milled rice, not paddy. Karnataka only. The seasonal-range view is history, not a forecast, and only 35.6% of 2026 prices fell inside its stated range.
- **Out of scope:** sell or hold advice; other states; sugarcane.
- **App shows:** "Likely to rise / fall / stay about the same", a range, the last recorded price, or "No tested forecast for this crop. Past price ranges only."

## 20-27. Leaf, curd, bulb and fruit classifiers

All use two-phase MobileNetV3-Large, 256 px images, a 60/20/20 split by similarity group, and the "leaf bar": macro-F1 at least 0.85, every class recall at least 0.70, and healthy precision at least 0.90 where a healthy class exists. Each is a single source and a single capture set, so all ship provisional. They are one model per crop and part, and the crop must be known.

| # | Task and classes | Test images | Macro-F1 (test) | Recall range | Notes |
|---|---|---|---|---|---|
| 20 | Coffee leaf: healthy, leaf rust, phoma | 641 | 0.9619 | 0.907-1.000 | Rust is called phoma 15 of 204 times |
| 21 | Tea leaf: fresh, Helopeltis, red spider mite | 7,029 | 0.9909 | 0.990-0.993 | Trained about 2 hours |
| 22 | Cauliflower leaf: Alternaria spot, downy mildew, healthy | 204 | 0.9952 | 0.984-1.000 | Small test set |
| 23 | Cauliflower curd, 6 classes | 332 | 0.9936 | 0.976-1.000 | Photos very alike; Alternaria has 9 test images |
| 24 | Onion leaf: healthy, unhealthy | 601 | 0.9684 | 0.960-0.977 | Capped sample; names no cause |
| 25 | Onion bulb: healthy, unhealthy | 600 | 0.9933 | 0.990-0.997 | Capped sample; names no cause |
| 26 | Potato leaf: early blight, late blight, healthy | 430 | 0.9794 | 0.967-1.000 | Lab photos (PlantVillage); healthy precision 0.9355 on 30 images |
| 27 | Tomato fruit grade: damaged, old, ripe, unripe | 1,446 | 0.9837 | 0.971-0.998 | Main confusion is Old versus Damaged |

- **Intended use:** a "what might this be" photo check with ranked alternatives and "None of these match".
- **Limitations (all):** lab or curated photos; field transfer unmeasured; "unhealthy" in 24 and 25 is a flag, not a diagnosis; leakage audits found 0 near-copies except curd (3.3%) and tomato fruit (0.2%).
- **Out of scope:** diagnosing anything outside the listed classes; any crop other than the one the model was trained for.

---

## 28. Wheat kernel sunn-pest damage: HELD

- **Task:** damaged versus undamaged wheat kernels in a photo of grain.
- **Result:** macro-F1 1.0000 on 34 photos, which clears the bar.
- **Why it is held:** **average colour alone scores 0.941 on the same 34 photos** (0.959 in cross-validation). The data cannot separate a real symptom (paler damaged kernels) from a lighting difference between how damaged and healthy grain was photographed.
- **Enforcement:** `ml/serving/holds.py` blocks it. The capabilities endpoint reports `awaiting_lighting_check`, so the app never offers it, and a direct call returns 409 `model_on_hold`.
- **To release:** run a lighting check on grain photographed under varied light, record it in `MODEL_RESULTS.md`, then remove the hold.

---

## Models that are not served

| # | Model | Why not |
|---|---|---|
| 4 | Disease Q&A, unscoped | Failed bar (recall@3 0.5447 against 0.70) |
| 5 | Soil fertility (original) | Failed bar (macro-F1 0.6944 against 0.75); replaced by 5b |
| 10 | Sugarcane leaf condition | Failed bar (macro-F1 0.5248 against 0.85); memorised capture sessions |
| 14 | Wheat canopy segmentation (joint) | Failed on cover (MAE 0.0756 against 0.05); heading alone ships as 14b |
| 15 | Soybean seed yield | Failed bar (R² 0.1449; MAE 1.9% worse than baseline) |
| 16 | Sugarcane yield | Cleared its bar but is trained on synthetic data, so it is never served |
| 19 | Vegetable variety and size | Failed bar (macro-F1 0.6657; 7 of 14 recalls fail) |

Models for which no usable data exists were never trained; see [`ml/PARKED_MODELS.md`](../ml/PARKED_MODELS.md).
