import { describe, expect, it } from "vitest";
import { editablePatch } from "./editablePatch";

describe("BUG-271 editable patch", () => {
  it("offers the proposal's own patch for apply_patch only", () => {
    expect(editablePatch("apply_patch", { patch: "--- /dev/null\n+++ notes.md\n" })).toBe("--- /dev/null\n+++ notes.md\n");
    expect(editablePatch("write_file", { patch: "x" })).toBeNull();
    expect(editablePatch("apply_patch", { patch: "  " })).toBeNull();
    expect(editablePatch("apply_patch", null)).toBeNull();
  });
});
