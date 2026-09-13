/*
 * One effective permission model, for every presentation on the page.
 *
 * NEW-PERM-02 — the Permissions page rendered the same capability four times:
 * the segmented control, the Common permissions summary, the Needs your
 * attention list and the authority table. Only the control read the modes the
 * owner had just changed. The other three read the gate list as it arrived from
 * the last `GET /api/capability-gates`, so setting a capability to **Never**
 * left the control saying Never and the summary above it still saying
 * Automatic, until a refresh nobody was told to make.
 *
 * A permissions page that answers the same question two ways is worse than one
 * that answers slowly: the owner cannot tell which answer is the one the
 * runtime will act on. So there is one list. A confirmed mutation is merged
 * into it, every presentation derives from the result, and nothing derives from
 * the raw read once a mutation has landed on top of it.
 *
 * None of this is enforcement. The runtime decides what a capability does; this
 * module decides what the page is allowed to claim about it, and the rule is
 * that it may only claim what the server has confirmed.
 */

import type { CapabilityGate } from "./apiTypes";
import { capabilityLabel, type DecisionMode } from "./capabilityModel";

/**
 * A mode the server has confirmed, and when.
 *
 * The sequence number is what stops a slow refresh from undoing a fast
 * mutation. A read that left before the change was confirmed carries the old
 * mode in good faith; merging it over the confirmation would show the owner a
 * value the server no longer holds. So each confirmation is stamped, and a read
 * may only clear the confirmations that are older than the read itself.
 */
export interface ConfirmedMode {
  mode: DecisionMode;
  seq: number;
}

export type ConfirmedModes = Record<string, ConfirmedMode>;

/** Record one server-confirmed mode change. */
export function confirmMode(
  confirmed: ConfirmedModes,
  capability: string,
  mode: DecisionMode,
  seq: number,
): ConfirmedModes {
  return { ...confirmed, [capability]: { mode, seq } };
}

/**
 * The gate list every presentation reads: the server's, with confirmations on
 * top.
 *
 * A confirmation for a capability this build does not list is dropped rather
 * than invented into a row — the read is authoritative about *which*
 * capabilities exist, and only the mode is overlaid.
 */
export function effectiveGates(
  gates: CapabilityGate[],
  confirmed: ConfirmedModes,
): CapabilityGate[] {
  return gates.map((gate) => {
    const entry = confirmed[gate.capability];
    if (entry === undefined || entry.mode === gate.decision_mode) return gate;
    return { ...gate, decision_mode: entry.mode };
  });
}

/** The plain mode values, for controls that take a mode map. */
export function confirmedModeValues(confirmed: ConfirmedModes): Record<string, DecisionMode> {
  return Object.fromEntries(
    Object.entries(confirmed).map(([capability, entry]) => [capability, entry.mode]),
  );
}

/**
 * The confirmations a read that started at `startedAt` is allowed to clear.
 *
 * A fresh read carries every mode the server held when it left, so the
 * confirmations it already reflects are redundant and are dropped. Anything
 * confirmed *after* the read left is newer than what came back and is kept, so
 * an in-flight refresh cannot roll the page back to a value the owner has
 * already changed.
 */
export function survivingModes(confirmed: ConfirmedModes, startedAt: number): ConfirmedModes {
  return Object.fromEntries(
    Object.entries(confirmed).filter(([, entry]) => entry.seq > startedAt),
  );
}

/**
 * What a bulk change actually did, per capability.
 *
 * The previous loop stopped at the first refusal and reported "The bulk change
 * was rejected", which is untrue in the ordinary case: the capabilities already
 * set stayed set, and the sentence told the owner they had not. A partial
 * result is a normal outcome of applying N independent governed mutations, so
 * it is reported as one — what changed, and what did not, by name.
 */
export function bulkOutcome(
  applied: string[],
  failed: string[],
): { kind: "ok" | "error"; text: string } | null {
  const names = (caps: string[]) => caps.map((cap) => capabilityLabel(cap)).join(", ");
  if (applied.length === 0 && failed.length === 0) return null;
  if (failed.length === 0) {
    const count = applied.length;
    return {
      kind: "ok",
      text: `${count} capabilit${count === 1 ? "y" : "ies"} changed.`,
    };
  }
  if (applied.length === 0) {
    return { kind: "error", text: `No capability was changed. Refused: ${names(failed)}.` };
  }
  return {
    kind: "error",
    text: `${applied.length} changed; ${failed.length} refused and left as ${
      failed.length === 1 ? "it was" : "they were"
    }: ${names(failed)}.`,
  };
}
