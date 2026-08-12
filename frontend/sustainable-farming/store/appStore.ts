import AsyncStorage from "@react-native-async-storage/async-storage";
import type {
  Field,
  Intervention,
  Planting,
  Recommendation,
  User,
  Vendor,
} from "../types/models";
import userSeed from "../data/mock/user.json";
import demoSeed from "../data/mock/demoSeed.json";

/**
 * A small reactive in-memory store standing in for WatermelonDB during the
 * frontend-only build. Screens subscribe via useSyncExternalStore (see
 * hooks in services/*.ts) so swapping this for WatermelonDB's observable
 * queries later only touches this file, not screen code.
 */
export interface AppState {
  hydrated: boolean;
  isAuthenticated: boolean;
  user: User;
  fields: Field[];
  plantings: Planting[];
  interventions: Intervention[];
  alerts: Recommendation[];
  vendors: Vendor[];
}

const STORAGE_KEY = "agrosense.appState.v1";

let state: AppState = {
  hydrated: false,
  isAuthenticated: false,
  user: userSeed as User,
  fields: [],
  plantings: [],
  interventions: [],
  alerts: [],
  vendors: demoSeed.vendors as Vendor[],
};

const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((listener) => listener());
}

function persist() {
  AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(state)).catch(() => {
    // Best-effort persistence for the frontend-only mock; a failed write
    // just means the next reload starts from the last hydrated state.
  });
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
      state = { ...state, ...JSON.parse(raw), hydrated: true };
    } else {
      state = { ...state, hydrated: true };
    }
  } catch {
    state = { ...state, hydrated: true };
  }
  emit();
}

export function setState(partial: Partial<AppState>) {
  state = { ...state, ...partial };
  emit();
  persist();
}

export function loadDemoData() {
  setState({
    fields: demoSeed.fields as Field[],
    plantings: demoSeed.plantings as Planting[],
    interventions: demoSeed.interventions as Intervention[],
    alerts: demoSeed.alerts as Recommendation[],
  });
}

export function resetDemo() {
  setState({
    user: { ...(userSeed as User) },
    fields: [],
    plantings: [],
    interventions: [],
    alerts: [],
  });
}

export function logout() {
  setState({ isAuthenticated: false });
}
