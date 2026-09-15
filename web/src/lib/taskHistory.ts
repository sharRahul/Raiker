/**
 * How a task's attempts read: the words, the badges, and the address.
 *
 * BUG-299 / UX-TASK-04. A task had a status and a current step, and no history.
 * [FIXED-533] gave one run one Stop, Resume and Run-now meaning across Home,
 * Tasks and Build, and with it a third, honest settlement — `outcome_unknown`,
 * whose remedy is *"refresh to see the run's current state"*. There was nowhere
 * to refresh to. [FIXED-531] deduplicated Home's rows and its acceptance asked
 * each to "link to the canonical Tasks detail", which did not exist either.
 *
 * `taskDetailHref` is that address, and it is one function rather than a
 * template literal in four views, because a link that means "the canonical
 * detail" cannot be canonical if each surface spells it differently.
 *
 * Nothing here decides anything. The server derives the attempts from the
 * governed events the task's own lifecycle wrote; this only says how they read.
 */
import type { TaskAttemptView, TaskView } from "./apiTypes";
import type { BadgeVariant } from "./types";

/** The canonical address of one task's attempt history. */
export function taskDetailHref(taskId: string): string {
  return `#/tasks?task=${encodeURIComponent(taskId)}`;
}

/**
 * The badge one attempt's outcome carries.
 *
 * `in_progress` is deliberately "active" rather than anything reassuring: a run
 * whose settlement never arrived has not succeeded, and this is exactly the row
 * an owner sent here by `outcome_unknown` is looking for.
 */
export function attemptBadge(outcome: string): BadgeVariant {
  switch (outcome) {
    case "completed":
      return "done";
    case "in_progress":
      return "active";
    case "waiting_for_approval":
      return "needs-approval";
    case "waiting_for_children":
      return "active";
    case "failed":
    case "cancelled":
      return "stopped";
    default:
      return "idle";
  }
}

/** The same outcome in English. An unknown one is shown verbatim, never hidden. */
export function attemptOutcomeLabel(outcome: string): string {
  switch (outcome) {
    case "completed":
      return "completed";
    case "failed":
      return "did not complete";
    case "waiting_for_approval":
      return "waiting for approval";
    case "waiting_for_children":
      return "waiting on delegated work";
    case "cancelled":
      return "stopped";
    case "in_progress":
      return "still running";
    case "recorded":
      return "recorded";
    default:
      return outcome;
  }
}

/**
 * What to call one attempt.
 *
 * A continuation is numbered alongside the runs because it *is* another pass at
 * the same work, and named for what released it, because "attempt 2" alone
 * would suggest the task had been run twice when what happened is that one
 * parked run was let through.
 */
export function attemptTitle(attempt: TaskAttemptView): string {
  if (attempt.kind === "continuation") return `Attempt ${attempt.index} · after your decision`;
  if (attempt.kind === "run") return `Attempt ${attempt.index}`;
  return "Recorded";
}

/**
 * Where one recorded transition can be opened, or null when there is nothing
 * to open.
 *
 * A link to an empty transcript is a dead end, so this offers the task's own
 * conversation only once that conversation holds something — the same rule the
 * task card's Thread link already applies.
 */
export function eventHref(task: TaskView, attempt: TaskAttemptView): string | null {
  if (attempt.approval_id) return `#/approvals?session=${encodeURIComponent(task.session_id)}`;
  // Only a run produced a conversation. Offering "Open the conversation" on the
  // filing record would send an owner to a transcript that has nothing to do
  // with the row they pressed — the task was merely created there.
  if (attempt.kind === "record") return null;
  if (task.thread_session_id && (task.thread_turns ?? 0) > 0) {
    return `#/new-chat?session=${encodeURIComponent(task.thread_session_id)}`;
  }
  return null;
}

/**
 * The attempts a person reads first: newest at the top.
 *
 * The server answers oldest-first because that is the order a history is
 * *derived* in; it is not the order it is read in. The most recent attempt is
 * the one an owner opened this page for.
 */
export function newestFirst(attempts: TaskAttemptView[]): TaskAttemptView[] {
  return [...attempts].reverse();
}

/**
 * One sentence summarising the whole history, for the panel's lead.
 *
 * It counts runs and continuations — not the `record` segments, which are the
 * filing and the owner's own acts rather than attempts at the work.
 */
export function historySummary(attempts: TaskAttemptView[]): string {
  const runs = attempts.filter((attempt) => attempt.kind !== "record");
  if (runs.length === 0) return "This task has not run yet.";
  const failed = runs.filter((attempt) => attempt.outcome === "failed").length;
  const waiting = runs.filter((attempt) => attempt.outcome === "waiting_for_approval").length;
  const parts = [`${runs.length} ${runs.length === 1 ? "attempt" : "attempts"}`];
  if (failed > 0) parts.push(`${failed} did not complete`);
  if (waiting > 0) parts.push(`${waiting} waited on a decision`);
  return `${parts.join(" · ")}.`;
}
