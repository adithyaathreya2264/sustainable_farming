import express from "express";
import { corsOriginsList } from "./config.js";
import { errorHandler, makeNotFoundHandler } from "./errors.js";
import { alertsRouter } from "./routes/alerts.js";
import { authRouter } from "./routes/auth.js";
import { fieldsRouter } from "./routes/fields.js";
import { internalRouter } from "./routes/internal.js";
import { mlRouter } from "./routes/ml.js";
import { interventionsRouter } from "./routes/interventions.js";
import { plantingsRouter } from "./routes/plantings.js";
import { catalogRouter, locationsRouter, soilRouter } from "./routes/reference.js";
import { scoutingRouter } from "./routes/scoutingObservations.js";
import { usersRouter } from "./routes/users.js";
import { weatherRouter } from "./routes/weather.js";

export function createApp() {
  const app = express();
  app.disable("x-powered-by");

  // CORS: origins from CORS_ALLOW_ORIGINS, no credentials, any method/header.
  app.use((req, res, next) => {
    const origin = req.headers.origin;
    const wildcard = corsOriginsList.includes("*");
    if (origin && (wildcard || corsOriginsList.includes(origin))) {
      res.setHeader("Access-Control-Allow-Origin", wildcard ? "*" : origin);
      if (!wildcard) res.setHeader("Vary", "Origin");
      if (req.method === "OPTIONS" && req.headers["access-control-request-method"]) {
        res.setHeader("Access-Control-Allow-Methods", "DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT");
        res.setHeader(
          "Access-Control-Allow-Headers",
          req.headers["access-control-request-headers"] ?? "*"
        );
        res.setHeader("Access-Control-Max-Age", "600");
        return res.status(200).type("text/plain").send("OK");
      }
    }
    next();
  });

  app.use(express.json());

  // Same registration order as the Python app.
  const mounts = [
    ["/api/v1/auth", authRouter],
    ["/api/v1/users", usersRouter],
    ["/api/v1/fields", fieldsRouter],
    ["/api/v1/plantings", plantingsRouter],
    ["/api/v1/interventions", interventionsRouter],
    ["/api/v1/scouting-observations", scoutingRouter],
    ["/api/v1", soilRouter],
    ["/api/v1/catalog", catalogRouter],
    ["/api/v1/locations", locationsRouter],
    ["/api/v1/internal", internalRouter],
    ["/api/v1/alerts", alertsRouter],
    ["/api/v1/weather", weatherRouter],
    ["/api/v1/ml", mlRouter],
  ];
  for (const [prefix, router] of mounts) app.use(prefix, router);

  app.get("/health", (_req, res) => res.json({ status: "ok" }));

  app.use(makeNotFoundHandler((path) => allowedMethodsFor(mounts, path)));
  app.use(errorHandler);
  return app;
}

/** Methods a path answers to, for the 405 fallback (introspects the routers). */
function allowedMethodsFor(mounts, requestPath) {
  const path = requestPath.replace(/\/+$/, "") || "/";
  const methods = new Set();
  const all = [["", { stack: [{ route: { path: "/health", methods: { get: true } } }] }], ...mounts];
  for (const [prefix, router] of all) {
    for (const layer of router.stack) {
      if (!layer.route) continue;
      const routePath = (prefix + (layer.route.path === "/" ? "" : layer.route.path)) || "/";
      const re = new RegExp("^" + routePath.replace(/:[^/]+/g, "[^/]+") + "$");
      if (re.test(path)) {
        for (const m of Object.keys(layer.route.methods)) if (layer.route.methods[m]) methods.add(m.toUpperCase());
      }
    }
  }
  return [...methods].sort();
}
