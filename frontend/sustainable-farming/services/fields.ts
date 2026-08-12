import { getState, setState } from "../store/appStore";
import type { Field } from "../types/models";

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
  lat: number;
  long: number;
  soilType: string;
}

export async function addField(input: AddFieldInput): Promise<Field> {
  const field: Field = {
    id: `f${Date.now()}`,
    userId: getState().user.id,
    ...input,
  };
  setState({ fields: [...getState().fields, field] });
  return field;
}
