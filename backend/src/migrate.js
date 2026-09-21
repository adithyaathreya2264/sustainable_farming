// Migration runner:  npm run migrate
//
// Migrations live in backend/migrations/NNNN_name.sql and are tracked in the
// `schema_migrations` table.
//
//  * Empty database              -> every migration runs for real.
//  * Existing database that was built by the old Alembic tooling and is at
//    revision e1f2a3b4c5d6       -> the baseline (0001) is STAMPED as applied
//    without running any DDL (the `alembic stamp head` equivalent); later
//    migrations then run normally. `alembic_version` is left untouched.
//  * Anything else (tables present but revision unknown/older) -> refuse.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import mysql from "mysql2/promise";
import { parseDatabaseUrl, settings } from "./config.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const MIGRATIONS_DIR = path.resolve(here, "..", "migrations");
const BASELINE = "0001_baseline";
const ALEMBIC_HEAD = "e1f2a3b4c5d6";

function listMigrations() {
  return fs
    .readdirSync(MIGRATIONS_DIR)
    .filter((f) => f.endsWith(".sql"))
    .sort()
    .map((f) => ({ version: f.replace(/\.sql$/, ""), file: path.join(MIGRATIONS_DIR, f) }));
}

async function tableExists(conn, name) {
  const [rows] = await conn.query(
    "SELECT 1 FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = ?",
    [name]
  );
  return rows.length > 0;
}

export async function migrate({ log = console.log } = {}) {
  const conn = await mysql.createConnection({
    ...parseDatabaseUrl(settings.databaseUrl),
    multipleStatements: true,
  });
  try {
    await conn.query(`CREATE TABLE IF NOT EXISTS schema_migrations (
      version VARCHAR(64) NOT NULL PRIMARY KEY,
      applied_at DATETIME NOT NULL,
      stamped TINYINT(1) NOT NULL DEFAULT 0
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`);

    const [appliedRows] = await conn.query("SELECT version FROM schema_migrations");
    const applied = new Set(appliedRows.map((r) => r.version));
    const migrations = listMigrations();

    if (applied.size === 0 && (await tableExists(conn, "users"))) {
      // Tables already exist but nothing is tracked yet: only safe for a DB
      // Alembic brought to its final revision.
      let revision = null;
      if (await tableExists(conn, "alembic_version")) {
        const [rows] = await conn.query("SELECT version_num FROM alembic_version");
        revision = rows[0]?.version_num ?? null;
      }
      if (revision !== ALEMBIC_HEAD) {
        throw new Error(
          `Database has tables but is not at Alembic revision ${ALEMBIC_HEAD} ` +
            `(found ${revision ?? "no alembic_version"}); refusing to guess. ` +
            "Bring it to that revision or use an empty database."
        );
      }
      await conn.query(
        "INSERT INTO schema_migrations (version, applied_at, stamped) VALUES (?, UTC_TIMESTAMP(), 1)",
        [BASELINE]
      );
      applied.add(BASELINE);
      log(`stamped ${BASELINE} (existing Alembic ${ALEMBIC_HEAD} schema; no DDL executed)`);
    }

    let ran = 0;
    for (const m of migrations) {
      if (applied.has(m.version)) continue;
      log(`applying ${m.version} ...`);
      await conn.query(fs.readFileSync(m.file, "utf8"));
      await conn.query(
        "INSERT INTO schema_migrations (version, applied_at, stamped) VALUES (?, UTC_TIMESTAMP(), 0)",
        [m.version]
      );
      ran += 1;
    }
    log(ran ? `done: ${ran} migration(s) applied` : "up to date");
    return ran;
  } finally {
    await conn.end();
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  migrate().catch((err) => {
    console.error(err.message);
    process.exit(1);
  });
}
