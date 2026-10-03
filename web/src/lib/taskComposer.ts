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

/**
 * UX-TASK-02 — cadences the scheduler steps in local calendar days, keeping the
 * local time of day, mirroring `CALENDAR_STEP_DAYS` in `raiker/tasks/schedule.py`.
 *
 * "Daily at 09:00" is 09:00 where the owner lives on both sides of a clock
 * change, so it is not a fixed number of milliseconds. `weekdays` steps a day at
 * a time and lands only on Monday to Friday. The test beside this and
 * `tests/test_task_schedule_preview_contract.py` hold the two lists together.
 */
export const CALENDAR_STEP_DAYS: Record<string, number> = {
  daily: 1,
  weekly: 7,
  weekdays: 1,
};

/** What a routine does about a slot that passed while Raiker was not running. */
export const MISSED_RUN_POLICIES = [
  {
    id: "run_once",
    label: "Run it once when Raiker is back",
    short: "runs a missed slot once",
  },
  {
    id: "skip",
    label: "Skip it and wait for the next slot",
    short: "skips missed slots",
  },
] as const;

export type MissedRunPolicy = (typeof MISSED_RUN_POLICIES)[number]["id"];

/** The IANA zone this browser reads and writes times in, sent with a schedule. */
export function scheduleZoneName(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

/** The zone the times on this screen are read and written in. */
export function scheduleZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "your local time";
  } catch {
    return "your local time";
  }
}

const MINUTE = 60_000;
const DAY = 24 * 60 * MINUTE;

interface Wall {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
}

/** The wall clock an instant reads as in `zone`, to the minute. */
function wallAt(instant: number, zone: string): Wall {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: zone,
    hourCycle: "h23",
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    minute: "numeric",
  }).formatToParts(new Date(instant));
  const read = (type: string) => Number(parts.find((part) => part.type === type)?.value ?? 0);
  return {
    year: read("year"),
    month: read("month") - 1,
    day: read("day"),
    hour: read("hour") % 24,
    minute: read("minute"),
  };
}

/** How far `zone` is ahead of UTC at an instant, in milliseconds. */
function offsetAt(instant: number, zone: string): number {
  const wall = wallAt(instant, zone);
  const asUtc = Date.UTC(wall.year, wall.month, wall.day, wall.hour, wall.minute);
  return asUtc - Math.floor(instant / MINUTE) * MINUTE;
}

/**
 * A wall-clock time in `zone` as an instant, deciding DST as the server does:
 * a repeated hour resolves to the first of the two, and a time inside the hour
 * the clocks skip uses the offset from before the change.
 */
function instantAt(wall: Wall, zone: string): number {
  const guess = Date.UTC(wall.year, wall.month, wall.day, wall.hour, wall.minute);
  const before = offsetAt(guess - 12 * 60 * MINUTE, zone);
  const after = offsetAt(guess + 12 * 60 * MINUTE, zone);
  const valid = [...new Set([before, after])]
    .map((offset) => guess - offset)
    .filter((instant) => offsetAt(instant, zone) === guess - instant);
  return valid.length > 0 ? Math.min(...valid) : guess - before;
}

/**
 * The next runs this schedule would produce, as the scheduler would produce them.
 *
 * Properties copied from `next_occurrence` rather than invented here, because
 * getting any wrong would make the preview a lie about the product: every slot
 * is counted from the slot the owner picked, every slot that has already passed
 * is skipped rather than owed, calendar cadences keep their local time across a
 * clock change, and nothing is previewed after the schedule's end.
 */
export function nextRuns(options: {
  cadence: TaskCadence;
  every: string;
  startAt: string;
  count?: number;
  now?: Date;
  /** The zone the schedule is read in; defaults to this browser's. */
  zone?: string;
  /** The last instant the schedule may run, if it ends. */
  until?: string;
}): Date[] {
  const count = options.count ?? 3;
  const start = new Date(options.startAt);
  if (options.startAt === "" || Number.isNaN(start.getTime())) return [];
  const now = options.now ?? new Date();
  if (options.cadence === "once") return [start];
  if (options.cadence !== "routine") return [];
  const zone = options.zone ?? scheduleZoneName();
  const end = options.until ? new Date(options.until).getTime() : Number.POSITIVE_INFINITY;
  const runs: Date[] = [];
  const keep = (at: number) => {
    if (at > now.getTime() && at <= end) runs.push(new Date(at));
  };
  const interval = RECURRENCE_INTERVAL_MS[options.every];
  const stepDays = CALENDAR_STEP_DAYS[options.every];
  if (stepDays === undefined) {
    if (!interval) return [start];
    let next = start.getTime();
    // The first slot that has not already passed. A first run in the future is
    // itself that slot; one in the past steps forward until it is.
    while (next <= now.getTime()) next += interval;
    for (let index = 0; index < count && next <= end; index += 1, next += interval) keep(next);
    return runs;
  }
  const anchor = wallAt(start.getTime(), zone);
  let day = Date.UTC(anchor.year, anchor.month, anchor.day);
  const today = wallAt(now.getTime(), zone);
  const todayDay = Date.UTC(today.year, today.month, today.day);
  if (todayDay > day) {
    const whole = Math.floor((todayDay - day) / DAY / stepDays);
    day += Math.max(0, whole - 1) * stepDays * DAY;
  }
  for (let guard = 0; runs.length < count && guard < 800; guard += 1, day += stepDays * DAY) {
    const date = new Date(day);
    const weekday = date.getUTCDay();
    if (options.every === "weekdays" && (weekday === 0 || weekday === 6)) continue;
    const at = instantAt(
      {
        year: date.getUTCFullYear(),
        month: date.getUTCMonth(),
        day: date.getUTCDate(),
        hour: anchor.hour,
        minute: anchor.minute,
      },
      zone,
    );
    if (at > end) break;
    keep(at);
  }
  return runs;
}
