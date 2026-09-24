const STORAGE_KEY = "agrosense.appState.v1";

const flush = () => new Promise((r) => setImmediate(r));

/**
 * Boot a fresh copy of the store module with `raw` (if given) already in
 * AsyncStorage, then run `hydrate()`. `jest.resetModules()` gives each test
 * its own module-level `state` and a fresh AsyncStorage mock instance.
 */
async function bootWith(raw?: string) {
  jest.resetModules();
  const mod = require("@react-native-async-storage/async-storage");
  const AsyncStorage = mod.default ?? mod;
  await AsyncStorage.clear();
  if (raw !== undefined) await AsyncStorage.setItem(STORAGE_KEY, raw);
  const store = require("../appStore") as typeof import("../appStore");
  await store.hydrate();
  return { store, AsyncStorage };
}

describe("appStore persistence migration", () => {
  it("discards a legacy pre-envelope blob (v1 -> v2) and starts clean", async () => {
    const { store } = await bootWith(
      JSON.stringify({
        authToken: "stale-jwt",
        fields: [{ id: "f1" }],
        isAuthenticated: true,
      })
    );
    const s = store.getState();
    expect(s.hydrated).toBe(true);
    expect(s.authToken).toBeNull();
    expect(s.fields).toEqual([]);
    expect(s.dataOrigin).toBe("empty");
  });

  it("discards a v1 envelope through migrations[2]", async () => {
    const { store } = await bootWith(
      JSON.stringify({
        schemaVersion: 1,
        data: { authToken: "x", fields: [{ id: "f1" }] },
      })
    );
    expect(store.getState().authToken).toBeNull();
    expect(store.getState().fields).toEqual([]);
  });

  it("resets alerts (old Recommendation shape) through migrations[3]", async () => {
    const { store } = await bootWith(
      JSON.stringify({
        schemaVersion: 2,
        data: {
          authToken: "keep-me",
          dataOrigin: "live",
          alerts: [
            { id: "a1", title: "Old shape", description: "x", confidencePct: 80 },
          ],
        },
      })
    );
    // Migration 3 only resets `alerts` — everything else at v2 carries through.
    expect(store.getState().authToken).toBe("keep-me");
    expect(store.getState().dataOrigin).toBe("live");
    expect(store.getState().alerts).toEqual([]);
  });

  it("seeds scoutingObservations through migrations[5] and keeps v4 data", async () => {
    const { store } = await bootWith(
      JSON.stringify({
        schemaVersion: 4,
        data: {
          authToken: "keep-me",
          dataOrigin: "live",
          fields: [{ id: "f1" }],
        },
      })
    );
    expect(store.getState().authToken).toBe("keep-me");
    expect(store.getState().fields).toHaveLength(1);
    expect(store.getState().scoutingObservations).toEqual([]);
  });

  it("drops lastPulledAt through migrations[6] and keeps v5 data", async () => {
    const { store } = await bootWith(
      JSON.stringify({
        schemaVersion: 5,
        data: {
          authToken: "keep-me",
          dataOrigin: "live",
          fields: [{ id: "f1" }],
          lastPulledAt: 42,
        },
      })
    );
    expect(store.getState().authToken).toBe("keep-me");
    expect(store.getState().fields).toHaveLength(1);
    expect(store.getState()).not.toHaveProperty("lastPulledAt");
  });

  it("ignores storage written by a newer schema version", async () => {
    const { store } = await bootWith(
      JSON.stringify({
        schemaVersion: 99,
        data: { authToken: "from-the-future", dataOrigin: "live" },
      })
    );
    expect(store.getState().hydrated).toBe(true);
    expect(store.getState().authToken).toBeNull();
    expect(store.getState().dataOrigin).toBe("empty");
  });

  it("starts clean on corrupt JSON without throwing", async () => {
    const { store } = await bootWith("{ not valid json");
    expect(store.getState().hydrated).toBe(true);
    expect(store.getState().dataOrigin).toBe("empty");
  });

  it("persists only whitelisted keys, wrapped in the current envelope", async () => {
    const { store, AsyncStorage } = await bootWith();
    store.setState({ authToken: "t" });
    await flush();

    const parsed = JSON.parse(await AsyncStorage.getItem(STORAGE_KEY));
    expect(parsed.schemaVersion).toBe(store.SCHEMA_VERSION);
    expect(parsed.data).toHaveProperty("authToken", "t");
    expect(parsed.data).not.toHaveProperty("hydrated");
    expect(parsed.data).not.toHaveProperty("vendors");
  });

  it("round-trips real data at the current schema version", async () => {
    const first = await bootWith();
    first.store.setState({
      fields: [{ id: "f9" } as never],
      dataOrigin: "live",
    });
    await flush();
    const raw = await first.AsyncStorage.getItem(STORAGE_KEY);

    const second = await bootWith(raw);
    expect(second.store.getState().fields).toHaveLength(1);
    expect(second.store.getState().dataOrigin).toBe("live");
  });

  it("markLiveSession wipes demo rows and flips origin to live", async () => {
    const { store } = await bootWith();
    store.setState({
      dataOrigin: "demo",
      fields: [{ id: "demo-field" } as never],
      plantings: [{ id: "demo-planting" } as never],
    });
    expect(store.getState().dataOrigin).toBe("demo");
    expect(store.getState().fields.length).toBeGreaterThan(0);

    store.markLiveSession();
    expect(store.getState().dataOrigin).toBe("live");
    expect(store.getState().fields).toEqual([]);
    expect(store.getState().plantings).toEqual([]);
  });

  it("markLiveSession keeps rows when the origin was not demo", async () => {
    const { store } = await bootWith();
    store.setState({ fields: [{ id: "real" } as never], dataOrigin: "empty" });
    store.markLiveSession();
    expect(store.getState().dataOrigin).toBe("live");
    expect(store.getState().fields).toHaveLength(1);
  });

  it("pruneOrphanedCatalogRefs drops rows with dead catalog refs", async () => {
    const { store } = await bootWith();
    store.setState({
      plantings: [
        { id: "p-keep", cropId: "c-new", varietyId: null },
        { id: "p-dead", cropId: "c-old", varietyId: null },
      ] as never,
      interventions: [
        { id: "i-orphan", plantingId: "p-dead", productId: null },
        { id: "i-keep", plantingId: "p-keep", productId: null },
      ] as never,
    });

    store.pruneOrphanedCatalogRefs(
      [{ id: "c-new", name: "New", varieties: [], growthStages: [] }],
      []
    );

    expect(store.getState().plantings.map((p) => p.id)).toEqual(["p-keep"]);
    expect(store.getState().interventions.map((i) => i.id)).toEqual(["i-keep"]);
  });
});
