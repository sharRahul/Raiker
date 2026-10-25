/**
 * QUI-F04 — the live work line: one line in the top bar while something runs.
 *
 * Two sources, both true as they are read. Background work is the task list
 * every surface counts (`isActiveTask` over `GET /api/tasks`), and each task
 * says its own `current_step` when it has one. A Chat or Build turn being
 * written in this window is not a task, so the surface running it reports it
 * here while it streams and withdraws it when it ends; the step is the same
 * status line the turn shows under its composer (QUI-C03).
 *
 * Nothing here invents progress: a task that reports no step says its state
 * ("running", "waiting for you"), never a percentage or a guess.
 */
import { isActiveTask } from "./statusMaps";
import type { TaskView } from "./apiTypes";

export interface LiveWorkItem {
  /** `task:<id>` or `turn:<surface>`, so a menu can key its rows. */
  id: string;
  /** What is being worked on: a task's title or a conversation's. */
  label: string;
  /** The real current step, in the owner's words. */
  step: string;
  /** Where clicking the row goes: the task, or the conversation. */
  href: string;
  /** True when it cannot move until the owner acts. */
  waiting: boolean;
}

/** Turns streaming in this window, keyed by the surface that runs them. */
export const foregroundWork = $state<Record<string, LiveWorkItem>>({});

/**
 * Chat and Build call this while a turn streams (with its current step) and
 * with `null` when it ends, so the line never outlives the work.
 */
export function reportForegroundWork(surface: string, item: Omit<LiveWorkItem, "id"> | null): void {
  if (item === null) {
    delete foregroundWork[surface];
    return;
  }
  foregroundWork[surface] = { ...item, id: `turn:${surface}` };
}

/** A task's state when it has not reported a step of its own. */
function taskStateWords(status: string): string {
  if (status === "waiting_for_approval") return "waiting for you";
  if (status === "paused") return "paused";
  if (status === "queued") return "queued";
  if (status === "waiting_for_children") return "waiting for work it started";
  if (status === "continuing") return "continuing after your decision";
  return "running";
}

/** The rows the line and its menu show, turns in this window first. */
export function liveWorkItems(
  tasks: readonly (Pick<TaskView, "task_id" | "title" | "status" | "current_step"> &
    Partial<Pick<TaskView, "scheduled_at">>)[],
  foreground: Readonly<Record<string, LiveWorkItem>>,
  now: Date = new Date(),
): LiveWorkItem[] {
  const rows: LiveWorkItem[] = Object.values(foreground);
  for (const task of tasks) {
    if (!isActiveTask(task.status)) continue;
    // A routine queued for a later time is waiting for its slot, not running:
    // counting it would make "2 tasks running" untrue (found live, TOOL round).
    if (task.status === "queued" && task.scheduled_at && Date.parse(task.scheduled_at) > now.getTime()) continue;
    const waiting = task.status === "waiting_for_approval" || task.status === "paused";
    const reported = (task.current_step ?? "").trim();
    // A waiting task says so even when it last reported a step: what the
    // owner needs to know is that it is their move.
    const step = waiting ? taskStateWords(task.status) : reported || taskStateWords(task.status);
    rows.push({
      id: `task:${task.task_id}`,
      label: task.title.trim() || "Untitled task",
      step,
      href: `#/tasks?task=${encodeURIComponent(task.task_id)}`,
      waiting,
    });
  }
  return rows;
}

/** The line itself: the one item's step, or how many things are running. */
export function liveWorkLine(items: readonly LiveWorkItem[]): string {
  if (items.length === 0) return "";
  if (items.length === 1) return `${items[0].label} · ${items[0].step}`;
  const allTasks = items.every((item) => item.id.startsWith("task:"));
  const waiting = items.filter((item) => item.waiting).length;
  const head = `${items.length} ${allTasks ? "tasks" : "things"} running`;
  return waiting > 0 ? `${head} · ${waiting} waiting for you` : head;
}
