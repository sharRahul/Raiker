// SPDX-License-Identifier: Apache-2.0
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, chmodSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import { HostStartError, parseReady, resolveHostCommand, startHost } from "../src/host";

test("the ready file must name a loopback Raiker", () => {
  assert.deepEqual(parseReady('{"url":"http://127.0.0.1:8765/","joined":true}'), {
    url: "http://127.0.0.1:8765/",
    joined: true,
  });
  assert.equal(parseReady('{"url":"http://203.0.113.9:8765/"}'), null);
  assert.equal(parseReady("{"), null);
  assert.equal(parseReady('{"port":8765}'), null);
});

test("an explicit command wins; a source checkout has no bundled host", () => {
  assert.deepEqual(
    resolveHostCommand({ explicit: ["x"], resourcesPath: "/nowhere", platform: "linux", packaged: true }),
    ["x"],
  );
  assert.equal(resolveHostCommand({ explicit: null, resourcesPath: "/nowhere", platform: "linux", packaged: false }), null);
  assert.equal(resolveHostCommand({ explicit: null, resourcesPath: "/nowhere", platform: "linux", packaged: true }), null);
});

function fakeHost(body: string): string {
  const dir = mkdtempSync(join(tmpdir(), "raiker-host-"));
  const script = join(dir, "host.js");
  writeFileSync(script, body);
  chmodSync(script, 0o755);
  return script;
}

test("startHost resolves when the host writes its ready file", { skip: process.platform === "win32" }, async () => {
  // The fake host receives `--no-browser --ready-file PATH`, exactly as raiker-app does.
  const script = fakeHost(
    `const p = process.argv[process.argv.indexOf("--ready-file") + 1];
     setTimeout(() => require("fs").writeFileSync(p, JSON.stringify({ url: "http://127.0.0.1:8799/", joined: false })), 200);
     setTimeout(() => {}, 2000);`,
  );
  const ready = await startHost([process.execPath, script], join(tmpdir(), `ready-${process.pid}-a.json`), 5000);
  assert.deepEqual(ready, { url: "http://127.0.0.1:8799/", joined: false });
});

test("startHost reports a host that exits before it is ready", { skip: process.platform === "win32" }, async () => {
  const script = fakeHost("process.exit(3);");
  await assert.rejects(
    startHost([process.execPath, script], join(tmpdir(), `ready-${process.pid}-b.json`), 5000),
    (error: unknown) => error instanceof HostStartError && /exit code 3/.test(error.message),
  );
});
