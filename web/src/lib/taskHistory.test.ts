import { describe, expect, it } from "vitest";
import {
  attemptBadge,
  attemptOutcomeLabel,
  attemptTitle,
  eventHref,
  historySummary,
  newestFirst,
  taskDetailHref,
} from "./taskHistory";
import type { TaskAttemptView, TaskView } from "./apiTypes";

function attempt(over: Partial<TaskAttemptView> = {}): TaskAttemptView {
  return {
    index: 1,
    kind: "run",
    started_at: "2026-09-15T09:00:00Z",
    ended_at: "2026-09-15T09:05:00Z",
    outcome: "completed",
    summary: "Done.",
    approval_id: null,
    events: [],
    ...over,
  };
}

function task(over: Partial<TaskView> = {}): TaskView {
  return {
    task_id: "task_1",
    session_id: "sess_inbox_owner",
    status: "completed",
    title: "Nightly digest",
    objective: "Summarise the day",
    current_step: null,
    progress_percent: null,
    created_at: "2026-09-15T08:00:00Z",
    updated_at: "2026-09-15T09:05:00Z",
    completed_at: null,
    summary: null,
    project_id: null,
    ...over,
  };
}

describe("taskDetailHref", () => {
  it("is one spelling of the canonical address, whoever links to it", () => {
    expect(taskDetailHref("task_1")).toBe("#/tasks?task=task_1");
  });

  it("encodes an id rather than pasting it into the query", () => {
    expect(taskDetailHref("task 1&x=2")).toBe("#/tasks?task=task%201%26x%3D2");
  });
});

describe("attempt outcomes", () => {
  it("never reports an unsettled run as anything reassuring", () => {
    // The row an owner sent here by `outcome_unknown` came to find.
    expect(attemptBadge("in_progress")).toBe("active");
    expect(attemptOutcomeLabel("in_progress")).toBe("still running");
  });

  it("shows an outcome it does not recognise verbatim rather than hiding it", () => {
    expect(attemptOutcomeLabel("something_new")).toBe("something_new");
    expect(attemptBadge("something_new")).toBe("idle");
  });

  it("names a continuation for what released it", () => {
    expect(attemptTitle(attempt({ kind: "continuation", index: 2 }))).toBe(
      "Attempt 2 · after your decision",
    );
    expect(attemptTitle(attempt({ index: 1 }))).toBe("Attempt 1");
    expect(attemptTitle(attempt({ kind: "record", index: 0 }))).toBe("Recorded");
  });
});

describe("historySummary", () => {
  it("says so plainly when nothing has run", () => {
    expect(historySummary([attempt({ kind: "record", index: 0 })])).toBe(
      "This task has not run yet.",
    );
  });

  it("counts attempts, and the two outcomes worth leading with", () => {
    expect(
      historySummary([
        attempt({ kind: "record", index: 0 }),
        attempt({ index: 1, outcome: "failed" }),
        attempt({ index: 2, outcome: "waiting_for_approval" }),
        attempt({ index: 3, outcome: "completed" }),
      ]),
    ).toBe("3 attempts · 1 did not complete · 1 waited on a decision.");
  });
});

describe("newestFirst", () => {
  it("reverses the derivation order without mutating the server's answer", () => {
    const attempts = [attempt({ index: 1 }), attempt({ index: 2 })];
    expect(newestFirst(attempts).map((entry) => entry.index)).toEqual([2, 1]);
    expect(attempts.map((entry) => entry.index)).toEqual([1, 2]);
  });
});

describe("eventHref", () => {
  it("opens the decision when the attempt named one", () => {
    expect(eventHref(task(), attempt({ approval_id: "apr_1" }))).toBe(
      "#/approvals?session=sess_inbox_owner",
    );
  });

  it("opens the task's own conversation once it holds something", () => {
    expect(
      eventHref(task({ thread_session_id: "sess_thread", thread_turns: 2 }), attempt()),
    ).toBe("#/new-chat?session=sess_thread");
  });

  it("offers no conversation on the filing record, which produced none", () => {
    expect(
      eventHref(task({ thread_session_id: "sess_thread", thread_turns: 2 }), attempt({ kind: "record", index: 0 })),
    ).toBeNull();
  });

  it("offers nothing rather than a link to an empty transcript", () => {
    expect(
      eventHref(task({ thread_session_id: "sess_thread", thread_turns: 0 }), attempt()),
    ).toBeNull();
    expect(eventHref(task(), attempt())).toBeNull();
  });
});
