// What belongs on the Observability overview under "What changed?".
//
// The overview is a digest, not the record. The record is the audit log, and it
// keeps everything — that is the point of it. The digest answers one question,
// and it was answering it with the wrong material twice over: on a quiet
// workspace with twelve identical authorization lookups, and after a single
// chat turn with twelve rows of that turn's own pipeline. Either way a real
// change — a capability turned on, a tool that ran, a task created — was pushed
// off the list by something that is not news.
//
// The discriminator is not a new hand-written list of "important" events. It is
// the one the transcript already uses: `turnPhases.ts` maps the lifecycle
// events the runtime streams into a turn's own gather → plan → act → verify
// timeline. An event the transcript already shows inside a turn is that turn's
// trace. It is not a change to the workspace, and it is one click away under
// "Open the full audit log".
import { phaseForEvent } from "./turnPhases";

/**
 * Turn-internal events that never reach a phase row, so `phaseForEvent` does
 * not know them, and that are still a turn's own mechanics rather than news.
 *
 * Deliberately short. Anything not listed here and not in a phase — a tool that
 * really executed, a capability the owner changed, a task created, an approval
 * decided — is a change and stays.
 */
const TURN_MECHANICS = new Set([
  // The turn state machine's own steps. One turn writes four or more.
  "turn_state_changed",
  // The skill index the runtime refreshes before it reads. Nothing changed
  // because of the owner, and nothing changed for the owner.
  "skills_indexed",
  // Every governed read resolves the acting principal first and records that it
  // did. A resolution that *failed* is news and is deliberately not here.
  "principal_resolved",
]);

/** Whether this event is one turn's own trace rather than a change. */
export function isTurnTrace(eventType: string): boolean {
  return phaseForEvent(eventType) !== null || TURN_MECHANICS.has(eventType);
}

/** The most recent changes, newest first, for the overview digest. */
export function digestEvents<T extends { event_type: string }>(
  events: readonly T[],
  limit = 12,
): T[] {
  return events.filter((event) => !isTurnTrace(event.event_type)).slice(0, limit);
}
