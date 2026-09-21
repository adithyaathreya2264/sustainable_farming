// Scheduler entry point for the recommendation / scheme-matching batch jobs.
//
//   npm run batch -- recommendations
//   npm run batch -- scheme-matching
//   npm run batch -- all
//   npm run batch -- all --loop --interval 900
//
// Meant for cron / Windows Task Scheduler (one-shot), or --loop to keep one
// process alive. A failed run in --loop mode is logged and the loop continues;
// a one-shot run lets the error propagate (non-zero exit).
import { pool } from "../src/db.js";
import { runRecommendations } from "../src/services/recommendationRun.js";
import { runSchemeMatching } from "../src/services/schemeRun.js";

const JOBS = {
  recommendations: runRecommendations,
  "scheme-matching": runSchemeMatching,
};

function stamp() {
  return new Date().toISOString().slice(0, 19).replace("T", " ") + "Z";
}

/** Python-dict-style result text: {'a': 1, 'b': 2} (keeps the old log format). */
function fmt(result) {
  return `{${Object.entries(result)
    .map(([k, v]) => `'${k}': ${v}`)
    .join(", ")}}`;
}

async function runOnce(target) {
  const names = target === "all" ? ["recommendations", "scheme-matching"] : [target];
  for (const name of names) {
    const result = await JOBS[name]();
    console.log(`[${stamp()}] ${name}: ${fmt(result)}`);
  }
}

const args = process.argv.slice(2);
const target = args.find((a) => !a.startsWith("--"));
const loop = args.includes("--loop");
const iIdx = args.indexOf("--interval");
const interval = iIdx >= 0 ? Number(args[iIdx + 1]) : 900;

if (!target || (target !== "all" && !JOBS[target])) {
  console.error("usage: run-batch.js {recommendations|scheme-matching|all} [--loop] [--interval N]");
  process.exit(2);
}

try {
  if (loop) {
    console.log(`run_batch loop: ${target} every ${interval}s (Ctrl-C to stop)`);
    for (;;) {
      try {
        await runOnce(target);
      } catch (err) {
        console.error(`[${stamp()}] run failed:`, err);
      }
      await new Promise((r) => setTimeout(r, interval * 1000));
    }
  } else {
    await runOnce(target);
  }
} finally {
  if (!loop) await pool.end();
}
