// SPDX-License-Identifier: Apache-2.0
import assert from "node:assert/strict";
import { test } from "node:test";

import { parseHostCommand, parseShellArgs } from "../src/args";

test("attach mode takes a loopback URL in either flag form", () => {
  assert.equal(parseShellArgs(["--raiker-url", "http://127.0.0.1:8765/#/x"], {}).url, "http://127.0.0.1:8765/");
  assert.equal(parseShellArgs(["--raiker-url=http://localhost:9000"], {}).url, "http://localhost:9000/");
});

test("a non-loopback URL is rejected by name, not silently opened", () => {
  const args = parseShellArgs(["--raiker-url", "http://10.0.0.5:8765/"], {});
  assert.equal(args.url, null);
  assert.equal(args.rejectedUrl, "http://10.0.0.5:8765/");
});

test("no URL means start a host", () => {
  const args = parseShellArgs(["."], { RAIKER_HOST_COMMAND: '["raiker-app","--workspace","/tmp/w"]' });
  assert.equal(args.url, null);
  assert.deepEqual(args.hostCommand, ["raiker-app", "--workspace", "/tmp/w"]);
});

test("a malformed host command is no command", () => {
  for (const raw of [undefined, "", "raiker-app", "[]", '[""]', "[1]", "{}"]) {
    assert.equal(parseHostCommand(raw), null, String(raw));
  }
});
