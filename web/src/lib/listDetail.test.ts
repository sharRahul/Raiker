import { describe, expect, it } from "vitest";
import {
  clampListWidth,
  DETAIL_MIN_PX,
  hashWithItem,
  itemFromHash,
  LIST_MIN_PX,
  stepSelection,
} from "./listDetail";

describe("list and detail (QUI-L02)", () => {
  it("reads and writes the selected item in the address, keeping the rest", () => {
    expect(itemFromHash("#/extensions?tab=services&item=github")).toBe("github");
    expect(itemFromHash("#/extensions?tab=services")).toBeNull();
    expect(hashWithItem("#/extensions?tab=services", "github")).toBe(
      "#/extensions?tab=services&item=github",
    );
    expect(hashWithItem("#/extensions?tab=services&item=github", null)).toBe(
      "#/extensions?tab=services",
    );
    expect(hashWithItem("#/models", "a b")).toBe("#/models?item=a+b");
  });

  it("never lets a drag make either side unreadable", () => {
    expect(clampListWidth(40, 1000)).toBe(LIST_MIN_PX);
    expect(clampListWidth(900, 1000)).toBe(1000 - DETAIL_MIN_PX);
    expect(clampListWidth(300, 1000)).toBe(300);
    expect(clampListWidth(300, 400)).toBe(LIST_MIN_PX);
  });

  it("steps the selection with the arrow keys without wrapping", () => {
    const ids = ["a", "b", "c"];
    expect(stepSelection(ids, null, 1)).toBe("a");
    expect(stepSelection(ids, null, -1)).toBe("c");
    expect(stepSelection(ids, "b", 1)).toBe("c");
    expect(stepSelection(ids, "c", 1)).toBe("c");
    expect(stepSelection(ids, "a", -1)).toBe("a");
    expect(stepSelection([], null, 1)).toBeNull();
  });
});
