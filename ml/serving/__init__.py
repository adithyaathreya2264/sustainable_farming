"""HTTP serving layer for the shipped models: a FastAPI sidecar on 127.0.0.1:8001.

The Node backend is its only caller (backend/src/services/mlClient.js). This
package owns two guarantees so that no caller can bypass them:

- nothing a model marks as internal (keys starting with `_`, e.g. yield's
  `_raw_model_output`) and no probability-like key leaves the process
  (`sanitize.py`);
- a model that failed its bar surfaces as a 409, never as a 500 and never as a
  result (`errors.py`, plus the gates already inside `ml/algorithms`).

Run from the repo root:

    .venv/Scripts/python.exe -m uvicorn ml.serving.app:app --host 127.0.0.1 --port 8001
"""
