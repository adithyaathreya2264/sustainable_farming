import cropsData from "../data/mock/crops.json";
import agriCatalogData from "../data/mock/agriCatalog.json";
import type { AgriCatalogItem, Crop, InterventionType } from "../types/models";

const crops = cropsData as Crop[];
const agriCatalog = agriCatalogData as AgriCatalogItem[];

export async function getCrops(): Promise<Crop[]> {
  return crops;
}

export async function getCropById(id: string): Promise<Crop | undefined> {
  return crops.find((c) => c.id === id);
}

export async function getAgriProductsByType(
  type: InterventionType
): Promise<AgriCatalogItem[]> {
  return agriCatalog.filter((p) => p.category === type);
}

export async function getAgriProductById(
  id: string
): Promise<AgriCatalogItem | undefined> {
  return agriCatalog.find((p) => p.id === id);
}
