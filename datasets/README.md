# Datasets

The raw datasets (~GBs) are **not in git** (see `.gitignore`); this file is the tracked record of what belongs here. `ml/paths.py` raises with the missing filename if one is absent.

Do not re-host third-party datasets publicly: their licences and provenance are unverified (see `../DATASETS_STATUS.md` §2). Download each from its original source, or keep a private copy (e.g. a **private** Hugging Face dataset repo) for your own use.

| Folder | Content | Source / licence |
|---|---|---|
| `Cauliflower Dataset` | cauliflower leaf and curd photos | TODO: add source link and licence |
| `PlantDoc-Dataset` | PlantDoc leaf disease images | PlantDoc (see its own README in the folder) |
| `Red and White Onion Dataset` | onion leaf/bulb photos | TODO |
| `SAR-CLD-2024 …` | cotton leaf disease (cotton model dropped from the app) | TODO |
| `Vegetables Image Dataset for Machine Applications` | vegetable images (model 19, rejected) | TODO |
| `Wheat Dataset for Species Classification and Sunn Pest Damage Detection` | wheat kernels / heading | TODO |
| `coffee_dataset`, `tea_leaves_datasets`, `potato_dataset`, `tomato_dataset`, `rice_leafs_disease`, `millets_dataset`, `tobacco_dataset`, `soybean_dataset`, `sugarcane_dataset` | crop leaf/part images and trait tables | TODO |
| `insects.v2-release.yolov8` | insect detection (YOLOv8 format) | Roboflow RF100 "insects" v2, CC BY 4.0, https://universe.roboflow.com/roboflow-100/insects-mytwu |
| `soil_dataset` | soil type images | TODO |
| `crop datasets`, `crop disease`, `farm datasets`, `weather datasets`, `datasets` | tabular crop, disease Q&A, yield and weather CSVs | TODO |
| `historical_price_dataset`, `market datasets(1)` | Agmarknet mandi prices (~1.6 GB) | TODO |

## Keeping a private copy on Hugging Face (optional)

```bash
pip install huggingface_hub
huggingface-cli login
huggingface-cli upload your-username/kishan-mitra-datasets datasets . --repo-type dataset --private
```

Restore with `huggingface-cli download your-username/kishan-mitra-datasets --repo-type dataset --local-dir datasets`.

## Trained models

Model artifacts are handled separately: see `ml/hf_artifacts.py` and the root README.
