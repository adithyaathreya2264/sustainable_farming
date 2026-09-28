# Unblocking the parked models

Companion to `PARKED_MODELS.md`, which says *why* each model was not trained.
This says *what specifically has to exist* before retraining is worth
attempting again, ordered by how close each one already is.

The app itself is a candidate data source for two of these — it already logs
`scouting_observations`, `interventions` and `plantings` — and where that is
true, this document says so concretely rather than gesturing at "more data".
Where the app cannot plausibly become the source (YOLO disease segmentation),
it says that too, so effort isn't spent waiting on a source that will never
arrive.

---

## 1. Disease from photograph

### Update 2026-09-23: photos were not enough — independent sessions are the unit

A sugarcane leaf dataset arrived and was trained (`MODEL_RESULTS.md` §10). It
failed, and *how* it failed changes what "unblocked" means for every crop.

**What was learned.** The dataset was shot in continuous streams: thousands of
photos, but only 216 independent capture sessions. Evaluated on sessions the
model had never seen, which is what a farmer's upload always is, it scored
0.52. Split by photo, it had scored 0.98. **Image count was the wrong measure of
how much data there is.**

What the per-class results show:

- Visually distinctive conditions generalised from few sessions: sett rot
  (14 sessions, recall 0.98), grassy shoot (9, 0.97).
- Conditions that resemble another failed, whatever the session count: brown
  spot (51 sessions, 0.61) and yellow leaf (41, 0.32).
- Many sessions did not rescue the well-sampled classes. That points at label
  quality as much as quantity: the same dataset files 294 photos under two
  different labels (`DATASETS_STATUS.md` §2.8).

**So what unblocks it, specifically:**

1. **A label audit before any new photos.** Retraining on more images carrying
   the same labels will not fix classes that fail with 41-51 sessions. An
   agronomist should review a sample of the confused classes (Dried Leaves vs
   Banded Chlorosis vs Yellow Leaf; Pokkah Boeng vs Brown Spot vs smut) to
   establish whether the folders are reliable. Until then, a sugarcane leaf
   model cannot be trusted whatever it scores.
2. **For every crop, keep EXIF capture metadata.** It is what made the session
   split possible at all. A dataset stripped of timestamps cannot be split
   honestly, and would produce exactly the inflated 0.98 seen here.

**Already built and waiting**: the training pipeline (with session-grouped
splitting and the duplicate and label-conflict checks), the class registry,
and a serving module that returns categories and Q&A links instead of raw
labels. A new crop needs two small edits, not new code: its class folders
registered in `ml/leaf_conditions.py`, and its dataset root added to
`LEAF_IMAGE_ROOTS` in `ml/paths.py`.

### Update 2026-09-23 (later): rice and insects are data-unblocked, not finished

A rice leaf dataset and an insect YOLO dataset arrived. Neither is blocked on
data any more. Both runs were stopped before their test reads; the insect
detector was resumed on 2026-09-24 and **ships, provisional**
(`MODEL_RESULTS.md` §11). Rice was retrained on 2026-09-24 and also **ships,
provisional** (`MODEL_RESULTS.md` §12). Rice still has no healthy class, so any rice model
stays conditional. Ragi and maize still have no leaf dataset.

### Original entry (2026-09-22)

**Blocked on:** leaf images for rice, ragi, cotton and sugarcane, each with a
healthy-crop class. Not a technique gap — transfer learning and augmentation
are both viable here (verified during the soil-type work: pretrained weights
download fine in this environment), so once images exist, training is a
day's work, not a research problem.

**Quantity to aim for.** PlantDoc's maize classes (64-179 images) reached
usable numbers with transfer learning on the soil-type task, which had 4
classes and roughly 40-155 images per class. A reasonable floor per (crop,
disease) class is **100-150 images**, plus a genuine healthy-crop class per
crop of similar size — without it the model can never say "this looks
fine", only "which disease does this most resemble," which is worse than no
answer. *(Superseded by the 2026-09-23 update above: image counts
proved to be the wrong measure. What matters is the number of independent
capture sessions, and label quality.)*

**Where images could come from, roughly in order of realism:**

1. **The app itself, eventually.** `scouting_observations` already exists
   and is tied to a `planting_id` (crop known) and `observed_at` (season
   known). It has no image column today, and nothing in the frontend
   captures a photo (no `expo-camera` or `ImagePicker` usage exists
   anywhere in the app, confirmed by a full search of the app's package
   dependencies and source tree). Adding photo capture to scouting logs
   would, over enough users and enough seasons, become the single
   best-fit source,
   because it is the exact population (Karnataka farmers, these five
   crops, real field conditions) the model needs to be right for. This is
   a **product decision** before it is an ML one — a storage/upload path,
   consent for using farmer photos in training, and a redaction pass
   (fields sometimes have people or license plates in frame) all have to
   exist first.
2. **Public agricultural image datasets scoped to these crops.** Search
   terms worth checking specifically: rice leaf disease dataset, sugarcane
   leaf disease dataset, finger millet / ragi blast dataset, cotton leaf
   disease dataset (Kaggle, Mendeley Data, and ICAR/KVK institutional
   repositories are the most likely hosts). Ragi is the highest-risk gap —
   it is a comparatively under-photographed crop globally, so it may be
   the one that has to come from source 1 or 3 with no public shortcut.
3. **A manual collection pass** — photographing known-disease and
   known-healthy plants at a KVK, agricultural university plot, or partner
   farm, with a domain expert present to label them correctly at capture
   time rather than after the fact. Slower, but produces the
   highest-confidence labels of the three options, and is the only one
   that can specifically target ragi.

**What does not unblock this:** more PlantDoc training, better
augmentation, or a larger model. The ceiling is the absence of the four
crops in the data, not model capacity.

---

## 2. Disease presence and insect presence questionnaires

**Blocked on:** real presence/absence observations for the five seeded
crops, with an explicit "not asked" state distinct from "No".

**This is the one closest to being unblocked by the app's own design, not a
hypothetical future feature.** `scouting_observations` already stores
`metric_key` / `metric_value` pairs against a `planting_id`, and the
agronomic rule engine already defines real metric keys tied to real pest
thresholds for these exact five crops:

| Crop | metric_key | Source |
|---|---|---|
| Rice | `dead_hearts_percent` | `RICE_STEM_BORER_SCOUT` |
| Sugarcane | `deadheart_percent` | `SUGARCANE_EARLY_SHOOT_BORER` |
| Cotton | `pheromone_trap_moths_per_night_3day_avg` | `COTTON_PBW_ETL` |
| Maize | `percent_plants_with_whorl_damage` | `MAIZE_FAW_ETL` |

(from `backend/scripts/reference-data.json`, `agronomic_rules`)

These are continuous field measurements, not yes/no questionnaire answers,
so they are not a drop-in replacement for the inherited 30-question format —
but they are exactly the kind of real, farm-conditions signal the synthetic
150-row files lack, and they already cover 4 of 5 crops. As
`scouting_observations` accumulates real rows over seasons, there is a
genuine path to either (a) training a presence/severity classifier directly
off these continuous metrics instead of yes/no answers, which is arguably a
better-posed problem than the inherited one, or (b) redesigning a
yes/no-style checklist around symptoms actually described in the disease
Q&A corpus (which does cover rice, maize, cotton, sugarcane — see
`ml/MODEL_RESULTS.md` section 4b) and logging farmer answers to it as new
scouting metric_keys.

**What's still missing regardless of path:** a genuine unanswered state.
The inherited bug — "not asked" silently scored as "No" — has to be designed
out from the start; `scouting_observations.metric_value` being simply absent
for a `metric_key` already gives this for free (no row means not observed,
rather than a row recording a false negative), which is a real improvement
over the inherited CSV format if this path is taken.

**Realistic timeline:** this depends on scouting adoption, not engineering
effort. If scouting logging becomes a regular habit for even a few hundred
active plantings across a season, the continuous-metric version (path a
above) becomes trainable. A few dozen logs will not be — the inherited
150-row synthetic file was itself too small for 30 features, and continuous
agronomic thresholds need enough spread across pest-pressure levels to learn
anything, not just enough rows.

---

## 3. YOLO disease segmentation

**Blocked on:** a real annotated disease segmentation or detection dataset.
This is the least likely item to become app-sourced, because polygon or
bounding-box annotation needs tooling and labelling effort well beyond what a
farmer does while scouting a field.

**What's needed, concretely:**
- A `data.yaml` (YOLO's class list plus train/val path manifest). None exists
  for `crop_diseases_yolo`.
- Materially more than the roughly 50 images the inherited set had. Low
  hundreds of annotated images per class is a realistic floor, even with
  transfer learning.
- Real polygon or multi-box labels, not the single-box-per-image labels the
  inherited set mostly had (most label files are 38 bytes).

**Realistic path:** a public disease segmentation dataset scoped to the app's
crops (Kaggle and Roboflow Universe host many pre-annotated agricultural sets).
If nothing scoped to the app's crops turns up, this should stay parked rather
than be trained on off-target classes, the mistake the PlantDoc entry above
describes.

Two things no longer block it: `ultralytics` is installed and pinned in
`ml/requirements.txt`, and the YOLO training path works (the insect detector,
model 11, was trained with it).

---

## Cross-cutting: what changes if or when scouting data starts to accumulate

Two of the three parked items (1 and 2) have a real, non-hypothetical path
through the app's own data model, but only once specific product
prerequisites exist:

- **Photo capture in scouting logs** (for item 1) — does not exist yet.
  Needs a schema column, an upload/storage path, and a consent-and-redaction
  decision before a single training image can come from it.
- **Sustained scouting adoption** (for item 2) — the metric_keys already
  exist in the rule engine and schema; what is missing is volume. This is
  worth checking on periodically (for example, how many distinct plantings
  have three or more scouting_observations logged this season) rather than
  assumed to have arrived.

Neither of these should be treated as solved by this document. They are the
two items where "wait and check again" is a legitimate strategy, unlike
item 3, which needs an explicit external data acquisition step that no amount
of app usage will produce on its own.
