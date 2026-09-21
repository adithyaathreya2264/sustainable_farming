import mysql from "mysql2/promise";
import { randomUUID } from "node:crypto";
import { parseDatabaseUrl, settings } from "./config.js";

const conn = parseDatabaseUrl(settings.databaseUrl);

export const pool = mysql.createPool({
  ...conn,
  waitForConnections: true,
  connectionLimit: 15,
  enableKeepAlive: true,
  decimalNumbers: true, // DECIMAL -> JS number (the API serialized floats)
  dateStrings: true, // DATE/DATETIME stay plain strings: no timezone shifts
  timezone: "+00:00",
});

export const newId = () => randomUUID();

export async function query(sql, params = []) {
  const [rows] = await pool.query(sql, params);
  return rows;
}

/** First row or null. */
export async function queryOne(sql, params = []) {
  const rows = await query(sql, params);
  return rows[0] ?? null;
}

/** Run `fn(tx)` in one transaction (commit on success, rollback on error). */
export async function withTransaction(fn) {
  const c = await pool.getConnection();
  const tx = {
    async query(sql, params = []) {
      const [rows] = await c.query(sql, params);
      return rows;
    },
    async queryOne(sql, params = []) {
      const rows = await tx.query(sql, params);
      return rows[0] ?? null;
    },
  };
  try {
    await c.beginTransaction();
    const result = await fn(tx);
    await c.commit();
    return result;
  } catch (err) {
    await c.rollback();
    throw err;
  } finally {
    c.release();
  }
}

export const bool = (v) => v === 1 || v === true;
