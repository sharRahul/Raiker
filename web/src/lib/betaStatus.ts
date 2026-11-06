/** The shared five-state vocabulary required by the beta UX gate. */
export type BetaStatus = "Ready" | "Working" | "Needs you" | "Unavailable" | "Failed";

export function taskBetaStatus(status: string): BetaStatus {
  switch (status) {
    case "queued": case "completed": return "Ready";
    case "running": case "continuing": case "cancelling": return "Working";
    case "paused": case "waiting_for_approval": case "waiting_for_user_answer": case "waiting_for_children": return "Needs you";
    case "failed": case "cancelled": case "stopped": return "Failed";
    default: return "Unavailable";
  }
}

export function modelBetaStatus(state: string | null | undefined): BetaStatus {
  switch (state) {
    case "ready": return "Ready";
    case "checking": return "Working";
    case "authentication_failed": case "quota_exhausted": case "unreachable": return "Failed";
    default: return "Unavailable";
  }
}

export function runtimeBetaStatus(status: string | null | undefined): BetaStatus {
  if (status === "active") return "Ready";
  if (status === "starting" || status === "stopping") return "Working";
  if (status === "suspended" || status === "disabled") return "Needs you";
  if (status === "failed") return "Failed";
  return "Unavailable";
}

/** Retain the measured detail without letting it replace the common status. */
export function withBetaStatus(status: BetaStatus, detail: string | null | undefined): string {
  const clean = detail?.trim();
  return clean && clean.toLowerCase() !== status.toLowerCase() ? `${status} · ${clean}` : status;
}
