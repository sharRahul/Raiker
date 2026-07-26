import { describe, expect, it } from "vitest";
import { AGENT_CADENCES, cadenceLabel } from "./agentCadence";

describe("agent cadences", () => {
  it("offers only cadences the server accepts", () => {
    // The server refuses an unknown `recurrence` rather than storing it as a
    // one-shot, so this list must stay a subset of what it will honour.
    expect(AGENT_CADENCES.map((cadence) => cadence.id)).toEqual([
      "continuous",
      "hourly",
      "daily",
      "weekly",
      "background",
    ]);
  });

  it("labels each running cadence in the reader's terms", () => {
    expect(cadenceLabel("continuous")).toBe("Keeps going until stopped");
    expect(cadenceLabel("weekly")).toBe("Runs weekly");
    expect(cadenceLabel("background")).toBe("One background run");
  });

  it("shows an unrecognised cadence verbatim instead of calling it a one-shot", () => {
    // A schedule created by another client must not be silently mislabelled.
    expect(cadenceLabel("fortnightly")).toBe("Repeats (fortnightly)");
  });
});
