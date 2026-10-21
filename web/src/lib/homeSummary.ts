/**
 * QUI-H01 — the words at the top of Home, and the week's finished work.
 *
 * Pure functions, so the rules are tested without rendering the page: the
 * greeting follows the owner's clock, the one fact under it appears only when
 * it is true, and "This week" names finished outcomes rather than counting them.
 */
import type { TaskView } from "./apiTypes";
import type { GoalView } from "./generated/apiContract";

/** "Welcome" on a first day; otherwise a greeting for the time of day. */
export function homeGreeting(name: string, firstDay: boolean, hour: number): string {
  const who = name.trim();
  const greeting = firstDay
    ? "Welcome"
    : hour < 12
      ? "Good morning"
      : hour < 18
        ? "Good afternoon"
        : "Good evening";
  return who === "" ? greeting : `${greeting}, ${who}`;
}

/** The one fact worth a line under the greeting, or nothing. */
export function homeFact(pendingDecisions: number): string | null {
  if (pendingDecisions <= 0) return null;
  return pendingDecisions === 1 ? "1 decision waiting" : `${pendingDecisions} decisions waiting`;
}

export const WEEK_MS = 7 * 24 * 60 * 60 * 1000;

export interface WeekOutcome {
  readonly id: string;
  readonly title: string;
  readonly href: string;
}

/**
 * Work that finished in the last seven days, newest first.
 *
 * Only `completed` counts: a cancelled or failed task is not an outcome, and
 * a partly met goal is still open. Untitled work is left out rather than shown
 * as an empty name.
 */
export function weekOutcomes(
  tasks: readonly Pick<TaskView, "task_id" | "title" | "status" | "completed_at" | "updated_at">[],
  goals: readonly Pick<GoalView, "goal_id" | "title" | "status" | "settled_at" | "updated_at">[],
  now: Date,
  taskHref: (taskId: string) => string,
): WeekOutcome[] {
  const since = now.getTime() - WEEK_MS;
  const within = (iso: string | null | undefined) => {
    const at = Date.parse(iso ?? "");
    return Number.isFinite(at) && at >= since && at <= now.getTime() ? at : null;
  };
  const rows: { at: number; outcome: WeekOutcome }[] = [];
  for (const task of tasks) {
    if (task.status !== "completed" || task.title.trim() === "") continue;
    const at = within(task.completed_at ?? task.updated_at);
    if (at !== null) rows.push({ at, outcome: { id: `task:${task.task_id}`, title: task.title, href: taskHref(task.task_id) } });
  }
  for (const goal of goals) {
    if (goal.status !== "completed" || goal.title.trim() === "") continue;
    const at = within(goal.settled_at ?? goal.updated_at);
    if (at !== null) {
      rows.push({
        at,
        outcome: { id: `goal:${goal.goal_id}`, title: goal.title, href: `#/work?tab=goals&record=${encodeURIComponent(goal.goal_id)}` },
      });
    }
  }
  return rows.sort((a, b) => b.at - a.at).map((row) => row.outcome);
}
