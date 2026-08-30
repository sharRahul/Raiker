import { afterEach, describe, expect, it } from "vitest";
import {
  clampExplorerWidth,
  DEFAULT_EXPLORER_WIDTH,
  MAX_EXPLORER_WIDTH,
  MIN_EXPLORER_WIDTH,
  readExplorerOpen,
  readExplorerWidth,
  rememberExplorerOpen,
  rememberExplorerWidth,
} from "./buildExplorer";

afterEach(() => window.localStorage.clear());

// B13 — the stored width is the one input here a person can edit by hand, so
// the clamp is applied on the way in *and* on the way out. A panel that has
// taken the whole window because storage said `99999` is not a preference
// anyone set.
describe("buildExplorer", () => {
  it("clamps a width to something a tree and a file can both live in", () => {
    expect(clampExplorerWidth(10)).toBe(MIN_EXPLORER_WIDTH);
    expect(clampExplorerWidth(99_999)).toBe(MAX_EXPLORER_WIDTH);
    expect(clampExplorerWidth(320)).toBe(320);
    expect(clampExplorerWidth(Number.NaN)).toBe(DEFAULT_EXPLORER_WIDTH);
  });

  it("clamps what it reads back, not only what it writes", () => {
    window.localStorage.setItem("raiker.build.explorerWidth", "99999");
    expect(readExplorerWidth()).toBe(MAX_EXPLORER_WIDTH);
    window.localStorage.setItem("raiker.build.explorerWidth", "not-a-number");
    expect(readExplorerWidth()).toBe(DEFAULT_EXPLORER_WIDTH);
  });

  it("round-trips a width and an open panel", () => {
    rememberExplorerWidth(360);
    expect(readExplorerWidth()).toBe(360);
    expect(readExplorerOpen()).toBe(false);
    rememberExplorerOpen(true);
    expect(readExplorerOpen()).toBe(true);
    rememberExplorerOpen(false);
    expect(readExplorerOpen()).toBe(false);
  });

  it("defaults rather than throwing when there is nothing stored", () => {
    expect(readExplorerWidth()).toBe(DEFAULT_EXPLORER_WIDTH);
    expect(readExplorerOpen()).toBe(false);
  });
});
