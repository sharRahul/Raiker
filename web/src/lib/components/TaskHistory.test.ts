/**
 * BR-D03 — a scheduled Build task's attempt says what its turn may claim about
 * its change, from the same outcome a Build turn shows; other tasks do not.
 */
import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import TaskHistory from "./TaskHistory.svelte";
import { stubFetch } from "../test-helpers";

function detail(surface: string): Record<string, unknown> {
  return {
    task: {
      task_id: "task_1", session_id: "sess_inbox", status: "completed", title: "Fix issue 12",
      objective: "Fix it", current_step: null, progress_percent: null, created_at: "2026-10-19T08:00:00Z",
      updated_at: "2026-10-19T09:05:00Z", completed_at: null, summary: "Done.", project_id: null, surface,
    },
    approvals: [],
    truncated: false,
    attempts: [
      {
        index: 1, kind: "run", started_at: "2026-10-19T09:00:00Z", ended_at: "2026-10-19T09:05:00Z",
        outcome: "completed", summary: "Finished.", approval_id: null, session_id: "sess_run", turn_id: "turn_run",
        events: [],
      },
    ],
  };
}

const OUTCOME = {
  turn_id: "turn_run", project_id: null, outcome: "completed_unverified", writes: 1, unapplied_writes: 0,
  pending_writes: 0, checks: [], reason: "Files changed. No checks are declared for this project, so nothing verified the change.",
  readback: [], target_drift: [], target: null, review: null,
};

describe("TaskHistory", () => {
  it("shows a Build task attempt's outcome", async () => {
    stubFetch({ "GET /api/sessions/sess_run/turns/turn_run/outcome": OUTCOME });
    render(TaskHistory, { detail: detail("build") as never, onclose: () => {}, onrefresh: () => {} });
    expect(await screen.findByTestId("build-outcome")).toHaveAttribute("data-outcome", "completed_unverified");
  });

  it("does not ask for an outcome on a Chat task", async () => {
    const fetch = stubFetch({ "GET /api/sessions/sess_run/turns/turn_run/outcome": OUTCOME });
    render(TaskHistory, { detail: detail("chat") as never, onclose: () => {}, onrefresh: () => {} });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.queryByTestId("build-outcome")).toBeNull();
    expect(fetch.mock.calls.some(([url]) => String(url).includes("/outcome"))).toBe(false);
  });
});
