import AsyncStorage from "@react-native-async-storage/async-storage";
import type {
  AgriCatalogItem,
  Alert,
  Crop,
  Field,
  Intervention,
  Planting,
  ScoutingObservation,
  User,
  Vendor,
  WeatherSnapshot,
} from "../types/models";

/** Placeholder shown before a real profile is loaded (pre-auth/onboarding). */
function blankUser(): User {
  return {
    id: "",
    phoneNumber: "",
    uniqueId: "",
    name: "",
    languagePref: "en",
    defaultUnit: "hectare",
    totalAreaHectares: 0,
    irrigationType: "rainfed",
    state: "",
    district: "",
    onboardingComplete: false,
  };
}

/**
 * A small reactive in-memory store (screens subscribe via
 * useSyncExternalStore) backed by a versioned, whitelisted AsyncStorage
 * envelope. The app is online-only (hooks/useRefreshTriggers.ts) — every
 * list here is just a cache of the last successful fetch, not a dirty-row
 * queue.
 */
export interface AppState {
  hydrated: boolean;
  isAuthenticated: boolean;
  authToken: string | null;
  /** Where the current row data came from — governs demo-row hygiene. */
  dataOrigin: "empty" | "demo" | "live";
  user: User;
  fields: Field[];
  plantings: Planting[];
  interventions: Intervention[];
  scoutingObservations: ScoutingObservation[];
  alerts: Alert[];
  vendors: Vendor[];
  crops: Crop[];
  agriInputs: AgriCatalogItem[];
  catalogFetchedAt: number | null;
  catalogDatasetTag: string | null;
  weather: WeatherSnapshot | null;
}

const STORAGE_KEY = "agrosense.appState.v1";

/** Bump on any persisted-shape change and add a `migrations[n]` entry. */
export const SCHEMA_VERSION = 6;

/** Only these keys are written to disk — `hydrated` is transient, `vendors`
 * has no persistence source at all (see defaultState). */
const PERSISTED_KEYS: (keyof AppState)[] = [
  "isAuthenticated",
  "authToken",
  "dataOrigin",
  "user",
  "fields",
  "plantings",
  "interventions",
  "scoutingObservations",
  "alerts",
  "crops",
  "agriInputs",
  "catalogFetchedAt",
  "catalogDatasetTag",
  "weather",
];

type PersistedData = Record<string, unknown>;

/**
 * Each entry migrates persisted `data` from version `n - 1` to `n`. Missing
 * keys after migration are filled in from `defaultState` on load, so a
 * migration only needs to touch what actually changed shape.
 */
const migrations: Record<number, (data: PersistedData) => PersistedData> = {
  // v1 blobs (including a legacy pre-envelope dump) can't distinguish demo
  // from real rows and predate the auth-token format below — discard both.
  2: (data) => ({ ...data, authToken: null, isAuthenticated: false, fields: [] }),
  // Old mock Recommendation shape -> unified Alert shape.
  3: (data) => ({ ...data, alerts: [] }),
  // Added the dashboard weather cache.
  4: (data) => ({ ...data, weather: null }),
  // Added field-scouting observations.
  5: (data) => ({ ...data, scoutingObservations: [] }),
  // Offline-first (sync-manager's pull cursor) was dropped.
  6: (data) => {
    const { lastPulledAt: _lastPulledAt, ...rest } = data;
    return rest;
  },
};

/**
 * Runs the migration chain over a parsed storage blob. Returns null when the
 * blob can't be trusted (from a future schema version) — the caller starts
 * clean instead of merging in something it doesn't understand.
 */
function migratePersisted(parsed: unknown): PersistedData | null {
  if (!parsed || typeof parsed !== "object") return null;
  const obj = parsed as Record<string, unknown>;

  let version: number;
  let data: PersistedData;
  if (typeof obj.schemaVersion === "number" && obj.data && typeof obj.data === "object") {
    version = obj.schemaVersion;
    data = { ...(obj.data as PersistedData) };
  } else {
    // No envelope at all — a legacy pre-migration dump. Treat as v1.
    version = 1;
    data = { ...obj };
  }

  if (version > SCHEMA_VERSION) return null;

  for (let v = version + 1; v <= SCHEMA_VERSION; v++) {
    const migrate = migrations[v];
    if (migrate) data = migrate(data);
  }
  return data;
}

function defaultState(): AppState {
  return {
    hydrated: false,
    isAuthenticated: false,
    authToken: null,
    dataOrigin: "empty",
    user: blankUser(),
    fields: [],
    plantings: [],
    interventions: [],
    scoutingObservations: [],
    alerts: [],
    vendors: [],
    crops: [],
    agriInputs: [],
    catalogFetchedAt: null,
    catalogDatasetTag: null,
    weather: null,
  };
}

let state: AppState = defaultState();

const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((listener) => listener());
}

function persist() {
  const data: PersistedData = {};
  for (const key of PERSISTED_KEYS) data[key] = state[key];
  AsyncStorage.setItem(STORAGE_KEY, JSON.stringify({ schemaVersion: SCHEMA_VERSION, data })).catch(
    () => {
      // Best-effort persistence; a failed write just means the next reload
      // starts from the last hydrated state.
    }
  );
}

export function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getState(): AppState {
  return state;
}

export async function hydrate() {
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    if (raw) {
      const migrated = migratePersisted(JSON.parse(raw));
      state = migrated
        ? { ...state, ...(migrated as Partial<AppState>), hydrated: true }
        : { ...state, hydrated: true };
    } else {
      state = { ...state, hydrated: true };
    }
  } catch {
    state = { ...defaultState(), hydrated: true };
  }
  emit();
}

export function setState(partial: Partial<AppState>) {
  state = { ...state, ...partial };
  emit();
  persist();
}

/**
 * Called right after a successful OTP verify. Demo rows can never reach the
 * backend, so if the session was showing demo data, wipe it before the first
 * real fetch; a session that already had real/empty data keeps it.
 */
export function markLiveSession() {
  const wasDemo = state.dataOrigin === "demo";
  setState({
    dataOrigin: "live",
    ...(wasDemo
      ? {
          fields: [],
          plantings: [],
          interventions: [],
          scoutingObservations: [],
          alerts: [],
        }
      : {}),
  });
}

export function logout() {
  setState({ isAuthenticated: false, authToken: null });
}

/**
 * Dev-only "reset user": wipes the whole local store (auth, profile, fields,
 * plantings, everything) back to a fresh-install state and clears the
 * persisted envelope outright, rather than persisting an empty one. Does not
 * touch the backend — the farmer's account/rows still exist there, so
 * re-logging in with the same phone number picks the profile back up. This
 * is for local testing only; call sites must gate it behind `__DEV__`.
 */
export function resetUser() {
  state = { ...defaultState(), hydrated: true };
  emit();
  AsyncStorage.removeItem(STORAGE_KEY).catch(() => {
    // Best-effort; an in-memory reset still took effect either way.
  });
}

/**
 * Reconciles locally-cached rows when the backend catalog's ids change under
 * us (e.g. a re-seed) — drops plantings whose `cropId` no longer resolves,
 * and any intervention/scouting-observation left pointing at a dropped
 * planting or a dead `productId`.
 */
export function pruneOrphanedCatalogRefs(nextCrops: Crop[], nextInputs: AgriCatalogItem[]) {
  const cropIds = new Set(nextCrops.map((c) => c.id));
  const inputIds = new Set(nextInputs.map((i) => i.id));

  const survivingPlantings = state.plantings.filter((p) => cropIds.has(p.cropId));
  const survivingPlantingIds = new Set(survivingPlantings.map((p) => p.id));

  const survivingInterventions = state.interventions.filter(
    (i) => survivingPlantingIds.has(i.plantingId) && (!i.productId || inputIds.has(i.productId))
  );
  const survivingScoutingObservations = state.scoutingObservations.filter((o) =>
    survivingPlantingIds.has(o.plantingId)
  );

  setState({
    plantings: survivingPlantings,
    interventions: survivingInterventions,
    scoutingObservations: survivingScoutingObservations,
  });
}
