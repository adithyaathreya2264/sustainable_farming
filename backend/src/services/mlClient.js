// HTTP client for the ML sidecar (ml/serving/, FastAPI on 127.0.0.1:8001).
//
// Every ML failure becomes an HttpError with a machine-readable `reason`, so
// routes never have to think about the sidecar and the app never sees a 500
// for a model problem:
//
//   sidecar 409 model_did_not_ship  -> 409, reason "model_did_not_ship"
//   sidecar 413 / 422               -> same status, sidecar's reason
//   refused connection, timeout, 5xx -> 503, reason "ml_unavailable"
import { HttpError } from "../errors.js";

// Read per call so tests (and a restarted sidecar on another port) need no reload.
export function mlSidecarUrl() {
  return (process.env.ML_SIDECAR_URL ?? "http://127.0.0.1:8001").replace(/\/$/, "");
}

const JSON_TIMEOUT_MS = 15_000;
// The first call to a torch model loads its weights; later calls are ~1 s.
const IMAGE_TIMEOUT_MS = 90_000;

function unavailable(cause) {
  return new HttpError(503, "Model service unavailable right now.", {}, {
    reason: "ml_unavailable",
    ...(cause ? { cause } : {}),
  });
}

async function send(path, init, timeoutMs) {
  let response;
  try {
    response = await fetch(`${mlSidecarUrl()}${path}`, {
      ...init,
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch (err) {
    throw unavailable(err?.name === "TimeoutError" ? "timeout" : "unreachable");
  }

  let body = null;
  try {
    body = await response.json();
  } catch {
    // Non-JSON from the sidecar is treated like any other sidecar fault.
  }

  if (response.ok) {
    if (body === null) throw unavailable("malformed_response");
    return body;
  }
  if (response.status === 409) {
    throw new HttpError(409, body?.detail ?? "This model is not available.", {}, {
      reason: body?.reason ?? "model_did_not_ship",
    });
  }
  if (response.status === 413 || response.status === 422) {
    throw new HttpError(response.status, body?.detail ?? "Invalid input for the model.", {}, {
      reason: body?.reason ?? "invalid_input",
    });
  }
  throw unavailable(body?.reason ?? `status_${response.status}`);
}

export function mlGet(path, params = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")
  ).toString();
  return send(qs ? `${path}?${qs}` : path, { method: "GET" }, JSON_TIMEOUT_MS);
}

export function mlPost(path, body) {
  return send(
    path,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
    JSON_TIMEOUT_MS
  );
}

/** Forward one uploaded photo (a Buffer) plus string form fields. */
export function mlImage(path, buffer, mimetype, fields = {}) {
  const form = new FormData();
  form.append("photo", new Blob([buffer], { type: mimetype }), "photo");
  for (const [key, value] of Object.entries(fields)) {
    if (value !== undefined && value !== null) form.append(key, String(value));
  }
  return send(path, { method: "POST", body: form }, IMAGE_TIMEOUT_MS);
}
