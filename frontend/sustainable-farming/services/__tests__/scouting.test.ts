import {
  scoutingObservationFromBackend,
  scoutingObservationToBackend,
} from "../../lib/syncMapping";
import { metricForPlanting } from "../../lib/scoutingMetrics";
import type { Crop, ScoutingObservation } from "../../types/models";

const flush = () => new Promise((r) => setImmediate(r));

async function bootStore() {
  jest.resetModules();
  const mod = require("@react-native-async-storage/async-storage");
  await (mod.default ?? mod).clear();
  const store = require("../../store/appStore") as typeof import("../../store/appStore");
  await store.hydrate();
  return store;
}

describe("scouting service + mapping", () => {
  it("addScoutingObservation appends an unsynced row", async () => {
    const store = await bootStore();
    const { addScoutingObservation, getScoutingObservationsByPlanting } =
      require("../scouting") as typeof import("../scouting");

    await addScoutingObservation({
      plantingId: "pl1",
      metricKey: "dead_hearts_percent",
      metricValue: 7,
      observedAt: "2026-08-01",
    });
    await flush();

    const rows = await getScoutingObservationsByPlanting("pl1");
    expect(rows).toHaveLength(1);
    expect(rows[0].isSynced).toBe(false);
    expect(rows[0].metricValue).toBe(7);
    expect(store.getState().scoutingObservations).toHaveLength(1);
  });

  it("syncMapping round-trips camel<->snake and marks synced on the way in", () => {
    const local: ScoutingObservation = {
      id: "so1",
      plantingId: "pl1",
      metricKey: "deadheart_percent",
      metricValue: 12.5,
      observedAt: "2026-07-15",
      notes: "north corner",
      isSynced: false,
    };
    const wire = scoutingObservationToBackend(local);
    expect(wire).toEqual({
      id: "so1",
      planting_id: "pl1",
      metric_key: "deadheart_percent",
      metric_value: 12.5,
      observed_at: "2026-07-15",
      notes: "north corner",
    });
    const back = scoutingObservationFromBackend(wire);
    expect(back).toEqual({ ...local, isSynced: true });
  });
});

describe("metricForPlanting", () => {
  const rice: Crop = {
    id: "c-rice",
    name: "Rice",
    varieties: [],
    growthStages: [
      { stageName: "Seedling", startDay: 0, endDay: 20 },
      { stageName: "Vegetative (Tillering)", startDay: 20, endDay: 45 },
      { stageName: "Panicle Initiation", startDay: 45, endDay: 65 },
    ],
  };

  it("returns the tillering metric when the planting is in that window", () => {
    const sowing = new Date(Date.now() - 30 * 86_400_000)
      .toISOString()
      .slice(0, 10);
    const m = metricForPlanting(rice, sowing);
    expect(m?.metricKey).toBe("dead_hearts_percent");
  });

  it("returns undefined outside a scouting stage", () => {
    const sowing = new Date(Date.now() - 5 * 86_400_000)
      .toISOString()
      .slice(0, 10);
    expect(metricForPlanting(rice, sowing)).toBeUndefined();
  });

  it("returns undefined when the crop has no stage data", () => {
    expect(
      metricForPlanting({ ...rice, growthStages: [] }, "2026-01-01")
    ).toBeUndefined();
  });
});
