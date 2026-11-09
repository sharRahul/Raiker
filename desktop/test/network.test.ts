// SPDX-License-Identifier: Apache-2.0
import assert from "node:assert/strict";
import { test } from "node:test";
import { isLoopbackNetworkRequest } from "../src/network";

test("the shell permits local HTTP and websocket resources without remote DNS", () => {
  for (const allowed of ["http://127.0.0.1:8765/api/health", "http://localhost:9000/", "ws://[::1]:8765/terminal"]) {
    assert.equal(isLoopbackNetworkRequest(allowed), true, allowed);
  }
});

test("remote resources and lookalike local names cannot bypass the shell policy", () => {
  for (const refused of [
    "https://dns.google/dns-query", "https://8.8.8.8/", "ws://example.org/",
    "http://127.0.0.2/", "http://127.0.0.1.example.org/", "http://localhost.example.org/",
    "http://user:password@127.0.0.1/", "https://example.org@127.0.0.1/",
    "file:///etc/passwd", "data:text/html,test", "not a URL",
  ]) {
    assert.equal(isLoopbackNetworkRequest(refused), false, refused);
  }
});
