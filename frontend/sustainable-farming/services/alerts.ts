import { apiFetch } from "../lib/apiClient";
import { getState, setState } from "../store/appStore";
import type { Alert, AlertKind, ConfidenceLabel, Vendor } from "../types/models";

/**
 * Unified feed (backend/api/v1/alerts.py, Phase 4 Part 2) — replaces the
 * separate mock `getAlerts()`/`getMatchedSchemes()` readers. Farmers view
 * and respond to alerts, they never create them, so this is a plain
 * fetch + narrow status PATCH, not the sync protocol (services/sync-manager.ts).
 */

interface BackendAlert {
  id: string;
  kind: AlertKind;
  severity: string | null;
  status: string;
  headline: string;
  detail: string | null;
  confidence_label: ConfidenceLabel;
  application_url: string | null;
  authority: string | null;
  eligibility_summary: string[] | null;
  generated_at: string;
  planting_id: string | null;
}

function alertFromBackend(row: BackendAlert): Alert {
  return {
    id: row.id,
    kind: row.kind,
    severity: (row.severity as Alert["severity"]) ?? null,
    status: row.status,
    headline: row.headline,
    detail: row.detail,
    confidenceLabel: row.confidence_label,
    applicationUrl: row.application_url,
    authority: row.authority,
    eligibilitySummary: row.eligibility_summary,
    generatedAt: row.generated_at,
    plantingId: row.planting_id,
  };
}

/**
 * Fetches and caches the alert feed. Best-effort/silent on failure (offline,
 * not yet authenticated) — same pattern as services/catalog.ts's
 * fetchAndCacheCatalog(), fired from the same connectivity/foreground
 * triggers (see hooks/useSyncTriggers.ts), not from screen mount.
 */
export async function fetchAndCacheAlerts(): Promise<void> {
  if (!getState().isAuthenticated) return;
  try {
    const res = await apiFetch<{ items: BackendAlert[] }>("/api/v1/alerts");
    setState({ alerts: res.items.map(alertFromBackend) });
  } catch {
    // Silent — cached copy (possibly empty) stays as-is until next trigger.
  }
}

export async function getRecommendationAlerts(): Promise<Alert[]> {
  return getState().alerts.filter((a) => a.kind === "recommendation");
}

export async function getSchemeAlerts(): Promise<Alert[]> {
  return getState().alerts.filter((a) => a.kind === "scheme_match");
}

export async function getAlertById(id: string): Promise<Alert | undefined> {
  return getState().alerts.find((a) => a.id === id);
}

/**
 * PATCH /api/v1/alerts/{kind}/{id}. Backend validates `status` against the
 * kind-specific allowed set (recommendation: acknowledged/followed/ignored;
 * scheme_match: viewed/dismissed/claimed) — a mismatch 422s. On success,
 * updates the cached row in place so callers don't need to refetch.
 */
export async function respondToAlert(
  kind: AlertKind,
  id: string,
  status: string
): Promise<void> {
  const updated = await apiFetch<BackendAlert>(`/api/v1/alerts/${kind}/${id}`, {
    method: "PATCH",
    body: { status },
  });
  const mapped = alertFromBackend(updated);
  setState({
    alerts: getState().alerts.map((a) => (a.id === id ? mapped : a)),
  });
}

export async function getNearbyVendors(): Promise<Vendor[]> {
  return getState().vendors;
}
