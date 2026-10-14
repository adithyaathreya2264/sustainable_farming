"""Upload / download trained model artifacts via the Hugging Face Hub.

    python -m ml.hf_artifacts upload   # push ml/artifacts/ (needs `huggingface-cli login`)
    python -m ml.hf_artifacts fetch    # pull them into ml/artifacts/

The repo id comes from the HF_REPO_ID environment variable (e.g.
"your-username/kishan-mitra-models"). Only what serving needs is transferred:
top-level model/metrics files and weights/. The large regenerable folders
(image_cache, yolo_data, yolo_runs) are never uploaded.

Requires: pip install huggingface_hub
"""
from __future__ import annotations

import argparse
import os
import sys

from ml import paths

IGNORE = ["image_cache/*", "yolo_data/*", "yolo_runs/*", "__pycache__/*"]


def _repo_id() -> str:
    repo = os.environ.get("HF_REPO_ID", "").strip()
    if not repo:
        sys.exit('Set HF_REPO_ID first, e.g. HF_REPO_ID="your-username/kishan-mitra-models".')
    return repo


def upload(private: bool) -> None:
    from huggingface_hub import HfApi

    api = HfApi()
    repo = _repo_id()
    api.create_repo(repo, repo_type="model", private=private, exist_ok=True)
    api.upload_folder(
        repo_id=repo,
        repo_type="model",
        folder_path=str(paths.ARTIFACTS_DIR),
        ignore_patterns=IGNORE,
        commit_message="Upload model artifacts",
    )
    print(f"Uploaded {paths.ARTIFACTS_DIR} -> https://huggingface.co/{repo}")


def fetch() -> None:
    from huggingface_hub import snapshot_download

    repo = _repo_id()
    paths.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=repo,
        repo_type="model",
        local_dir=str(paths.ARTIFACTS_DIR),
        ignore_patterns=IGNORE,
    )
    print(f"Downloaded {repo} -> {paths.ARTIFACTS_DIR}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    up = sub.add_parser("upload", help="push ml/artifacts/ to the Hub")
    up.add_argument("--public", action="store_true", help="create the repo public (default: private)")
    sub.add_parser("fetch", help="pull artifacts from the Hub")
    args = parser.parse_args()
    if args.cmd == "upload":
        upload(private=not args.public)
    else:
        fetch()


if __name__ == "__main__":
    main()
