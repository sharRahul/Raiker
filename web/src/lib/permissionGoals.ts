/*
 * UX-PERM-05 — the Permissions page's effective posture, said by goal.
 *
 * The page answers "can Raiker use *this capability*" sixty-odd times. An owner
 * arrives with a coarser question — *can Raiker edit my files? send a message
 * for me?* — and had to assemble the answer from several rows. This module
 * answers those questions directly, read-only, from the same effective gates
 * the rows below render, so a summary can never say something the rows do not.
 *
 * Nothing here changes what is enforced. Each goal names the capabilities it
 * reads, and a capability the runtime did not report is simply not counted:
 * a goal with none reported says so rather than guessing "cannot".
 */
import type { CapabilityGate } from "./apiTypes";
import { isAvailable, isDecisionMode, isReady, type DecisionMode } from "./capabilityModel";

export interface PermissionGoal {
  id: string;
  /** The goal as a verb phrase: "edit project files". */
  goal: string;
  capabilities: readonly string[];
}

/** The questions an owner arrives with, each mapped to what answers it. */
export const PERMISSION_GOALS: readonly PermissionGoal[] = [
  { id: "files", goal: "edit project files", capabilities: ["file_write_execution", "patch_apply_execution"] },
  {
    id: "commands",
    goal: "run commands and code",
    capabilities: ["shell_execution", "process_execution", "host_network_code_execution"],
  },
  { id: "git", goal: "commit and push code", capabilities: ["git_write_execution", "git_push_execution"] },
  { id: "web", goal: "read web pages", capabilities: ["web_fetch"] },
  {
    id: "messages",
    goal: "send messages and email",
    capabilities: [
      "email_runtime",
      "external_channel_runtime",
      "connector_gmail_runtime",
      "connector_slack_runtime",
    ],
  },
  { id: "memory", goal: "remember things about you", capabilities: ["memory_write_execution"] },
  { id: "schedule", goal: "run work on a schedule", capabilities: ["scheduled_routines"] },
];

export type GoalVerdict = "automatic" | "allow" | "ask" | "never" | "unknown" | "not_reported";

export interface GoalSummary {
  id: string;
  verdict: GoalVerdict;
  /** The read-only sentence, e.g. "Can edit project files after asking you". */
  sentence: string;
  /** How many of the goal's capabilities can run, of how many were reported. */
  usable: number;
  reported: number;
  /** The capability to reveal when the owner wants to change this. */
  firstCapability: string | null;
}

/** Most permissive first: a goal is as open as its most open usable path. */
const ORDER: DecisionMode[] = ["auto", "allow", "ask", "deny"];

function capitalise(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function goalSummaries(gates: CapabilityGate[]): GoalSummary[] {
  const byName = new Map(gates.map((gate) => [gate.capability, gate]));
  return PERMISSION_GOALS.map((goal) => {
    const reported = goal.capabilities
      .map((name) => byName.get(name))
      .filter((gate): gate is CapabilityGate => gate !== undefined);
    const base = { id: goal.id, reported: reported.length, firstCapability: reported[0]?.capability ?? null };
    if (reported.length === 0) {
      return {
        ...base,
        verdict: "not_reported" as const,
        usable: 0,
        sentence: `This runtime reports nothing that would ${goal.goal}`,
      };
    }
    // Usable means it can run at all. Never is a mode of a usable capability,
    // but for this question it answers the same as off: Raiker cannot.
    const runnable = reported.filter((gate) => isAvailable(gate) && isReady(gate));
    // Unknown is never read as permission (NEW-PERM-03): one unrecognised mode
    // on a runnable capability makes the whole goal unknown, not open.
    if (runnable.some((gate) => !isDecisionMode(gate.decision_mode))) {
      return {
        ...base,
        verdict: "unknown" as const,
        usable: runnable.length,
        sentence: `Unknown whether Raiker can ${goal.goal} — one setting is not one this page recognises`,
      };
    }
    const modes: DecisionMode[] = runnable
      .map((gate) => gate.decision_mode as DecisionMode)
      .filter((mode) => mode !== "deny");
    const usable = modes.length;
    const partial = usable < reported.length ? ` (${usable} of ${reported.length} ways)` : "";
    const open = ORDER.find((mode) => modes.includes(mode));
    switch (open) {
      case "auto":
        return { ...base, verdict: "automatic" as const, usable, sentence: `Can ${goal.goal} on its own, and chain further steps${partial}` };
      case "allow":
        return { ...base, verdict: "allow" as const, usable, sentence: `Can ${goal.goal} without asking${partial}` };
      case "ask":
        return { ...base, verdict: "ask" as const, usable, sentence: `Can ${goal.goal} after asking you${partial}` };
      default:
        return { ...base, verdict: "never" as const, usable: 0, sentence: capitalise(`cannot ${goal.goal}`) };
    }
  });
}
