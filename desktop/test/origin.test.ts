// SPDX-License-Identifier: Apache-2.0
import assert from "node:assert/strict";
import { test } from "node:test";

import { classifyNavigation, decidePermission, loopbackOrigin } from "../src/origin";

const APP = "http://127.0.0.1:8765";

test("only plain-http loopback addresses are Raiker origins", () => {
  assert.equal(loopbackOrigin("http://127.0.0.1:8765/#/home"), APP);
  assert.equal(loopbackOrigin("http://localhost:9000/"), "http://localhost:9000");
  assert.equal(loopbackOrigin("http://[::1]:8765/"), "http://[::1]:8765");
  for (const refused of [
    "https://127.0.0.1:8765/",
    "http://192.168.1.4:8765/",
    "http://127.0.0.1.example.com/",
    "http://user:pw@127.0.0.1:8765/",
    "file:///etc/passwd",
    "not a url",
  ]) {
    assert.equal(loopbackOrigin(refused), null, refused);
  }
});

test("navigation stays on the Raiker origin and sends everything else away", () => {
  assert.equal(classifyNavigation(`${APP}/#/settings`, APP), "same-window");
  assert.equal(classifyNavigation("http://127.0.0.1:8770/", APP), "app-window");
  assert.equal(classifyNavigation("https://docs.anthropic.com/", APP), "external");
  assert.equal(classifyNavigation("http://example.com/", APP), "external");
  assert.equal(classifyNavigation("mailto:owner@example.com", APP), "external");
  for (const denied of [
    "file:///C:/Windows/System32/",
    "javascript:alert(1)",
    "data:text/html,<p>x</p>",
    "raiker-evil://run",
    "https://user:pw@example.com/",
  ]) {
    assert.equal(classifyNavigation(denied, APP), "deny", denied);
  }
});

test("permissions are granted only to the Raiker origin and only those Raiker uses", () => {
  assert.equal(decidePermission("notifications", `${APP}/`, APP), true);
  assert.equal(decidePermission("clipboard-sanitized-write", `${APP}/`, APP), true);
  assert.equal(decidePermission("media", `${APP}/`, APP, ["audio"]), true);
  assert.equal(decidePermission("media", `${APP}/`, APP, ["audio", "video"]), false);
  assert.equal(decidePermission("media", `${APP}/`, APP, []), false);
  assert.equal(decidePermission("geolocation", `${APP}/`, APP), false);
  assert.equal(decidePermission("notifications", "https://example.com/", APP), false);
  assert.equal(decidePermission("notifications", "http://127.0.0.1:9999/", APP), false);
});
