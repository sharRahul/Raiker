import { afterEach, describe, expect, it, vi } from "vitest";
import { resumeRun, startRunNow, stopRun } from "./taskLifecycle";
import { stubFetch } from "./test-helpers";
import type { TaskView } from "./apiTypes";

afterEach(() => vi.unstubAllGlobals());

const TASK = {
  task_id: "task_1",
  session_id: "sess_1",
  title: "Reindex the code map",
  objective: "Walk src/",
  status: "running",
  recurrence: null,
  scheduled_at: null,
  created_at: "2026-09-14T00:00:00Z",
  updated_at: "2026-09-14T00:00:00Z",
  current_step: null,
  progress_percent: null,
} as unknown as TaskView;

/*
 * REM-TASK-02 — Home, Tasks and Build each carried their own copy of "stop this
 * task". They sent the same request and said three different things about it,
 * and two of the three discarded the runtime's reason on failure. Worse, all
 * three reported two outcomes for three genuinely different situations.
 *
 * The three are asserted here rather than on any one surface, because the whole
 * point is that no surface owns this meaning.
 */
describe("stopRun", () => {
  it("says the stop was requested, not that the run stopped", async () => {
    // A cycle already in flight finishes its current step: that is the
    // safe-boundary contract, and a notice reading "Stopped" would be a claim
    // the runtime never made.
    stubFetch({
      "POST /api/interrupts": {
        applied: [{ task_id: "task_1", result: "cancelled" }],
        safe_boundary: true,
        turn_control: null,
      },
    });

    const outcome = await stopRun(TASK, "stopped from the Workbench board");

    expect(outcome.ok).toBe(true);
    expect(outcome.settlement).toBe("requested");
    expect(outcome.notice).toMatch(/Asked .* to stop at its next safe boundary/);
  });

  it("does not claim a stop the runtime did not apply to this task", async () => {
    // The call succeeded and this task is not in `applied` — usually because the
    // run had already settled. Saying "asked it to stop" would describe an act
    // that did not occur.
    stubFetch({
      "POST /api/interrupts": { applied: [], safe_boundary: true, turn_control: null },
    });

    const outcome = await stopRun(TASK, "stopped from the Workbench board");

    expect(outcome.ok).toBe(false);
    expect(outcome.settlement).toBe("outcome_unknown");
    expect(outcome.notice).toMatch(/did not apply it/i);
  });

  it("reports a refusal as settled, with the reason the runtime gave", async () => {
    stubFetch({
      "POST /api/interrupts": {
        __status: 403,
        detail: { ok: false, reason_code: "human_principal_required" },
      },
    });

    const outcome = await stopRun(TASK, "stopped from the Workbench board");

    expect(outcome.settlement).toBe("completed");
    expect(outcome.reasonCode).toBe("human_principal_required");
    // The reason reaches the owner. Two of the three copies threw it away.
    expect(outcome.notice).toMatch(/human_principal_required/);
    expect(outcome.notice).toMatch(/Nothing changed/);
  });

  it("does not claim nothing happened when nothing answered", async () => {
    // The distinction this controller exists for. A request that lost its
    // response may well have been applied, and "Could not request the stop" —
    // which is what two surfaces said here — is a claim nobody is in a position
    // to make. An owner who believes it presses Stop again, or assumes work is
    // still running when it is not.
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))),
    );

    const outcome = await stopRun(TASK, "stopped from the Workbench board");

    expect(outcome.ok).toBe(false);
    expect(outcome.settlement).toBe("outcome_unknown");
    expect(outcome.notice).toMatch(/may or may not have been applied/i);
    expect(outcome.notice).not.toMatch(/nothing changed/i);
  });
});

describe("resumeRun", () => {
  it("continues a parked run", async () => {
    stubFetch({ "POST /api/tasks/task_1/resume": { ok: true, reason_code: null } });

    const outcome = await resumeRun(TASK);

    expect(outcome.ok).toBe(true);
    expect(outcome.notice).toMatch(/Continuing/);
  });

  it("explains the one refusal an owner can act on", async () => {
    stubFetch({
      "POST /api/tasks/task_1/resume": { ok: false, reason_code: "no_resolved_approval" },
    });

    const outcome = await resumeRun(TASK);

    expect(outcome.settlement).toBe("completed");
    expect(outcome.notice).toMatch(/nothing to continue/i);
  });
});

describe("startRunNow", () => {
  it("reports a start as requested rather than as finished", async () => {
    stubFetch({ "POST /api/tasks/task_1/run": { ok: true } });

    const outcome = await startRunNow(TASK);

    expect(outcome.settlement).toBe("requested");
    expect(outcome.notice).toMatch(/Starting/);
  });
});
