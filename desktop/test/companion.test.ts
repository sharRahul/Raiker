// SPDX-License-Identifier: Apache-2.0
import assert from "node:assert/strict";
import { test } from "node:test";

import { attentionCount, isAppHash, quickEntryBounds, QUICK_ENTRY_SIZE, trayTooltip, withDot } from "../src/companion";

test("Quick Entry is 560×120, centred on the display, a quarter of the way down", () => {
  const bounds = quickEntryBounds({ x: 1920, y: 0, width: 1440, height: 900 });
  assert.deepEqual(bounds, { x: 1920 + 440, y: 225, width: QUICK_ENTRY_SIZE.width, height: QUICK_ENTRY_SIZE.height });
});

test("only an in-app route opens in a new window, never a URL", () => {
  assert.equal(isAppHash("#/projects?project=proj_1"), true);
  assert.equal(isAppHash("#/work?tab=projects&project=a%20b"), true);
  for (const bad of ["https://example.com", "#//evil.example", "javascript:alert(1)", "#/<script>", "#/" + "a".repeat(600), 7]) {
    assert.equal(isAppHash(bad), false, String(bad));
  }
});

test("the tray says how many decisions wait, in words", () => {
  assert.equal(trayTooltip(0), "Raiker");
  assert.equal(trayTooltip(1), "Raiker — 1 decision is waiting for you");
  assert.equal(trayTooltip(3), "Raiker — 3 decisions are waiting for you");
  assert.equal(attentionCount(2), 2);
  for (const bad of [-1, 1.5, "3", null]) assert.equal(attentionCount(bad), 0);
});

test("the attention dot is painted in the top-right corner of a copy", () => {
  const size = 32;
  const icon = new Uint8Array(size * size * 4);
  const dotted = withDot(icon, size, size);
  const at = (x: number, y: number) => dotted[(y * size + x) * 4 + 3];
  assert.equal(at(size - 8, 8), 255);
  assert.equal(at(2, size - 2), 0);
  assert.equal(icon[(8 * size + size - 8) * 4 + 3], 0, "the original is untouched");
});
