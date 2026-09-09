import { apiFetch } from "../lib/apiClient";
import { getState, setState } from "../store/appStore";
import {
  fieldFromBackend,
  fieldToBackend,
  interventionFromBackend,
  interventionToBackend,
  plantingFromBackend,
  plantingToBackend,
  scoutingObservationFromBackend,
  scoutingObservationToBackend,
  type BackendField,
  type BackendIntervention,
  type BackendPlanting,
  type BackendScoutingObservation,
} from "../lib/syncMapping";
import type {
  Field,
  Intervention,
  Planting,
  ScoutingObservation,
} from "../types/models";

/**
 * Hand-rolled sync client speaking the real backend's WatermelonDB-shaped
 * wire protocol (backend/api/v1/sync.py) over plain fetch — chosen over the
 * literal `@nozbe/watermelondb` package so Expo Go keeps working (see the
 * "Background Data Sync" plan section for the full trade-off). Scope:
 * `fields`/`plantings`/`interventions`/`scouting_observations` are
 * pushed/applied. `recommendations` and `scheme_matches` are server-generated
 * (rule engine, scheme matcher) and delivered to the app by services/alerts.ts
 * via GET/PATCH /api/v1/alerts — never synced (the backend's push path ignores
 * them).
 */

interface TableChanges<T> {
  created: T[];
  updated: T[];
  deleted: string[];
}

interface PullResponse {
  changes: {
    fields?: TableChanges<BackendField>;
    plantings?: TableChanges<BackendPlanting>;
    interventions?: TableChanges<BackendIntervention>;
    scouting_observations?: TableChanges<BackendScoutingObservation>;
    // recommendations / scheme_matches served by pull but ignored here — see
    // file docstring (delivered via /api/v1/alerts instead).
    [table: string]: TableChanges<unknown> | undefined;
  };
  timestamp: number;
}

function applyTableChanges<T extends { id: string }, B>(
  local: T[],
  changes: TableChanges<B> | undefined,
  fromBackend: (row: B) => T
): T[] {
  if (!changes) return local;
  const byId = new Map(local.map((item) => [item.id, item]));
  for (const row of [...changes.created, ...changes.updated]) {
    const mapped = fromBackend(row);
    byId.set(mapped.id, mapped);
  }
  for (const id of changes.deleted) byId.delete(id);
  return Array.from(byId.values());
}

async function pull(): Promise<void> {
  const { lastPulledAt } = getState();
  const params = new URLSearchParams({ schema_version: "1" });
  if (lastPulledAt !== null) params.set("last_pulled_at", String(lastPulledAt));

  const res = await apiFetch<PullResponse>(`/api/v1/sync?${params.toString()}`, {
    method: "GET",
  });

  setState({
    fields: applyTableChanges(getState().fields, res.changes.fields, fieldFromBackend),
    plantings: applyTableChanges(
      getState().plantings,
      res.changes.plantings,
      plantingFromBackend
    ),
    interventions: applyTableChanges(
      getState().interventions,
      res.changes.interventions,
      interventionFromBackend
    ),
    scoutingObservations: applyTableChanges(
      getState().scoutingObservations,
      res.changes.scouting_observations,
      scoutingObservationFromBackend
    ),
    lastPulledAt: res.timestamp,
  });
}

function collectDirty(): {
  fields: Field[];
  plantings: Planting[];
  interventions: Intervention[];
  scoutingObservations: ScoutingObservation[];
} {
  const { fields, plantings, interventions, scoutingObservations } = getState();
  return {
    fields: fields.filter((f) => !f.isSynced),
    plantings: plantings.filter((p) => !p.isSynced),
    interventions: interventions.filter((i) => !i.isSynced),
    scoutingObservations: scoutingObservations.filter((o) => !o.isSynced),
  };
}

async function push(): Promise<void> {
  const dirty = collectDirty();
  const nothingDirty =
    dirty.fields.length === 0 &&
    dirty.plantings.length === 0 &&
    dirty.interventions.length === 0 &&
    dirty.scoutingObservations.length === 0;
  if (nothingDirty) return;

  const { lastPulledAt } = getState();
  const params = new URLSearchParams();
  if (lastPulledAt !== null) params.set("last_pulled_at", String(lastPulledAt));

  const body = {
    fields: { created: dirty.fields.map(fieldToBackend), updated: [], deleted: [] },
    plantings: {
      created: dirty.plantings.map(plantingToBackend),
      updated: [],
      deleted: [],
    },
    interventions: {
      created: dirty.interventions.map(interventionToBackend),
      updated: [],
      deleted: [],
    },
    scouting_observations: {
      created: dirty.scoutingObservations.map(scoutingObservationToBackend),
      updated: [],
      deleted: [],
    },
  };

  await apiFetch(`/api/v1/sync?${params.toString()}`, { method: "POST", body });

  const dirtyIds = {
    fields: new Set(dirty.fields.map((f) => f.id)),
    plantings: new Set(dirty.plantings.map((p) => p.id)),
    interventions: new Set(dirty.interventions.map((i) => i.id)),
    scoutingObservations: new Set(dirty.scoutingObservations.map((o) => o.id)),
  };
  setState({
    fields: getState().fields.map((f) =>
      dirtyIds.fields.has(f.id) ? { ...f, isSynced: true } : f
    ),
    plantings: getState().plantings.map((p) =>
      dirtyIds.plantings.has(p.id) ? { ...p, isSynced: true } : p
    ),
    interventions: getState().interventions.map((i) =>
      dirtyIds.interventions.has(i.id) ? { ...i, isSynced: true } : i
    ),
    scoutingObservations: getState().scoutingObservations.map((o) =>
      dirtyIds.scoutingObservations.has(o.id) ? { ...o, isSynced: true } : o
    ),
  });
}

async function attemptSync(): Promise<void> {
  // Pull first so a 409 on push (stale sync_version) has the best chance of
  // already being resolved by the time push runs — and so the retry-once
  // wrapper's second attempt re-pulls before re-pushing, per WatermelonDB's
  // own documented recommendation.
  await pull();
  await push();
}

let isSyncing = false;

/**
 * SHOULD NOT be called while a sync is already in progress — guarded here
 * with a flag rather than relying solely on any downstream safety, per
 * WatermelonDB's own docs' warning about concurrent synchronize() calls.
 * Failures are retried once (re-pull, then re-push) and otherwise swallowed
 * silently — a transient sync failure is not something to scare a farmer
 * with; the next trigger (connectivity, foreground, or the periodic
 * fallback in hooks/useSyncTriggers.ts) will catch up.
 *
 * No-ops while `dataOrigin === "demo"`: sample rows carry mock catalog IDs
 * and a fake owner and must never be pushed. `markLiveSession()` (real login)
 * clears them and flips the origin to `"live"`.
 */
export async function synchronize(): Promise<void> {
  if (isSyncing) return;
  if (!getState().isAuthenticated) return;
  if (getState().dataOrigin === "demo") return;

  isSyncing = true;
  try {
    await attemptSync();
  } catch {
    try {
      await attemptSync();
    } catch {
      // Give up silently until the next trigger.
    }
  } finally {
    isSyncing = false;
  }
}
