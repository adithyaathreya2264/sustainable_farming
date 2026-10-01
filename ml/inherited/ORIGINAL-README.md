# Smart Agriculture Machine Learning System (`ml/`)

This directory contains the machine learning algorithms, model training pipelines, and datasets for an AI-powered agricultural advisory system.

---

## 📚 Documentation & Guides

- **Interactive Codebase Guide:** Open [`index.html`](file:///e:/major-project-research/ml/index.html) in your browser for a line-by-line low-level breakdown of all 29 Python files, algorithms, I/O contracts, and dataflows.
- **Datasets Documentation:** See [`datasets/README.md`](file:///e:/major-project-research/ml/datasets/README.md) for a comprehensive field dictionary, row counts, statistical distributions, and consuming model mappings for all 11 dataset files.
- **Python Dependencies:** See [`requirements.txt`](file:///e:/major-project-research/ml/requirements.txt) to install required third-party packages:
  ```bash
  pip install -r requirements.txt
  ```

---

## 📂 Repository Structure

```
ml/
├── index.html            # Interactive codebase & architecture guide (Light/Dark themes)
├── requirements.txt      # Python dependencies for inference and training
├── algorithms/           # Real-time inference modules (crop, disease, fertilizer, yield, price)
├── datasets/             # Agronomic, chemical, weather, and NLP datasets
│   ├── README.md         # Detailed datasets technical documentation
│   ├── crop_datasets/    # Multi-class crop recommendation datasets (31 & 51 crops)
│   ├── disease_qa/       # Multilingual pathology Q&A dataset (EN, HI, MR)
│   └── farm_datasets/    # Crop yield, state soil averages, and climatology logs
├── saved_models/         # Pre-trained models, pipelines, and lookup JSONs
└── training/             # Offline data preparation and model training scripts
```
