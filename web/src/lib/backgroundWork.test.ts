import { describe, expect, it } from "vitest";
import { backgroundLabel, backgroundSummary } from "./backgroundWork";

const now = new Date("2026-10-03T12:00:00Z");
const at = (iso: string) => ({ updated_at: iso, completed_at: iso });

describe("backgroundSummary", () => {
  it("counts active work the way the rail lists it, and failures from today only", () => {
    const summary = backgroundSummary(
      [
        { status: "running", ...at("2026-10-03T11:00:00Z") },
        { status: "waiting_for_approval", ...at("2026-10-03T11:00:00Z") },
        { status: "failed", ...at("2026-10-03T08:00:00Z") },
        { status: "failed", ...at("2026-10-01T08:00:00Z") },
        { status: "completed", ...at("2026-10-03T11:00:00Z") },
      ],
      now,
    );
    expect(summary).toEqual({ active: 2, waiting: 1, failed: 1 });
  });

  it("names every non-zero count, and says when nothing is running", () => {
    expect(backgroundLabel({ active: 0, waiting: 0, failed: 0 })).toBe(
      "Background work: nothing running",
    );
    expect(backgroundLabel({ active: 1, waiting: 0, failed: 2 })).toBe(
      "Background work: 1 running, 2 failed today",
    );
    expect(backgroundLabel(null)).toBe("Background work");
  });
});
