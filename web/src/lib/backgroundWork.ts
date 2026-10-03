/**
 * UX-CHAT-04 — what Chat's background-work toggle says before it is opened.
 *
 * The toggle was an icon with no label and no count, so the one place Chat
 * shows work running on its own looked like a layout control, and a run that
 * had failed in the background was invisible until someone happened to open
 * the rail. This summarises the same `/api/tasks` list the rail draws — the
 * same filter, the same active states — so the badge and the rail cannot
 * disagree about what is there.
 */
import { isActiveTask } from "./statusMaps";
import type { TaskView } from "./apiTypes";

export interface BackgroundSummary {
  /** Unfinished work, as the rail's "running" list counts it. */
  active: number;
  /** Of those, the ones waiting on the owner. */
  waiting: number;
  /** Work that failed within the window. */
  failed: number;
}

/** A failure stays worth flagging for a day; older ones are history. */
export const FAILED_WINDOW_MS = 24 * 60 * 60 * 1000;

export function backgroundSummary(
  tasks: readonly Pick<TaskView, "status" | "updated_at" | "completed_at">[],
  now: Date = new Date(),
): BackgroundSummary {
  let active = 0;
  let waiting = 0;
  let failed = 0;
  for (const task of tasks) {
    if (isActiveTask(task.status)) {
      active += 1;
      if (task.status === "waiting_for_approval" || task.status === "paused") waiting += 1;
      continue;
    }
    if (task.status !== "failed") continue;
    const at = Date.parse(task.completed_at ?? task.updated_at);
    if (Number.isFinite(at) && now.getTime() - at <= FAILED_WINDOW_MS) failed += 1;
  }
  return { active, waiting, failed };
}

/** The toggle's accessible name: the label plus every count that is not zero. */
export function backgroundLabel(summary: BackgroundSummary | null): string {
  if (summary === null) return "Background work";
  const parts: string[] = [];
  if (summary.active) parts.push(`${summary.active} running`);
  if (summary.waiting) parts.push(`${summary.waiting} waiting for you`);
  if (summary.failed) parts.push(`${summary.failed} failed today`);
  return parts.length ? `Background work: ${parts.join(", ")}` : "Background work: nothing running";
}
