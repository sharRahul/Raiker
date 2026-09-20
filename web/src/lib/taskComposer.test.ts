// COMPOSER-10 — one instruction field, and the timing said even while hidden.
import { describe, expect, it } from "vitest";
import {
  MAX_DERIVED_TITLE,
  RECURRENCE_INTERVAL_MS,
  TASK_CADENCES,
  cadenceFor,
  deriveTitle,
  nextRuns,
  primaryAction,
  runModeFor,
  scheduleSummary,
  timingFor,
  wantsStartTime,
} from "./taskComposer";
import { AGENT_CADENCES } from "./agentCadence";

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

/**
 * REM-TASK-01 — when work runs, and how it runs, asked as two questions.
 *
 * The chip row was one control answering two questions. These pin the
 * translation both ways, so the four shapes the runtime accepts are exactly the
 * four the composer can reach — no more, and no fewer.
 */
describe("timing and run mode", () => {
  it("round-trips every shape the runtime accepts", () => {
    for (const cadence of ["now", "once", "routine", "background"] as const) {
      expect(cadenceFor(timingFor(cadence), runModeFor(cadence))).toBe(cadence);
    }
  });

  it("asks for a background agent from the timing it actually has", () => {
    expect(cadenceFor("now", "background")).toBe("background");
    // A background agent starts now; there is no scheduled variant to compose.
    expect(cadenceFor("at", "background")).toBe("once");
    expect(cadenceFor("repeating", "background")).toBe("routine");
  });
});

/**
 * REM-TASK-01 — the preview is the scheduler's own arithmetic, or it is a lie.
 */
describe("the next runs a schedule would produce", () => {
  const now = new Date("2026-09-20T12:00:00Z");

  it("has nothing to preview for work that runs now", () => {
    expect(nextRuns({ cadence: "now", every: "daily", startAt: "", now })).toEqual([]);
    expect(nextRuns({ cadence: "background", every: "daily", startAt: "", now })).toEqual([]);
  });

  it("previews a one-off as the single run it is", () => {
    const runs = nextRuns({ cadence: "once", every: "daily", startAt: "2026-09-21T09:00:00Z", now });
    expect(runs).toHaveLength(1);
    expect(runs[0].toISOString()).toBe("2026-09-21T09:00:00.000Z");
  });

  it("anchors a routine to the slot the owner picked", () => {
    const runs = nextRuns({
      cadence: "routine", every: "daily", startAt: "2026-09-21T09:00:00Z", now,
    });
    expect(runs.map((run) => run.toISOString())).toEqual([
      "2026-09-21T09:00:00.000Z",
      "2026-09-22T09:00:00.000Z",
      "2026-09-23T09:00:00.000Z",
    ]);
  });

  it("skips slots that have already passed rather than owing them", () => {
    // Four days of daily slots are behind `now`. The scheduler skips them, so
    // the preview must not imply four runs are queued up.
    const runs = nextRuns({
      cadence: "routine", every: "daily", startAt: "2026-09-16T09:00:00Z", now, count: 1,
    });
    expect(runs.map((run) => run.toISOString())).toEqual(["2026-09-21T09:00:00.000Z"]);
  });

  it("says nothing at all until a first run has been chosen", () => {
    expect(nextRuns({ cadence: "routine", every: "daily", startAt: "", now })).toEqual([]);
    expect(nextRuns({ cadence: "routine", every: "daily", startAt: "not a time", now })).toEqual([]);
  });

  it("covers every repeating cadence the composer offers", () => {
    const offered = AGENT_CADENCES.filter((entry) => entry.id !== "background").map((e) => e.id);
    expect(offered.every((id) => id in RECURRENCE_INTERVAL_MS)).toBe(true);
  });
});
