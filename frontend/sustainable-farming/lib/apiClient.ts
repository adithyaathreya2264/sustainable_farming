import { getState } from "../store/appStore";
import Constants from "expo-constants";

/**
 * Use Expo's current dev-server host for physical devices, so a changing LAN
 * IP does not need to be copied into .env. EXPO_PUBLIC_API_BASE_URL remains an
 * override for simulators, tunnels, and production builds.
 */
const expoHost = Constants.expoConfig?.hostUri
  ? new URL(`http://${Constants.expoConfig.hostUri}`).hostname
  : undefined;

export const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ||
  (expoHost ? `http://${expoHost}:8000` : "http://10.0.2.2:8000");

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

interface ApiFetchOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  /** Skip attaching the Authorization header (login/OTP endpoints). */
  skipAuth?: boolean;
}

export async function apiFetch<T>(
  path: string,
  { body, skipAuth, headers, ...rest }: ApiFetchOptions = {}
): Promise<T> {
  const token = getState().authToken;

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(!skipAuth && token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  const text = await res.text();
  const data = text ? JSON.parse(text) : undefined;

  if (!res.ok) {
    const message =
      (data && typeof data === "object" && "detail" in data
        ? String((data as { detail: unknown }).detail)
        : undefined) ?? `Request failed with status ${res.status}`;
    throw new ApiError(res.status, message, data);
  }

  return data as T;
}

/** The machine-readable `reason` the backend puts beside `detail` on ML
 * errors ("ml_unavailable", "model_did_not_ship", "symptom_required", ...). */
export function apiErrorReason(err: unknown): string | null {
  if (err instanceof ApiError && err.body && typeof err.body === "object" && "reason" in err.body) {
    return String((err.body as { reason: unknown }).reason);
  }
  return null;
}

interface ApiUploadOptions {
  /** Local file URI from expo-image-picker / expo-image-manipulator. */
  uri: string;
  mimeType?: string;
  /** Extra multipart form fields, sent as strings. */
  fields?: Record<string, string | boolean | undefined>;
}

/**
 * Multipart POST of one photo (field name `photo`) plus form fields.
 * Content-Type is deliberately NOT set: React Native's fetch must add the
 * multipart boundary itself, and a hand-set header drops it.
 */
export async function apiUpload<T>(
  path: string,
  { uri, mimeType = "image/jpeg", fields = {} }: ApiUploadOptions
): Promise<T> {
  const token = getState().authToken;
  const form = new FormData();
  form.append("photo", {
    uri,
    name: mimeType === "image/png" ? "photo.png" : "photo.jpg",
    type: mimeType,
  } as unknown as Blob);
  for (const [key, value] of Object.entries(fields)) {
    if (value !== undefined) form.append(key, String(value));
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });

  const text = await res.text();
  const data = text ? JSON.parse(text) : undefined;
  if (!res.ok) {
    const message =
      (data && typeof data === "object" && "detail" in data
        ? String((data as { detail: unknown }).detail)
        : undefined) ?? `Request failed with status ${res.status}`;
    throw new ApiError(res.status, message, data);
  }
  return data as T;
}
