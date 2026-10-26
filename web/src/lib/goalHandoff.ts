/**
 * QUI-F03 / BUG-355 — a goal's intake, started from Chat.
 *
 * *Make this a goal* on a turn, and *Track it* on a goal Raiker noticed, open
 * Work › Goals with the form filled in from the owner's own words. Goals is
 * code-split and mounts only when its route is entered, so the draft waits
 * here as a one-shot request the next Goals mount takes (the pattern
 * `scheduleHandoff.ts` uses for Tasks).
 *
 * It carries text, not authority: nothing is created until the owner saves the
 * form, and a saved goal is a draft that runs only once accepted and started.
 */
export interface GoalDraft {
  title: string;
  objective: string;
  /** The conversation it came from, named in the form so the owner knows why it is filled. */
  fromTitle: string | null;
  projectId: string | null;
}

let pending: GoalDraft | null = null;

/** A short outcome from a request: its first line, at most 80 characters. */
export function goalTitle(text: string): string {
  const line = text.split("\n").map((part) => part.trim()).find((part) => part !== "") ?? "";
  const capital = line.charAt(0).toUpperCase() + line.slice(1);
  return capital.length <= 80 ? capital : `${capital.slice(0, 79).trimEnd()}…`;
}

/** Ask the next Goals mount to open its form with this filled in. */
export function requestGoalDraft(draft: GoalDraft): void {
  pending = { ...draft, objective: draft.objective.trim().slice(0, 4000) };
}

/** Take the waiting draft, if any. Reading it clears it. */
export function takeGoalDraft(): GoalDraft | null {
  const draft = pending;
  pending = null;
  return draft;
}
