import { describe, expect, it } from "vitest";
import { formatContextUsage, formatCost, sourceNote, spendShares } from "./contextPresentation";

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

describe("formatCost", () => {
  it("keeps four decimals for sub-cent amounts so a real charge is not rounded to zero", () => {
    // API costs are routinely fractions of a cent; two decimals would render a
    // genuine charge as "$0.00" and read as free.
    expect(formatCost("0.0143", "USD", "en-US")).toBe("$0.0143");
  });

  it("uses two decimals once the amount is worth more than a cent", () => {
    expect(formatCost("2.41", "USD", "en-US")).toBe("$2.41");
  });

  it("returns null for an unknown amount rather than a zero", () => {
    expect(formatCost(null, "USD")).toBeNull();
    expect(formatCost(undefined, "USD")).toBeNull();
    expect(formatCost("", "USD")).toBeNull();
    expect(formatCost("not-a-number", "USD")).toBeNull();
  });

  it("renders a genuine zero, which means free rather than unknown", () => {
    expect(formatCost("0", "USD", "en-US")).toBe("$0.00");
  });

  it("falls back to a plain amount for an unknown currency code", () => {
    expect(formatCost("1.5", "NOTACURRENCY", "en-US")).toBe("1.50 NOTACURRENCY");
  });
});

describe("sourceNote", () => {
  it("names each price source so a pulled price is never mistaken for a shipped one", () => {
    expect(sourceNote("provider")).toBe("provider-reported");
    expect(sourceNote("owner")).toBe("your configured price");
    expect(sourceNote("config", "2026-07")).toBe("list price, as of 2026-07");
  });

  it("returns null for an absent or unknown source", () => {
    expect(sourceNote(null)).toBeNull();
    expect(sourceNote("something-new")).toBeNull();
  });
});

describe("spendShares", () => {
  it("gives each provider its share of total spend", () => {
    const shares = spendShares([
      { id: "anthropic-hosted", cost: "3" },
      { id: "openai-hosted", cost: "1" },
    ]);
    expect(shares).toEqual({ "anthropic-hosted": 75, "openai-hosted": 25 });
  });

  it("omits providers with no cost rather than showing a zero bar", () => {
    const shares = spendShares([
      { id: "anthropic-hosted", cost: "2" },
      { id: "local", cost: null },
      { id: "unused", cost: "0" },
    ]);
    expect(shares).toEqual({ "anthropic-hosted": 100 });
  });

  it("returns no shares at all when nothing has been spent", () => {
    // A share of zero has no meaning, and a row of 0% bars would imply the
    // opposite of "nothing to show".
    expect(spendShares([{ id: "a", cost: "0" }, { id: "b", cost: null }])).toEqual({});
    expect(spendShares([])).toEqual({});
  });
});
