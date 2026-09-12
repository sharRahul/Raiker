/*
 * The two questions the Permissions page is actually answering.
 *
 * The page exposed availability (`On` / `Off`) and decision mode (`Ask` /
 * `Allow` / `Auto` / `Deny`) side by side at nearly equal weight. Both are real
 * backend concepts and both must stay, but read together they are not
 * self-explanatory — the review lists the questions an owner is left with, and
 * every one of them is fair:
 *
 *   How can a capability be On and Deny?
 *   What does Off + Ask mean?
 *   Is Allow another way of turning it on?
 *   What is the difference between On, Allow and Auto?
 *
 * They are not parallel systems. One is *whether Raiker may use this at all*;
 * the other is *what happens when it wants to*. So the page asks them as two
 * questions, in that order, and the words answer in the owner's terms: `deny`
 * stays `deny` in the store and reads as **Never** on screen.
 *
 * Nothing here changes what the runtime enforces. This module is wording and
 * ordering only — the authority model is unchanged, and a capability's
 * behaviour is still decided by the gate, never by the label over it.
 */

import { capabilityLabel, type DecisionMode } from "./capabilityModel";
import type { CapabilityGate } from "./apiTypes";

/** The first question, in the owner's words. */
export const AVAILABILITY_QUESTION = "Can Raiker use this?";
/** The second, which only matters once the first is yes. */
export const BEHAVIOUR_QUESTION = "When Raiker wants to use it";

export interface BehaviourCopy {
  /** What the owner reads on the control. */
  label: string;
  /** What pressing it means, said without naming a backend concept. */
  hint: string;
}

/**
 * The behaviour vocabulary.
 *
 * `Never` rather than `Deny` because it answers the *when* question — "when
 * Raiker wants to use it: never" — which is also what makes On + Never
 * intelligible instead of contradictory: the capability exists and is
 * available, and every attempt to use it is refused.
 */
export const BEHAVIOUR_COPY: Record<DecisionMode, BehaviourCopy> = {
  ask: {
    label: "Ask me",
    hint: "Raiker stops and waits for your approval every time (default).",
  },
  allow: {
    label: "Allow",
    hint: "Raiker goes ahead without asking, inside the limits your policy sets.",
  },
  auto: {
    label: "Automatic",
    hint: "Raiker goes ahead and may chain further steps of its own. The most permissive.",
  },
  deny: {
    label: "Never",
    hint: "Raiker is refused every time, even though the capability is available.",
  },
};

/**
 * The one line a collapsed row shows: availability, then behaviour.
 *
 * Both facts on the closed row is the point — a permission list that has to be
 * opened row by row to learn what is on cannot be scanned, and scanning is the
 * whole reason to have the list.
 */
export function rowSummary(
  gate: Pick<CapabilityGate, "state" | "decision_mode">,
  available: boolean,
): string {
  const behaviour = BEHAVIOUR_COPY[gate.decision_mode as DecisionMode];
  const availability = available ? "On" : "Off";
  return behaviour === undefined ? availability : `${availability} · ${behaviour.label}`;
}

/**
 * The handful an owner actually comes to change, above the full registry.
 *
 * Sixty-six equally weighted cards is a registry, not a page: the capabilities
 * people arrive to adjust are a short list, and the rest is reference. Named by
 * backend capability so the section cannot drift from what it claims to
 * control; anything not installed in this build simply does not appear.
 */
export const COMMON_PERMISSIONS = [
  "web_fetch",
  "file_write_execution",
  "shell_execution",
  "git_push_execution",
  "external_channel_runtime",
] as const;

export function commonGates(gates: CapabilityGate[]): CapabilityGate[] {
  const byName = new Map(gates.map((gate) => [gate.capability, gate]));
  return COMMON_PERMISSIONS.map((name) => byName.get(name)).filter(
    (gate): gate is CapabilityGate => gate !== undefined,
  );
}

/**
 * Owner wording for the one refusal this page has to state often.
 *
 * "Not permitted for your principal" names an internal concept to explain a
 * limit the owner cannot do anything about. The fact is the same; the sentence
 * is about their account rather than about our vocabulary.
 */
export const CANNOT_CHANGE_HERE = "This setting cannot be changed for this account.";

export interface PermissionAttention {
  capability: string;
  label: string;
  /** Why it is here, in one clause. */
  reason: string;
}

/**
 * What on this page needs the owner.
 *
 * Deliberately narrow, and narrowed twice. The first version counted every
 * capability the *build* cannot offer — "no route yet", "governed elsewhere" —
 * which put fifteen rows under a heading that says *needs your attention* and
 * offered no action for any of them; a fact about what this build ships is not
 * a decision an owner has to make. The second added "switched on but the
 * runtime is not running it", which cannot happen: `runtime_enabled` is derived
 * from the gate's own state in `raiker/phase_gates.py`, so the two can never
 * disagree, and a rule that can never fire is a rule that only looks like
 * safety.
 *
 * What is left is the one state that genuinely wants a second look: a
 * capability set to run automatically. It is the only mode that acts with
 * nobody in the loop, so it is the one an owner may want to be reminded they
 * left on. When nothing is automatic this returns nothing, and the page says so
 * by showing no attention section at all.
 */
export function permissionAttention(gates: CapabilityGate[]): PermissionAttention[] {
  return gates
    .filter((gate) => gate.decision_mode === "auto")
    .map((gate) => ({
      capability: gate.capability,
      label: capabilityLabel(gate.capability),
      reason: "runs automatically, without asking you",
    }));
}
