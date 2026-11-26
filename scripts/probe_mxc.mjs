/**
 * RU-05 evaluation only; this does not enable MXC in Raiker.
 * npm install --prefix output/mxc-evaluation --ignore-scripts @microsoft/mxc-sdk@1.1.0
 * node scripts/probe_mxc.mjs [SDK installation directory] [built Windows runner]
 * Synthetic fixtures are retained under output/mxc-evaluation for inspection.
 */
import { execFile } from "node:child_process";
import { copyFileSync, mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { createServer } from "node:net";
import { release } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { promisify } from "node:util";

if (process.platform !== "win32") throw new Error("This evaluation needs Windows.");
const execute = promisify(execFile);
const sdkRoot = resolve(process.argv[2] ?? "output/mxc-evaluation");
const require = createRequire(join(sdkRoot, "package.json"));
const { run, getPlatformSupport, probe } = await import(pathToFileURL(require.resolve("@microsoft/mxc-sdk/v1")));
const sdkVersion = require("./node_modules/@microsoft/mxc-sdk/package.json").version;
const base = mkdtempSync(join(sdkRoot, "probe-"));
const copy = join(base, "copy");
const deniedRoot = join(base, "denied-root");
const explicitChild = join(deniedRoot, "explicit-child");
for (const path of [copy, explicitChild, join(copy, ".git"), join(copy, ".raiker")]) mkdirSync(path, { recursive: true });
const runner = join(copy, "raiker-command-runner.exe");
copyFileSync(resolve(process.argv[3] ?? "native/target/debug/raiker-command-runner.exe"), runner);
const masked = join(base, "owner-secret.txt");
writeFileSync(masked, "synthetic-mxc-canary");
// Deliberately grant ALL APPLICATION PACKAGES below a denied root. Only
// synthetic fixtures are touched; this is the historical AppContainer escape.
await execute("icacls.exe", [explicitChild, "/grant", "*S-1-15-2-1:(OI)(CI)F"]);
const listener = createServer(socket => socket.end());
await new Promise(resolve => listener.listen(0, "0.0.0.0", resolve));
const port = listener.address().port;
const test = {
  nonce: "mxc-probe-20261126", inside_path: join(copy, "inside.txt"),
  outside_paths: [join(base, "escape.txt"), join(explicitChild, "escape.txt"), join(copy, ".git", "escape.txt"), join(copy, ".raiker", "escape.txt")],
  // An external TCP handshake, with no application payload, separates egress
  // from Windows' special treatment of connections to this same host.
  masked_read_path: masked, connect_address: "1.1.1.1:443", loopback_address: `127.0.0.1:${port}`,
  spawn_grandchild: true, hold_for_probe: false,
};
// CommandLineToArgvW escaping; JSON must remain one literal argument.
const quote = value => '"' + value.replace(/(\\*)"/g, '$1$1\\"').replace(/(\\+)$/, "$1$1") + '"';
const report = output => JSON.parse(output.trim().split(/\r?\n/).find(line => line.startsWith("{")));
const verdict = (outside, inside) => outside === true && inside === false ? "enforced" : inside === true ? "unenforced" : "indeterminate";
try {
  const control = report((await execute(runner, ["--selftest", JSON.stringify(test)], { encoding: "utf8", timeout: 20000 })).stdout);
  if (control.descendant_pid) process.kill(control.descendant_pid);
  const request = {
    containment: { type: "processcontainer" },
    command: [runner, "--selftest", JSON.stringify(test)].map(quote).join(" "), workingDirectory: copy,
    filesystem: { readwritePaths: [copy], deniedPaths: [masked, deniedRoot, join(copy, ".git"), join(copy, ".raiker")] },
    network: { egress: { default: "deny" }, ingress: { default: "deny" } }, timeoutMs: 20000,
  };
  const compatibility = await probe(request);
  const result = await run(request);
  const inside = report(result.stdout);
  await new Promise(resolve => setTimeout(resolve, 1000));
  let descendant = "indeterminate";
  if (inside.descendant_pid) {
    try { process.kill(inside.descendant_pid, 0); descendant = "unenforced"; process.kill(inside.descendant_pid); }
    catch (error) { descendant = error.code === "ESRCH" ? "enforced" : "indeterminate"; }
  }
  const observations = {
    relay: inside.nonce === test.nonce ? "enforced" : "unenforced",
    workspace_write: inside.inside_write.allowed === true ? "enforced" : "unenforced",
    escape_write: verdict(control.outside_writes[0].allowed, inside.outside_writes[0].allowed),
    explicit_allow_below_denied_root: verdict(control.outside_writes[1].allowed, inside.outside_writes[1].allowed),
    protected_git: verdict(control.outside_writes[2].allowed, inside.outside_writes[2].allowed),
    protected_raiker: verdict(control.outside_writes[3].allowed, inside.outside_writes[3].allowed),
    masked_read: verdict(control.masked_read.allowed, inside.masked_read.allowed),
    egress: verdict(control.connect.allowed, inside.connect.allowed),
    loopback: verdict(control.loopback.allowed, inside.loopback.allowed),
    own_loopback: inside.own_loopback.allowed ? "enforced" : "unenforced", descendant_reaped: descendant,
  };
  const passed = Object.values(observations).every(value => value === "enforced") && result.exitCode === 0 && !result.timedOut;
  console.log(JSON.stringify({ evaluation_only: true, production_available: false, sdkVersion, os: release(), fixtures: base, platform: getPlatformSupport(), compatibility, observations, passed, control, inside, result }, null, 2));
  process.exitCode = passed ? 0 : 1;
} finally { listener.close(); }
