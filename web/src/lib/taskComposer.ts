/**
 * COMPOSER-10 — planning work reads as an instruction, not as a form.
 *
 * Task creation was a card of eight controls, all of them present all of the
 * time: Title, Instructions, a when-row, a how-row, Parent work, Priority,
 * Repeat, Start time, a model picker and two badges. Asking Raiker to do
 * something in Chat takes one field; asking it to do the same thing *later*
 * took ten, which teaches an owner that scheduling is a different and more
 * administrative kind of act than asking. It is not — a scheduled cycle is one
 * governed turn, the same as a typed prompt.
 *
 * So this module holds the two derivations that let one instruction field
 * replace the pair of fields at the top, and the timing details move behind a
 * control that is only opened when the owner wants them.
 */

/** The four shapes of work, in the order the chips offer them. */
export const TASK_CADENCES = [
  { id: "now", label: "Task", action: "Create task" },
  { id: "once", label: "Once", action: "Schedule task" },
  { id: "routine", label: "Routine", action: "Create routine" },
  { id: "background", label: "Background", action: "Start background agent" },
] as const;

export type TaskCadence = (typeof TASK_CADENCES)[number]["id"];

/** Longest derived title. The API caps titles at 240; this is a readable line. */
export const MAX_DERIVED_TITLE = 120;

/**
 * A title for the instruction the owner wrote.
 *
 * The API needs a title and an objective; the composer asks for one thing. So
 * the title is *derived* — the instruction's first sentence, trimmed to a
 * readable length — and the owner can override it in the details when the
 * derived one is not what they would have called it.
 *
 * Deriving rather than duplicating is the point. Two required fields at the top
 * of a form is two chances to be asked the same question twice, and the second
 * answer is nearly always the first one shortened by hand.
 */
export function deriveTitle(instruction: string): string {
  const text = instruction.replace(/\s+/g, " ").trim();
  if (text === "") return "";
  // The first sentence, where there is one: a full stop is the author's own
  // mark for "this much is the gist".
  const stop = text.search(/[.!?](\s|$)/);
  const first = stop > 0 ? text.slice(0, stop) : text;
  if (first.length <= MAX_DERIVED_TITLE) return first;
  // Cut on a word boundary rather than mid-word, and say it was cut.
  const clipped = first.slice(0, MAX_DERIVED_TITLE);
  const lastSpace = clipped.lastIndexOf(" ");
  return `${(lastSpace > 40 ? clipped.slice(0, lastSpace) : clipped).trimEnd()}…`;
}

/** The primary action's label for this cadence. */
export function primaryAction(cadence: TaskCadence): string {
  return TASK_CADENCES.find((entry) => entry.id === cadence)?.action ?? "Create task";
}

/** Whether this shape of work needs a start time before it can be created. */
export function wantsStartTime(cadence: TaskCadence): boolean {
  return cadence === "once" || cadence === "routine";
}

/**
 * The one-line summary of the timing the owner has chosen, for the collapsed
 * control — so the details being hidden never means the choice is invisible.
 */
export function scheduleSummary(options: {
  cadence: TaskCadence;
  every: string;
  everyLabel: string;
  startAt: string;
}): string {
  switch (options.cadence) {
    case "now":
      return "Runs now";
    case "background":
      return "Runs until its work is done";
    case "once":
      return options.startAt ? `Once, at ${readableTime(options.startAt)}` : "Once — pick a time";
    case "routine":
      return options.startAt
        ? `${options.everyLabel}, from ${readableTime(options.startAt)}`
        : `${options.everyLabel} — pick a first run`;
  }
}

function readableTime(value: string): string {
  const at = new Date(value);
  if (Number.isNaN(at.getTime())) return value;
  return at.toLocaleString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * REM-TASK-01 — when work runs, and how it runs, asked as two questions.
 *
 * The composer offered one row of four chips — `Task`, `Once`, `Routine`,
 * `Background` — which is two questions wearing one control. Two of those
 * chips answer *when* ("once, at a time I pick", "repeating") and two answer
 * *how* ("one pass", "keep working until it is done"). An owner who wanted a
 * background agent had to know that the answer was filed under the timing row,
 * and an owner reading the row back could not tell which of the two properties
 * a chip had set.
 *
 * The four shapes underneath are unchanged — this is the same `TaskCadence` the
 * runtime already accepts, asked for in the order a person thinks about it.
 * Combinations the runtime does not have are not offered: a background agent
 * starts now, so the run-mode question only appears under "Now".
 */
export const TASK_TIMINGS = [
  { id: "now", label: "Now" },
  { id: "at", label: "At a time" },
  { id: "repeating", label: "Repeating" },
] as const;

export type TaskTiming = (typeof TASK_TIMINGS)[number]["id"];

export const TASK_RUN_MODES = [
  { id: "single", label: "One pass" },
  { id: "background", label: "Until it is done" },
] as const;

export type TaskRunMode = (typeof TASK_RUN_MODES)[number]["id"];

export function timingFor(cadence: TaskCadence): TaskTiming {
  if (cadence === "once") return "at";
  if (cadence === "routine") return "repeating";
  return "now";
}

export function runModeFor(cadence: TaskCadence): TaskRunMode {
  return cadence === "background" ? "background" : "single";
}

/** The shape the runtime is asked for, from the two questions the owner answered. */
export function cadenceFor(timing: TaskTiming, runMode: TaskRunMode): TaskCadence {
  if (timing === "at") return "once";
  if (timing === "repeating") return "routine";
  return runMode === "background" ? "background" : "now";
}

/**
 * The gap between one governed cycle and the next, mirroring
 * `RECURRING_INTERVALS` in `raiker/tasks/scheduler.py`.
 *
 * Duplicated deliberately and narrowly: this is a *preview*, and a preview that
 * disagreed with the scheduler would be worse than no preview at all. The test
 * beside it asserts the two lists carry the same names.
 */
export const RECURRENCE_INTERVAL_MS: Record<string, number> = {
  continuous: 20 * 60_000,
  hourly: 60 * 60_000,
  daily: 24 * 60 * 60_000,
  weekly: 7 * 24 * 60 * 60_000,
};

/** The zone the times on this screen are read and written in. */
export function scheduleZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "your local time";
  } catch {
    return "your local time";
  }
}

/**
 * The next runs this schedule would produce, as the scheduler would produce them.
 *
 * Two properties are copied from `next_run_after` rather than invented here,
 * because getting either wrong would make the preview a lie about the product:
 * a recurring schedule is anchored to the slot the owner picked rather than to
 * "now", and every slot that has already passed is skipped rather than owed. A
 * host that was asleep does not wake up running the same cycle six times, and
 * the preview must not imply that it does.
 */
export function nextRuns(options: {
  cadence: TaskCadence;
  every: string;
  startAt: string;
  count?: number;
  now?: Date;
}): Date[] {
  const count = options.count ?? 3;
  const start = new Date(options.startAt);
  if (options.startAt === "" || Number.isNaN(start.getTime())) return [];
  const now = options.now ?? new Date();
  if (options.cadence === "once") return [start];
  if (options.cadence !== "routine") return [];
  const interval = RECURRENCE_INTERVAL_MS[options.every];
  if (!interval) return [start];
  let next = start.getTime();
  // The first slot that has not already passed. A first run in the future is
  // itself that slot; one in the past steps forward until it is.
  while (next <= now.getTime()) next += interval;
  const runs: Date[] = [];
  for (let index = 0; index < count; index += 1) runs.push(new Date(next + interval * index));
  return runs;
}
