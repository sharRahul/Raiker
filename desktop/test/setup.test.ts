// SPDX-License-Identifier: Apache-2.0
import assert from "node:assert/strict";
import { chmodSync, existsSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import { parseShellArgs } from "../src/args";
import {
  blockingSummary,
  isSetupAction,
  parseSystemCheck,
  plainCause,
  readReceipt,
  runSystemCheck,
  SETUP_ACTIONS,
  SETUP_CHANNELS,
  SetupStageError,
  setupMode,
  verifyHost,
  writeReceipt,
} from "../src/setup";

const ROOT = join(__dirname, "..", "..");

const CHECK = {
  checks: [
    { id: "os", label: "Operating system", state: "pass", detail: "Ubuntu 24.04", remedy: "", mandatory: true },
    { id: "memory", label: "Memory", state: "fail", detail: "3.0 GB", remedy: "Raiker needs at least 4 GB of memory.", mandatory: true },
    { id: "storage", label: "Free storage", state: "warn", detail: "12 GB free", remedy: "Local models need 20 GB.", mandatory: true },
  ],
  blocking: ["memory"],
  ready: false,
};

test("the setup preload repeats exactly the shell's channels and actions", () => {
  const preload = readFileSync(join(ROOT, "src", "setupPreload.ts"), "utf-8");
  for (const channel of Object.values(SETUP_CHANNELS)) assert.ok(preload.includes(`"${channel}"`), channel);
  const listed = preload.match(/const ACTIONS: readonly string\[\] = \[([^\]]*)\]/)?.[1] ?? "";
  assert.deepEqual([...listed.matchAll(/"([a-z]+)"/g)].map((match) => match[1]), [...SETUP_ACTIONS]);
  assert.equal(isSetupAction("open"), true);
  assert.equal(isSetupAction("exec"), false);
  assert.equal(isSetupAction(1), false);
});

test("the Setup page handles every event the shell sends and every action it may ask for", () => {
  const page = readFileSync(join(ROOT, "static", "setup.js"), "utf-8");
  for (const event of ["manifest", "stage", "checks", "log", "complete", "failed"]) {
    assert.ok(page.includes(`case "${event}"`), event);
  }
  for (const action of SETUP_ACTIONS) assert.ok(page.includes(`bridge.send("${action}")`), action);
  const html = readFileSync(join(ROOT, "static", "setup.html"), "utf-8");
  assert.match(html, /default-src 'none'/); // packaged page, nothing remote
});

test("setup runs on a first start, an update or a repair, and not otherwise", (t) => {
  const dir = mkdtempSync(join(tmpdir(), "raiker-receipt-"));
  const path = join(dir, "nested", "setup-complete.json");
  assert.equal(readReceipt(path), null);
  assert.equal(setupMode(null, "1.0.0", false), "install");
  writeReceipt(path, "1.0.0", new Date("2026-10-17T00:00:00Z"));
  const receipt = readReceipt(path);
  assert.deepEqual(receipt, { schema: 1, version: "1.0.0", completedAt: "2026-10-17T00:00:00.000Z" });
  assert.equal(existsSync(`${path}.partial`), false);
  assert.equal(setupMode(receipt, "1.0.0", false), null);
  assert.equal(setupMode(receipt, "1.1.0", false), "update");
  assert.equal(setupMode(receipt, "1.0.0", true), "repair");
  writeFileSync(path, '{"schema":2,"version":"1.0.0"}');
  assert.equal(readReceipt(path), null);
  t.diagnostic("a damaged receipt means setup runs again");
});

test("--repair asks for the Setup window again", () => {
  assert.equal(parseShellArgs(["--repair"], {}).repair, true);
  assert.equal(parseShellArgs([], {}).repair, false);
});

test("the system check answer is read strictly, and a block is said in the owner's words", () => {
  const answer = parseSystemCheck(JSON.stringify(CHECK));
  assert.ok(answer !== null);
  assert.equal(answer.ready, false);
  assert.equal(blockingSummary(answer), "Raiker needs at least 4 GB of memory.");
  assert.equal(parseSystemCheck("{"), null);
  assert.equal(parseSystemCheck(JSON.stringify({ ...CHECK, ready: "no" })), null);
  assert.equal(parseSystemCheck(JSON.stringify({ ...CHECK, checks: [{ id: "x", label: "X", state: "bad" }] })), null);
});

test("a raw failure becomes one sentence", () => {
  assert.match(plainCause("ENOSPC: no space left on device"), /out of disk space/);
  assert.match(plainCause("EACCES: permission denied, mkdir"), /not allowed to write/);
  assert.match(plainCause("Raiker's host did not become ready within 120 seconds."), /took too long/);
  assert.match(plainCause("Raiker could not start its host: spawn ENOENT"), /missing/);
  assert.match(plainCause("Raiker's host stopped before it was ready (exit code 1)."), /stopped while it was starting/);
  assert.match(plainCause("something else"), /did not finish/);
});

function fakeHost(body: string): string {
  const dir = mkdtempSync(join(tmpdir(), "raiker-check-host-"));
  const script = join(dir, "host.js");
  writeFileSync(script, body);
  chmodSync(script, 0o755);
  return script;
}

test("the system check is the host's own, read from the file it writes", { skip: process.platform === "win32" }, async () => {
  const script = fakeHost(
    `const args = process.argv.slice(2);
     if (args[0] !== "system-check" || args[1] !== "--output") process.exit(9);
     require("fs").writeFileSync(args[2], ${JSON.stringify(JSON.stringify(CHECK))});
     process.exit(1);`,
  );
  const answer = await runSystemCheck([process.execPath, script], join(tmpdir(), `check-${process.pid}-a.json`), 5000);
  assert.deepEqual(answer.blocking, ["memory"]);
});

test("a system check that gives no answer stops setup", { skip: process.platform === "win32" }, async () => {
  const script = fakeHost("process.exit(2);");
  await assert.rejects(
    runSystemCheck([process.execPath, script], join(tmpdir(), `check-${process.pid}-b.json`), 5000),
    (error: unknown) => error instanceof SetupStageError && /no answer/.test(error.message),
  );
});

function response(status: number, body: unknown, type = "application/json") {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (name: string) => (name.toLowerCase() === "content-type" ? type : null) },
    json: async () => body,
  };
}

test("verification needs an open store, text search and the interface", async () => {
  const healthy = { status: "ok", store: "ok", text_search_engine: "fts5" };
  const ok = await verifyHost("http://127.0.0.1:8765/", async (url) =>
    url.endsWith("/api/health") ? response(200, healthy) : response(200, "", "text/html; charset=utf-8"),
  );
  assert.equal(ok.ok, true);
  const locked = await verifyHost("http://127.0.0.1:8765", async () => response(200, { store: "unavailable", reason: "vault_key_invalid" }));
  assert.equal(locked.ok, false);
  assert.match(locked.detail, /vault_key_invalid/);
  const noUi = await verifyHost("http://127.0.0.1:8765/", async (url) =>
    url.endsWith("/api/health") ? response(200, healthy) : response(404, "", "text/plain"),
  );
  assert.equal(noUi.ok, false);
});
