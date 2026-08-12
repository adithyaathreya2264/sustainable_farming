import { getState } from "../store/appStore";
import type { Recommendation, Vendor } from "../types/models";

export async function getAlerts(): Promise<Recommendation[]> {
  return [...getState().alerts].sort((a, b) =>
    b.createdAt.localeCompare(a.createdAt)
  );
}

export async function getAlertById(id: string): Promise<Recommendation | undefined> {
  return getState().alerts.find((a) => a.id === id);
}

export async function getNearbyVendors(): Promise<Vendor[]> {
  return getState().vendors;
}
