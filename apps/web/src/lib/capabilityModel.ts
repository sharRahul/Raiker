import type { CapabilityGate } from "./apiTypes";
import type { BadgeVariant } from "./types";

// Capability gate states that mean the gate is enabled (anything else is off / not yet enabled).
const ENABLED_STATES = new Set(["enabled_read_only", "enabled_policy_gated", "enabled_runtime"]);

/** True when the gate is not enabled (off, planned, or only "readiness"-ready). */
export function isDisabled(gate: CapabilityGate): boolean {
  return !ENABLED_STATES.has(gate.state);
}

/** A capability with no real executor is deferred (future), not merely gated. */
export function isDeferred(gate: CapabilityGate): boolean {
  const reason = gate.blocked_reason_code ?? "";
  return reason.includes("no_executor") || reason.includes("no_requirement_entry");
}

/** Map a backend gate to a status badge (text + shape; never colour-only). */
export function gateBadge(gate: CapabilityGate): BadgeVariant {
  if (gate.state === "enabled_read_only") return "read-only";
  if (ENABLED_STATES.has(gate.state)) return "implemented";
  if (isDeferred(gate)) return "deferred";
  return "disabled";
}

/** Group gates by backend phase (a real backend field) for the matrix. */
export function groupByPhase(gates: CapabilityGate[]): { phase: number; gates: CapabilityGate[] }[] {
  const byPhase = new Map<number, CapabilityGate[]>();
  for (const gate of gates) {
    const list = byPhase.get(gate.phase) ?? [];
    list.push(gate);
    byPhase.set(gate.phase, list);
  }
  return [...byPhase.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([phase, list]) => ({
      phase,
      gates: [...list].sort((a, b) => a.capability.localeCompare(b.capability)),
    }));
}

export interface CapabilityExplanation {
  status: string;
  why: string;
  requirement: string;
  kind: "deferred" | "gated" | "enabled";
}

const REASON_TEXT: Record<string, string> = {
  "activation_blocked:no_executor": "No runtime exists for this capability yet.",
  "activation_blocked:no_requirement_entry": "This capability is not flippable in this runtime.",
  "activation_blocked:runtime_mode_not_active": "The required runtime mode is not active.",
  "activation_blocked:no_threat_model_ack": "A threat-model acknowledgement is required.",
  "activation_blocked:needs_human_confirmation": "A human confirmation token is required.",
  disabled_by_capability_gate: "The capability gate is turned off.",
};

/** Plain-English explanation for the DisabledCapabilityExplainer. */
export function explainCapability(gate: CapabilityGate): CapabilityExplanation {
  if (ENABLED_STATES.has(gate.state)) {
    return { status: gate.state, why: "Enabled.", requirement: "—", kind: "enabled" };
  }
  const reason = gate.blocked_reason_code ?? "";
  const why = REASON_TEXT[reason] ?? (reason ? reason : "This capability is currently off.");
  const notReady = Object.entries(gate.readiness)
    .filter(([, ready]) => !ready)
    .map(([key]) => key.replace(/_ready$/, ""));
  const deferred = isDeferred(gate);
  const requirement = deferred
    ? "Not available in the local single-user runtime (no executor)."
    : notReady.length > 0
      ? `Pending readiness: ${notReady.join(", ")}.`
      : "Enable via Security Settings → Runtime Mutations (if your principal is authorised).";
  return {
    status: gate.state,
    why,
    requirement,
    kind: deferred ? "deferred" : "gated",
  };
}
