// Run the API (node --watch) and the ML sidecar together, with prefixed output.
// Ctrl+C stops both; if either exits, the other is stopped too.
//
//   npm run dev:all
import { spawn } from "node:child_process";
import path from "node:path";
import readline from "node:readline";
import { fileURLToPath } from "node:url";
import { startSidecar } from "./start-ml.js";

const backendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function prefix(child, label) {
  for (const stream of [child.stdout, child.stderr]) {
    readline.createInterface({ input: stream }).on("line", (line) => console.log(`[${label}] ${line}`));
  }
}

const ml = startSidecar(["ignore", "pipe", "pipe"]);
const api = spawn(process.execPath, ["--watch", "src/server.js"], {
  cwd: backendDir,
  stdio: ["ignore", "pipe", "pipe"],
});
prefix(ml, "ml ");
prefix(api, "api");

let stopping = false;
function stopAll(code = 0) {
  if (stopping) return;
  stopping = true;
  ml.kill();
  api.kill();
  setTimeout(() => process.exit(code), 500);
}
ml.on("exit", (code) => stopAll(code ?? 0));
api.on("exit", (code) => stopAll(code ?? 0));
process.on("SIGINT", () => stopAll(0));
process.on("SIGTERM", () => stopAll(0));
