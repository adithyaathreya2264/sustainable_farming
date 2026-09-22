// Cron-triggered batch endpoints, guarded by X-Internal-Key (not a farmer JWT).
import { Router } from "express";
import { requireInternalKey } from "../auth.js";
import { runRecommendations } from "../services/recommendationRun.js";
import { runSchemeMatching } from "../services/schemeRun.js";

export const internalRouter = Router();
internalRouter.use(requireInternalKey);

internalRouter.post("/run-recommendations", async (_req, res) => {
  res.json(await runRecommendations());
});

internalRouter.post("/run-scheme-matching", async (_req, res) => {
  res.json(await runSchemeMatching());
});
