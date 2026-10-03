/**
 * UX-TASK-05 — one lifecycle, and the actions each part of it offers.
 *
 * The runtime has twelve task statuses and every surface used to decide for
 * itself what an owner could press for which of them. Home said **Cancel** for a
 * scheduled run and **Stop** for the same request everywhere else; every active
 * row offered **Stop**, including one already stopping; nothing said whether a
 * finished task could be run again, or what doing so would repeat.
 *
 * The phases are the ones the server publishes on every task
 * (`raiker/tasks/lifecycle.py`):
 *
 *   not started → scheduled / queued → running → waiting → completed / failed / stopped
 *
 * and this module is the one place that says what each phase allows. Every
 * surface asks it, so one task offers the same controls wherever it is shown.
 *
 * The rules it encodes:
 *
 * * **Run now** is offered only on work that has not started. A scheduled run
 *   keeps its slot; running it early would be a second cycle, not this one.
 * * **Cancel** is the word before anything has run, **Stop** once it has. Both
 *   are the same governed request; what differs is what it interrupts.
 * * **Continue** is offered only where a run is parked on a decision the owner
 *   already made — the recovery for a continuation that could not proceed.
 * * **Run again** is offered on finished one-off work, and it files *new* work
 *   with the same instruction. A finished run is never replayed in place, so
 *   nothing it already did — a message sent, a file written — is repeated by
 *   pressing a button. A routine is never "run again": it re-arms itself.
 */
import type { BadgeVariant } from "./types";
import type { TaskView } from "./apiTypes";

export const TASK_PHASES = [
  "not_started",
  "scheduled",
  "queued",
  "running",
  "waiting",
  "completed",
  "failed",
  "stopped",
] as const;

export type TaskPhase = (typeof TASK_PHASES)[number];

export type TaskAction = "run_now" | "cancel" | "stop" | "continue" | "run_again";

const STATUS_PHASES: Record<string, TaskPhase> = {
  queued: "queued",
  running: "running",
  continuing: "running",
  cancelling: "running",
  waiting_for_approval: "waiting",
  waiting_for_user_answer: "waiting",
  waiting_for_children: "waiting",
  paused: "waiting",
  completed: "completed",
  failed: "failed",
  cancelled: "stopped",
};

/**
 * The phase a task is in. The server's own answer wins; the derivation is for
 * a row from a server that predates it, and reads an unknown status as
 * waiting — never as done.
 */
export function taskPhase(task: Pick<TaskView, "status" | "scheduled_at"> & { phase?: string }, now = new Date()): TaskPhase {
  if (task.phase && (TASK_PHASES as readonly string[]).includes(task.phase)) {
    return task.phase as TaskPhase;
  }
  const phase = STATUS_PHASES[task.status] ?? "waiting";
  if (phase !== "queued") return phase;
  if (!task.scheduled_at) return "not_started";
  const due = new Date(task.scheduled_at).getTime();
  return Number.isNaN(due) || due <= now.getTime() ? "queued" : "scheduled";
}

/** What an owner may do with this task, in the order the controls are drawn. */
export function taskActions(
  task: Pick<TaskView, "status" | "scheduled_at" | "recurrence"> & { phase?: string },
  now = new Date(),
): TaskAction[] {
  const phase = taskPhase(task, now);
  switch (phase) {
    case "not_started":
      return ["run_now", "cancel"];
    case "scheduled":
    case "queued":
      return ["cancel"];
    case "running":
      // Already asked to stop: a second Stop is not a second request anyone needs.
      return task.status === "cancelling" ? [] : ["stop"];
    case "waiting":
      return task.status === "waiting_for_approval" || task.status === "paused"
        ? ["continue", "stop"]
        : ["stop"];
    case "completed":
    case "failed":
    case "stopped":
      return task.recurrence && task.recurrence !== "background" ? [] : ["run_again"];
  }
}

/** The button's own words. */
export function taskActionLabel(action: TaskAction): string {
  switch (action) {
    case "run_now":
      return "Run now";
    case "cancel":
      return "Cancel";
    case "stop":
      return "Stop";
    case "continue":
      return "Continue now";
    case "run_again":
      return "Run again";
  }
}

/** The phase as the owner reads it on a badge. */
export function taskPhaseLabel(phase: TaskPhase): string {
  switch (phase) {
    case "not_started":
      return "not started";
    case "scheduled":
      return "scheduled";
    case "queued":
      return "queued";
    case "running":
      return "running";
    case "waiting":
      return "waiting";
    case "completed":
      return "completed";
    case "failed":
      return "failed";
    case "stopped":
      return "stopped";
  }
}

export function taskPhaseBadge(phase: TaskPhase): BadgeVariant {
  switch (phase) {
    case "completed":
      return "done";
    case "failed":
    case "stopped":
      return "stopped";
    case "waiting":
      return "needs-approval";
    case "not_started":
    case "scheduled":
      return "idle";
    default:
      return "active";
  }
}

/**
 * The one halting control a row offers — **Cancel** before the work has run,
 * **Stop** once it has, nothing while a stop is already under way. Home and
 * Build's side panel draw only this control, and draw it from here, so the same
 * task is never "Cancel" on one surface and "Stop" on another.
 */
export function haltAction(
  task: Pick<TaskView, "status" | "scheduled_at" | "recurrence"> & { phase?: string },
  now = new Date(),
): "stop" | "cancel" | null {
  const actions = taskActions(task, now);
  if (actions.includes("cancel")) return "cancel";
  if (actions.includes("stop")) return "stop";
  return null;
}
