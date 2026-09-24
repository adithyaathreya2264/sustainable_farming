import { cropFit, type CropRecommendationResult } from "../cropRecommendation";
import { photoCheckFromBackend, remedyFor } from "../ml";

async function bootStore() {
  jest.resetModules();
  const mod = require("@react-native-async-storage/async-storage");
  await (mod.default ?? mod).clear();
  const store = require("../../store/appStore") as typeof import("../../store/appStore");
  await store.hydrate();
  return store;
}

const entry = (cropKey: string, cropId: string | null) => ({
  cropKey,
  cropId,
  displayName: cropKey,
  isSeededCrop: true,
  confidenceLabel: "provisional" as const,
});

const rec: CropRecommendationResult = {
  recommended: entry("ragi", "crop-ragi"),
  alternatives: [entry("maize", "crop-maize"), entry("jute", null)],
  unreachableSeededCrops: ["sugarcane"],
  usedSoilTest: false,
  basis: "soil_type",
};

describe("cropFit", () => {
  it("matches by crop id / ML key, not display name", () => {
    // "Ragi (Finger Millet)" never equalled the model's "Ragi" display name.
    expect(cropFit({ id: "crop-ragi", mlKey: "ragi" }, rec)).toBe("top");
    expect(cropFit({ id: "other-id", mlKey: "maize" }, rec)).toBe("alternative");
    expect(cropFit({ id: "crop-sugarcane", mlKey: "sugarcane" }, rec)).toBe("unscored");
    expect(cropFit({ id: "crop-cotton", mlKey: "cotton" }, rec)).toBeNull();
  });

  it("tolerates catalog rows cached before ml_key existed", () => {
    expect(cropFit({ id: "crop-ragi" }, rec)).toBe("top");
    expect(cropFit({ id: "crop-cotton" }, rec)).toBeNull();
  });
});

describe("photo check mapping", () => {
  it("maps an insect result, keeping boxes as fractions", () => {
    const r = photoCheckFromBackend("insects", {
      detections: [
        {
          key: "yellow_stem_borer",
          display_name: "Yellow Stem Borer",
          confidence_label: "provisional",
          pest_of_this_crop: true,
          related_rules: ["RICE_STEM_BORER_SCOUT"],
          box: { x1: 0.1, y1: 0.2, x2: 0.5, y2: 0.6 },
        },
      ],
      no_detection: false,
      caveats: ["c"],
    });
    expect(r.kind).toBe("insects");
    if (r.kind !== "insects") return;
    expect(r.detections[0]).toMatchObject({ displayName: "Yellow Stem Borer", relatedRules: ["RICE_STEM_BORER_SCOUT"] });
    expect(r.detections[0].box.x2).toBe(0.5);
  });

  it("maps a conditional leaf refusal to a null condition with its reason", () => {
    const r = photoCheckFromBackend("leaf", { condition: null, alternatives: [], reason: "symptom_required" });
    expect(r.kind === "leaf" && r.condition).toBeNull();
    expect(r.kind === "leaf" && r.reason).toBe("symptom_required");
  });
});

describe("remedyFor", () => {
  const remedies = { en: "Spray X", hi: "X छिड़कें", hindiIsEnglishFallback: false };

  it("uses Hindi only when a genuine Hindi text exists", () => {
    expect(remedyFor(remedies, "hi")).toEqual({ text: "X छिड़कें", shownInEnglish: false });
    expect(remedyFor({ ...remedies, hi: "Spray X", hindiIsEnglishFallback: true }, "hi")).toEqual({
      text: "Spray X",
      shownInEnglish: true,
    });
  });

  it("falls back to English, flagged, for languages the corpus lacks", () => {
    expect(remedyFor(remedies, "kn")).toEqual({ text: "Spray X", shownInEnglish: true });
    expect(remedyFor(remedies, "en")).toEqual({ text: "Spray X", shownInEnglish: false });
  });
});

describe("apiUpload", () => {
  it("sends multipart with auth and without a hand-set Content-Type", async () => {
    const store = await bootStore();
    store.setState({ isAuthenticated: true, authToken: "tok" });
    const { apiUpload } = require("../../lib/apiClient") as typeof import("../../lib/apiClient");
    const fetchMock = jest.fn().mockResolvedValue({ ok: true, text: async () => JSON.stringify({ ok: 1 }) });
    (global as unknown as { fetch: typeof fetch }).fetch = fetchMock as never;

    await apiUpload("/api/v1/ml/soil-type", { uri: "file:///x.jpg", fields: { field_id: "f1", skip: undefined } });

    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({ Authorization: "Bearer tok" });
    expect(init.body).toBeInstanceOf(FormData);
  });

  it("surfaces the backend's reason on failure", async () => {
    await bootStore();
    const { apiUpload, apiErrorReason, ApiError } = require("../../lib/apiClient") as typeof import("../../lib/apiClient");
    (global as unknown as { fetch: typeof fetch }).fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 503,
      text: async () => JSON.stringify({ detail: "down", reason: "ml_unavailable" }),
    }) as never;

    const err = await apiUpload("/x", { uri: "file:///x.jpg" }).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(apiErrorReason(err)).toBe("ml_unavailable");
  });
});
