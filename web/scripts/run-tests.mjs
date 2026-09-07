import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

// Node 25 exposes an experimental process-global localStorage. Test runners
// enumerate globals before jsdom starts, which triggers Node's invalid-path
// warning in every worker. Disable only that experimental Node API when the
// runtime supports the flag; jsdom still supplies the browser Storage API.
// Older CI runtimes (Node 20/22) do not know the flag and run unchanged.
const webStorageFlag = "--no-experimental-webstorage";
const supportsWebStorageFlag = process.allowedNodeEnvironmentFlags.has(webStorageFlag);
const execArgs = supportsWebStorageFlag ? [webStorageFlag] : [];
const nodeOptions = [process.env.NODE_OPTIONS, supportsWebStorageFlag ? webStorageFlag : ""]
  .filter(Boolean)
  .join(" ");
const vitest = fileURLToPath(new URL("../node_modules/vitest/vitest.mjs", import.meta.url));
const result = spawnSync(
  process.execPath,
  [...execArgs, vitest, "run", ...process.argv.slice(2)],
  { stdio: "inherit", env: { ...process.env, NODE_OPTIONS: nodeOptions } },
);

if (result.error) throw result.error;
process.exit(result.status ?? 1);
