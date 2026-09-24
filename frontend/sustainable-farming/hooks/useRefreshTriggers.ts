import { useEffect } from "react";
import { AppState, type AppStateStatus } from "react-native";
import { fetchAndCacheCatalog } from "../services/catalog";
import { fetchAndCacheAlerts } from "../services/alerts";
import { fetchAndCacheWeather } from "../services/weather";
import { fetchAndCacheLocations } from "../services/locations";
import { fetchAndCacheFields } from "../services/fields";
import { fetchAndCachePlantings } from "../services/plantings";
import { fetchAndCacheInterventions } from "../services/interventions";
import { fetchAndCacheScoutingObservations } from "../services/scouting";
import { useAppState } from "./useAppState";

const FALLBACK_INTERVAL_MS = 5 * 60 * 1000;

/**
 * The app is online-only (no local dirty-row queue) — every cached list
 * (catalog, alerts, weather, locations, fields/plantings/interventions/
 * scouting observations) is just refetched from the backend on the same
 * trigger set: app foreground and a periodic fallback timer, so a
 * cron-triggered run-recommendations/run-scheme-matching batch run becomes
 * visible here on the farmer's next foreground/interval fetch.
 */
function refreshAll() {
  fetchAndCacheCatalog();
  fetchAndCacheAlerts();
  fetchAndCacheWeather();
  fetchAndCacheLocations();
  fetchAndCacheFields();
  fetchAndCachePlantings();
  fetchAndCacheInterventions();
  fetchAndCacheScoutingObservations();
}

/**
 * Wires the trigger conditions for background data refresh: the app
 * returning to the foreground, and a periodic fallback timer.
 */
export function useRefreshTriggers() {
  const isAuthenticated = useAppState((s) => s.isAuthenticated);

  useEffect(() => {
    if (!isAuthenticated) return;

    refreshAll(); // fetch everything immediately if the app opens already authenticated

    const appStateSubscription = AppState.addEventListener(
      "change",
      (next: AppStateStatus) => {
        if (next === "active") refreshAll();
      }
    );

    const interval = setInterval(refreshAll, FALLBACK_INTERVAL_MS);

    return () => {
      appStateSubscription.remove();
      clearInterval(interval);
    };
  }, [isAuthenticated]);
}
