import { describe, expect, it } from "vitest";

import { PAGE_SIZE, page } from "./pagination";

describe("Work list pagination (QUI-L12)", () => {
  it("shows the first 50 rows, then a page more each time", () => {
    const items = Array.from({ length: 120 }, (_, index) => index);
    expect(page(items, PAGE_SIZE)).toHaveLength(50);
    expect(page(items, PAGE_SIZE * 2)).toHaveLength(100);
    expect(page(items, PAGE_SIZE * 3)).toHaveLength(120);
  });

  it("never shows fewer than one page", () => {
    expect(page([1, 2, 3], 0)).toEqual([1, 2, 3]);
  });
});
