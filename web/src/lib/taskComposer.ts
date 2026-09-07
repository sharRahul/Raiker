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
