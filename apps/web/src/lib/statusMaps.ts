// Map backend status strings (tasks, approvals, turns, agent responses) to badge
// variants. Unknown statuses fall back to "idle" and the caller shows the raw
// status text as the badge label, so nothing is ever hidden.

import type { BadgeVariant } from "./types";

export function taskBadge(status: string): BadgeVariant {
  switch (status) {
    case "completed":
      return "done";
    case "queued":
    case "running":
    case "paused":
      return "active";
    case "cancelled":
    case "failed":
      return "stopped";
    default:
      return "idle";
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
    case "denied":
    case "failed":
      return "stopped";
    default:
      return "idle";
  }
}
