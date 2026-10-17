// SPDX-License-Identifier: Apache-2.0
import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import { DEFAULT_STATE, loadState, sanitizeState, saveState } from "../src/windowState";

const SCREEN = [{ x: 0, y: 0, width: 1920, height: 1080 }];

test("a saved window on a connected display reopens where it was", () => {
  const state = sanitizeState({ bounds: { x: 100, y: 80, width: 1400, height: 900 }, maximized: true }, SCREEN);
  assert.deepEqual(state, { bounds: { x: 100, y: 80, width: 1400, height: 900 }, maximized: true });
});

test("a window on an unplugged display is re-centred, keeping its size", () => {
  const state = sanitizeState({ bounds: { x: 4000, y: 80, width: 1400, height: 900 }, maximized: false }, SCREEN);
  assert.deepEqual(state, { bounds: { width: 1400, height: 900 }, maximized: false });
});

test("sizes are clamped between the minimum and the largest display", () => {
  const state = sanitizeState({ bounds: { width: 100, height: 99999 } }, SCREEN);
  assert.deepEqual(state.bounds, { width: 720, height: 1080 });
});

test("garbage falls back to the default", () => {
  for (const raw of [null, 1, "x", {}, { bounds: { width: "a", height: 2 } }]) {
    assert.deepEqual(sanitizeState(raw, SCREEN), DEFAULT_STATE);
  }
});

test("state round-trips through its file", () => {
  const file = join(mkdtempSync(join(tmpdir(), "raiker-state-")), "nested", "window-state.json");
  saveState(file, { bounds: { x: 10, y: 20, width: 1000, height: 700 }, maximized: false });
  assert.deepEqual(loadState(file, SCREEN), { bounds: { x: 10, y: 20, width: 1000, height: 700 }, maximized: false });
  assert.deepEqual(loadState(join(file, "missing"), SCREEN), DEFAULT_STATE);
});
