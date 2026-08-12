import { useSyncExternalStore } from "react";
import { getState, subscribe, type AppState } from "../store/appStore";

export function useAppState<T>(selector: (state: AppState) => T): T {
  return useSyncExternalStore(subscribe, () => selector(getState()));
}
