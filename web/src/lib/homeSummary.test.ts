import { describe, expect, it } from "vitest";
import { homeFact, homeGreeting, weekOutcomes } from "./homeSummary";

describe("homeGreeting", () => {
  it("welcomes a first day and greets by time of day after it", () => {
    expect(homeGreeting("Rahul", true, 9)).toBe("Welcome, Rahul");
    expect(homeGreeting("Rahul", false, 9)).toBe("Good morning, Rahul");
    expect(homeGreeting("Rahul", false, 13)).toBe("Good afternoon, Rahul");
    expect(homeGreeting("Rahul", false, 21)).toBe("Good evening, Rahul");
    expect(homeGreeting("  ", false, 9)).toBe("Good morning");
  });
});

describe("homeFact", () => {
  it("says something only when a decision is waiting", () => {
    expect(homeFact(0)).toBeNull();
    expect(homeFact(1)).toBe("1 decision waiting");
    expect(homeFact(3)).toBe("3 decisions waiting");
  });
});

describe("weekOutcomes", () => {
  const now = new Date("2026-10-21T12:00:00Z");
  const href = (id: string) => `#/tasks?task=${id}`;
  it("names completed work from the last seven days, newest first", () => {
    const rows = weekOutcomes(
      [
        { task_id: "a", title: "Merge the login fix", status: "completed", completed_at: "2026-10-19T10:00:00Z", updated_at: "" },
        { task_id: "b", title: "Send the proposal", status: "completed", completed_at: "2026-10-20T10:00:00Z", updated_at: "" },
        { task_id: "c", title: "Too old", status: "completed", completed_at: "2026-10-10T10:00:00Z", updated_at: "" },
        { task_id: "d", title: "Failed import", status: "failed", completed_at: "2026-10-20T10:00:00Z", updated_at: "" },
        { task_id: "e", title: "  ", status: "completed", completed_at: "2026-10-20T10:00:00Z", updated_at: "" },
      ],
      [{ goal_id: "g1", title: "Book the trip", status: "completed", settled_at: "2026-10-21T08:00:00Z", updated_at: "" }],
      now,
      href,
    );
    expect(rows.map((row) => row.title)).toEqual(["Book the trip", "Send the proposal", "Merge the login fix"]);
    expect(rows[1].href).toBe("#/tasks?task=b");
    expect(rows[0].href).toBe("#/work?tab=goals&record=g1");
  });
});
