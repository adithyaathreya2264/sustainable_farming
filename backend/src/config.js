// Environment-driven configuration (same variable names as the Python backend).
import dotenv from "dotenv";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
export const BACKEND_DIR = path.resolve(here, "..");
dotenv.config({ path: path.join(BACKEND_DIR, ".env"), quiet: true });

function env(name) {
  return process.env[name] ?? process.env[name.toLowerCase()];
}

function required(name) {
  const v = env(name);
  if (v === undefined || v === "") throw new Error(`Missing required setting ${name}`);
  return v;
}

/** Parse the existing SQLAlchemy-style URL (mysql+pymysql://user:pw@host:3306/db?charset=utf8mb4). */
export function parseDatabaseUrl(raw) {
  const url = new URL(raw.replace(/^mysql\+\w+:\/\//, "mysql://"));
  return {
    host: url.hostname,
    port: url.port ? Number(url.port) : 3306,
    user: decodeURIComponent(url.username),
    password: decodeURIComponent(url.password),
    database: decodeURIComponent(url.pathname.replace(/^\//, "")),
    charset: url.searchParams.get("charset") ?? "utf8mb4",
  };
}

export function loadSettings() {
  return {
    databaseUrl: required("DATABASE_URL"),
    jwtSecret: required("JWT_SECRET"),
    internalApiKey: required("INTERNAL_API_KEY"),
    jwtAlgorithm: env("JWT_ALGORITHM") ?? "HS256",
    jwtExpiryMinutes: Number(env("JWT_EXPIRY_MINUTES") ?? 60 * 24 * 7),
    mockOtp: env("MOCK_OTP") ?? "123456",
    corsAllowOrigins: env("CORS_ALLOW_ORIGINS") ?? "*",
    port: Number(env("PORT") ?? 8000),
  };
}

export const settings = loadSettings();

export const corsOriginsList = settings.corsAllowOrigins
  .split(",")
  .map((o) => o.trim())
  .filter(Boolean);
