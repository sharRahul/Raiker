/**
 * QUI-F06 / QUI-F18 — a task form filled in, never a task created.
 *
 * Two ways in. **Templates** (Work › Tasks): *Morning brief*, *Weekly inbox
 * tidy* and *Watch this page* fill the instruction and the schedule. **Save as
 * routine** (Chat, after a turn went well): the request that worked becomes the
 * instruction of a repeating task. Either way the owner reads it, changes it
 * and presses Create: nothing is saved or scheduled without that sign-off, and
 * the task runs under the same approvals as any other work.
 */
import type { TaskTiming } from "./taskComposer";

export interface TaskDraft {
  title: string;
  objective: string;
  timing: TaskTiming;
  /** A cadence id from `AGENT_CADENCES`, for a repeating draft. */
  every: string;
  /** Local wall-clock time of the first run, `HH:MM`, for a repeating draft. */
  at: string;
  /** For a weekly draft: the weekday of the first run, 0 = Sunday. */
  weekday?: number;
}

export interface ScheduleTemplate extends TaskDraft {
  id: string;
  label: string;
  /** One line under the label: what it does and what it never does. */
  detail: string;
}

export const SCHEDULE_TEMPLATES: readonly ScheduleTemplate[] = [
  {
    id: "morning-brief",
    label: "Morning brief",
    detail: "Every morning: today's calendar, what is waiting on you, and what is due.",
    title: "Morning brief",
    objective:
      "Give me a short brief for today: what is on my calendar, anything in Raiker waiting on my " +
      "decision, and the tasks due today. Keep it to one screen and send nothing on my behalf.",
    timing: "repeating",
    every: "daily",
    at: "08:00",
  },
  {
    id: "weekly-inbox-tidy",
    label: "Weekly inbox tidy",
    detail: "Every Monday: what needs a reply and what could be archived. Nothing is sent or archived.",
    title: "Weekly inbox tidy",
    objective:
      "Look through my inbox from the last week. List the messages that need a reply from me, " +
      "grouped by who they are from, and suggest which ones could be archived. Do not send, " +
      "archive or delete anything.",
    timing: "repeating",
    every: "weekly",
    at: "09:00",
    weekday: 1,
  },
  {
    id: "watch-page",
    label: "Watch this page",
    detail: "Every day: what changed on a page since the last check. Add the address.",
    title: "Watch a page",
    objective: "Check https:// and tell me what changed since the last check. If nothing changed, say so in one line.",
    timing: "repeating",
    every: "daily",
    at: "09:00",
  },
];

let pending: TaskDraft | null = null;

/** Ask the next Tasks mount to open with this draft in its form. */
export function requestTaskDraft(draft: TaskDraft): void {
  pending = draft;
}

/** Consume the draft, if there is one. Reading it clears it. */
export function takeTaskDraft(): TaskDraft | null {
  const draft = pending;
  pending = null;
  return draft;
}

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

/**
 * The first run as a `datetime-local` value: the next time the clock reads
 * `at` (on `weekday`, when given), from `now`. Never in the past.
 */
export function firstRunValue(draft: Pick<TaskDraft, "at" | "weekday">, now: Date = new Date()): string {
  const [hours, minutes] = draft.at.split(":").map(Number);
  const next = new Date(now);
  next.setHours(hours, minutes, 0, 0);
  if (draft.weekday !== undefined) {
    const ahead = (draft.weekday - next.getDay() + 7) % 7;
    next.setDate(next.getDate() + ahead);
  }
  if (next.getTime() <= now.getTime()) next.setDate(next.getDate() + (draft.weekday !== undefined ? 7 : 1));
  return `${next.getFullYear()}-${pad(next.getMonth() + 1)}-${pad(next.getDate())}T${pad(next.getHours())}:${pad(next.getMinutes())}`;
}

/**
 * QUI-F18 — the draft *Save as routine* opens: the request that worked, as the
 * instruction of a daily task, with its title taken from the conversation.
 */
export function routineFromTurn(prompt: string, conversationTitle: string, steps: readonly string[] = []): TaskDraft {
  // The steps are what the turn's own record says it did, so the owner reads
  // what the routine will repeat, and which steps will ask them first.
  const said = steps.length > 0 ? `\n\nLast time this took these steps: ${steps.join("; ")}.` : "";
  const objective = `${prompt.trim()}${said}`;
  const title = conversationTitle.trim() || prompt.trim().split(/\s+/).slice(0, 8).join(" ");
  return { title: title.slice(0, 240), objective, timing: "repeating", every: "daily", at: "09:00" };
}

/** QUI-F18 — a turn's recorded calls as the steps a routine would repeat. */
export function routineSteps(rows: readonly { label: string; action: string; state: string; toolName: string }[]): string[] {
  return rows
    .filter((row) => row.state === "success" && row.toolName !== "update_plan" && row.toolName !== "tool_search")
    .map((row) => (row.action ? `${row.label} (${row.action})` : row.label));
}
