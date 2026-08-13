import { getState, setState } from "../store/appStore";
import type { Coordinates, Field } from "../types/models";

/** Async to mirror the shape of the future FastAPI/WatermelonDB calls. */
export async function getFields(): Promise<Field[]> {
  return getState().fields;
}

export async function getFieldById(id: string): Promise<Field | undefined> {
  return getState().fields.find((f) => f.id === id);
}

export interface AddFieldInput {
  name: string;
  areaHectares: number;
  boundary: Coordinates[];
  soilType: string;
}

function centroid(points: Coordinates[]): Coordinates {
  const sum = points.reduce(
    (acc, p) => ({ lat: acc.lat + p.lat, long: acc.long + p.long }),
    { lat: 0, long: 0 }
  );
  return { lat: sum.lat / points.length, long: sum.long / points.length };
}

export async function addField(input: AddFieldInput): Promise<Field> {
  const { lat, long } = centroid(input.boundary);
  const field: Field = {
    id: `f${Date.now()}`,
    userId: getState().user.id,
    name: input.name,
    areaHectares: input.areaHectares,
    lat,
    long,
    boundary: input.boundary,
    soilType: input.soilType,
  };
  setState({ fields: [...getState().fields, field] });
  return field;
}
