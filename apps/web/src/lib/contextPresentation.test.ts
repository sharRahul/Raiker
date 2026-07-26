import { describe, expect, it } from "vitest";
import { formatContextUsage } from "./contextPresentation";

describe("formatContextUsage", () => {
  it("formats a bounded used/total context label and percentage", () => {
    expect(formatContextUsage(63_900, 1_000_000)).toEqual({
      label: "63.9K / 1.0M (6%)",
      percent: 6,
    });
  });

  it("never renders a context bar beyond one hundred percent", () => {
    expect(formatContextUsage(1_200, 1_000).percent).toBe(100);
  });
});
