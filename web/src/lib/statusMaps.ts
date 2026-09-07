// Map backend status strings (tasks, approvals, turns, agent responses) to badge
// variants. Unknown statuses fall back to "idle" and the caller shows the raw
// status text as the badge label, so nothing is ever hidden.

import type { BadgeVariant } from "./types";

// Unfinished work. `waiting_for_approval` belongs here and is the reason this is
// shared rather than repeated: a run parked on a decision has not finished and
// has not failed, so every surface that counts, lists, or stops active work must
// agree that it is still active (BUG-09). Mirrors `_ACTIVE_TASK_STATES` in
// `raiker/api/routes_prompts.py`, which decides what "stop everything" reaches.
export const ACTIVE_TASK_STATES = [
  "queued",
  "running",
  // A granted approval being replayed into a parked scheduled run (BUG-25).
  // Unfinished like the rest: it is the state between the decision and the
  // outcome, and it has to be stoppable and countable while it lasts.
  "continuing",
  "paused",
  "waiting_for_approval",
  // BUG-220 — a task whose own run finished while work it delegated has not.
  // Unfinished, and counted as such: reporting it as done is the false
  // completion this state exists to prevent.
  "waiting_for_children",
];

export function isActiveTask(status: string): boolean {
  return ACTIVE_TASK_STATES.includes(status);
}

export function taskBadge(status: string): BadgeVariant {
  switch (status) {
    case "completed":
      return "done";
    case "queued":
    case "running":
    case "continuing":
    case "paused":
      return "active";
    case "waiting_for_approval":
      return "needs-approval";
    case "waiting_for_children":
      return "active";
    case "cancelled":
    case "failed":
      return "stopped";
    default:
      return "idle";
  }
}

// Backend task statuses are snake_case identifiers; a badge should read as
// English. An unknown status is shown verbatim rather than hidden or guessed at.
export function taskStatusLabel(status: string): string {
  switch (status) {
    case "waiting_for_approval":
      return "waiting for approval";
    case "waiting_for_children":
      return "waiting on delegated work";
    case "continuing":
      return "continuing after approval";
    case "waiting_for_user_answer":
      return "waiting for your answer";
    case "cancelling":
      return "stopping";
    default:
      return status;
  }
}

export function approvalBadge(status: string): BadgeVariant {
  switch (status) {
    case "pending":
      return "needs-approval";
    case "approved":
    case "executed":
      return "done";
    case "denied":
    case "expired":
      return "stopped";
    case "execution_failed":
      return "blocked";
    default:
      return "idle";
  }
}

export function responseBadge(status: string): BadgeVariant {
  switch (status) {
    case "completed":
      return "done";
    case "queued":
    case "running":
      return "active";
    case "needs_approval":
      return "needs-approval";
    // `stopped` (B17/C13) is a turn the owner ended at a safe boundary. It
    // shares this badge with a denial because both are decisions rather than
    // completions, and it is deliberately not `failed`: the runtime did what it
    // was told.
    case "denied":
    case "failed":
    case "stopped":
      return "stopped";
    default:
      return "idle";
  }
}
