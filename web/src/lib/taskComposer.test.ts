// COMPOSER-10 — one instruction field, and the timing said even while hidden.
import { describe, expect, it } from "vitest";
import {
  MAX_DERIVED_TITLE,
  TASK_CADENCES,
  deriveTitle,
  primaryAction,
  scheduleSummary,
  wantsStartTime,
} from "./taskComposer";

describe("deriveTitle", () => {
  it("takes the instruction's first sentence", () => {
    // Two required fields at the top of a form is two chances to ask the same
    // question twice, and the second answer is the first one shortened by hand.
    expect(deriveTitle("Summarise security news. Flag anything urgent.")).toBe(
      "Summarise security news",
    );
  });

  it("uses the whole instruction when there is no sentence break", () => {
    expect(deriveTitle("Review today's priorities")).toBe("Review today's priorities");
  });

  it("collapses the whitespace a pasted instruction carries", () => {
    expect(deriveTitle("  Check\n\n the   backups ")).toBe("Check the backups");
  });

  it("is empty for an empty instruction rather than a placeholder", () => {
    expect(deriveTitle("")).toBe("");
    expect(deriveTitle("   \n ")).toBe("");
  });

  it("cuts a long first sentence on a word boundary and says it was cut", () => {
    const long = `${"alpha ".repeat(60)}end.`;
    const title = deriveTitle(long);
    expect(title.length).toBeLessThanOrEqual(MAX_DERIVED_TITLE + 1);
    expect(title.endsWith("…")).toBe(true);
    expect(title).not.toMatch(/alph…$/);
  });

  it("does not treat a decimal point as the end of a sentence", () => {
    expect(deriveTitle("Keep spend under 12.50 a day")).toBe("Keep spend under 12.50 a day");
  });
});

describe("the primary action", () => {
  it("names what pressing it will do, per shape of work", () => {
    expect(primaryAction("now")).toBe("Create task");
    expect(primaryAction("once")).toBe("Schedule task");
    expect(primaryAction("routine")).toBe("Create routine");
    expect(primaryAction("background")).toBe("Start background agent");
  });

  it("covers every cadence the chips offer", () => {
    for (const entry of TASK_CADENCES) {
      expect(primaryAction(entry.id)).toBe(entry.action);
    }
  });
});

describe("wantsStartTime", () => {
  it("is true only for the two shapes anchored to a slot", () => {
    // A routine without one means "daily from whenever I pressed the button",
    // which is not a schedule anybody chose.
    expect(wantsStartTime("once")).toBe(true);
    expect(wantsStartTime("routine")).toBe(true);
    expect(wantsStartTime("now")).toBe(false);
    expect(wantsStartTime("background")).toBe(false);
  });
});

describe("scheduleSummary", () => {
  const base = { every: "daily", everyLabel: "Daily", startAt: "" };

  it("says what an unscheduled task will do", () => {
    expect(scheduleSummary({ ...base, cadence: "now" })).toBe("Runs now");
    expect(scheduleSummary({ ...base, cadence: "background" })).toBe(
      "Runs until its work is done",
    );
  });

  it("asks for the missing half rather than implying a time", () => {
    expect(scheduleSummary({ ...base, cadence: "once" })).toBe("Once — pick a time");
    expect(scheduleSummary({ ...base, cadence: "routine" })).toBe("Daily — pick a first run");
  });

  it("states the chosen time, so hiding the details never hides the choice", () => {
    const summary = scheduleSummary({
      ...base,
      cadence: "routine",
      startAt: "2026-09-11T08:00",
    });
    expect(summary).toContain("Daily, from");
    expect(summary).toContain("08:00");
  });

  it("shows an unparseable value rather than swallowing it", () => {
    expect(scheduleSummary({ ...base, cadence: "once", startAt: "not-a-date" })).toContain(
      "not-a-date",
    );
  });
});
