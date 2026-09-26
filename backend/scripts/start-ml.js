// Start the ML sidecar (ml/serving/, FastAPI) with the repo-root virtualenv.
//
//   npm run ml                  lazy model loading
//   ML_PRELOAD=1 npm run ml     warm every shipped model first (for demos)
//
// ML_PYTHON_BIN overrides the interpreter; ML_SIDECAR_PORT the port (8001).
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
export const REPO_ROOT = path.resolve(here, "..", "..");

export function pythonBin() {
  if (process.env.ML_PYTHON_BIN) return process.env.ML_PYTHON_BIN;
  const candidates = [
    path.join(REPO_ROOT, ".venv", "Scripts", "python.exe"),
    path.join(REPO_ROOT, ".venv", "bin", "python"),
  ];
  const found = candidates.find((p) => fs.existsSync(p));
  if (!found) {
    throw new Error(
      `No virtualenv at ${path.join(REPO_ROOT, ".venv")}. Create it per ml/README.md, ` +
        "or set ML_PYTHON_BIN."
    );
  }
  return found;
}

export function startSidecar(stdio = "inherit") {
  const port = process.env.ML_SIDECAR_PORT ?? "8001";
  return spawn(
    pythonBin(),
    ["-m", "uvicorn", "ml.serving.app:app", "--host", "127.0.0.1", "--port", port],
    { cwd: REPO_ROOT, stdio, env: { ...process.env, PYTHONUNBUFFERED: "1" } }
  );
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const child = startSidecar();
  const stop = () => child.kill();
  process.on("SIGINT", stop);
  process.on("SIGTERM", stop);
  child.on("exit", (code) => process.exit(code ?? 0));
}
