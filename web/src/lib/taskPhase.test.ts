import { describe, expect, it } from "vitest";
import { haltAction, taskActions, taskPhase, TASK_PHASES } from "./taskPhase";

/**
 * UX-TASK-05 — one lifecycle, and what each part of it lets an owner press.
 * These are asserted here rather than on any one surface, because no surface
 * owns this meaning: Tasks, Home and Build all draw from it.
 */
describe("the task lifecycle", () => {
  const now = new Date("2026-10-03T12:00:00Z");
  const row = (status: string, scheduled_at: string | null = null, recurrence: string | null = null) => ({
    status,
    scheduled_at,
    recurrence,
  });

  it("tells not-started, scheduled and queued work apart", () => {
    expect(taskPhase(row("queued"), now)).toBe("not_started");
    expect(taskPhase(row("queued", "2026-10-04T09:00:00Z"), now)).toBe("scheduled");
    expect(taskPhase(row("queued", "2026-10-03T11:59:00Z"), now)).toBe("queued");
  });

  it("puts every runtime status in a phase, and an unknown one in waiting", () => {
    for (const status of ["running", "continuing", "cancelling"]) expect(taskPhase(row(status), now)).toBe("running");
    for (const status of ["waiting_for_approval", "waiting_for_user_answer", "waiting_for_children", "paused"]) {
      expect(taskPhase(row(status), now)).toBe("waiting");
    }
    expect(taskPhase(row("cancelled"), now)).toBe("stopped");
    expect(taskPhase(row("something_new"), now)).toBe("waiting");
  });

  it("prefers the phase the server published", () => {
    expect(taskPhase({ ...row("queued"), phase: "scheduled" }, now)).toBe("scheduled");
    expect(taskPhase({ ...row("queued"), phase: "nonsense" }, now)).toBe("not_started");
    expect(TASK_PHASES).toContain("not_started");
  });

  it("offers Run now only before the work has started", () => {
    expect(taskActions(row("queued"), now)).toEqual(["run_now", "cancel"]);
    expect(taskActions(row("queued", "2026-10-04T09:00:00Z"), now)).toEqual(["cancel"]);
    expect(taskActions(row("running"), now)).toEqual(["stop"]);
  });

  it("says Cancel before a run and Stop after, and nothing while a stop is under way", () => {
    expect(haltAction(row("queued", "2026-10-04T09:00:00Z"), now)).toBe("cancel");
    expect(haltAction(row("running"), now)).toBe("stop");
    expect(haltAction(row("waiting_for_children"), now)).toBe("stop");
    expect(haltAction(row("cancelling"), now)).toBeNull();
    expect(haltAction(row("completed"), now)).toBeNull();
  });

  it("offers Continue only where a decision can release the run", () => {
    expect(taskActions(row("waiting_for_approval"), now)).toEqual(["continue", "stop"]);
    expect(taskActions(row("paused"), now)).toEqual(["continue", "stop"]);
    expect(taskActions(row("waiting_for_children"), now)).toEqual(["stop"]);
  });

  it("runs finished one-off work again as new work, and never a routine", () => {
    expect(taskActions(row("failed"), now)).toEqual(["run_again"]);
    expect(taskActions(row("cancelled"), now)).toEqual(["run_again"]);
    expect(taskActions(row("completed", null, "background"), now)).toEqual(["run_again"]);
    expect(taskActions(row("completed", null, "daily"), now)).toEqual([]);
  });
});
