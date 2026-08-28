/**
 * BUG-71 — what the Memory page is allowed to promise.
 *
 * The page used to tell every owner "When Raiker identifies a useful preference
 * or durable fact, it will propose it for review" regardless of whether any turn
 * could actually propose one. That sentence is true only when the
 * `memory_write_execution` gate is on and its decision mode is not `deny`; with
 * the gate off it described a capability the owner had not turned on, and with
 * the mode at Deny it described one they had explicitly refused.
 *
 * This derives the honest sentence from the same two facts the runtime reads,
 * so the page cannot drift from the gate again. It is pure so it can be tested
 * without a browser.
 */

export type MemoryWritePostureKind = "loading" | "proposes" | "gate_off" | "denied" | "unknown";

export interface MemoryWritePosture {
  kind: MemoryWritePostureKind;
  /** One sentence stating what will happen, in the owner's terms. */
  headline: string;
  /** The single control that changes it, or null when nothing needs changing. */
  action: string | null;
}

const ENABLED_STATES = new Set(["enabled_read_only", "enabled_policy_gated", "enabled_runtime"]);

export function memoryWritePosture(gates: CapabilityGateLike[] | null | undefined): MemoryWritePosture {
  if (gates === undefined) {
    return {
      kind: "loading",
      headline: "Checking memory permissions…",
      action: null,
    };
  }
  if (gates === null) {
    return {
      kind: "unknown",
      headline: "Raiker could not read your memory permissions.",
      action: "Open Permissions",
    };
  }
  const gate = gates.find((entry) => entry.capability === "memory_write_execution");
  if (gate === undefined || !ENABLED_STATES.has(gate.state)) {
    return {
      kind: "gate_off",
      headline:
        "Memory store is off, so no conversation can propose something to remember. This page stays a viewer until you turn it on.",
      action: "Turn on Memory store",
    };
  }
  if (gate.decision_mode === "deny") {
    return {
      kind: "denied",
      headline:
        "Memory store is on but set to Deny, so a proposed memory is refused before it reaches you.",
      action: "Change the decision mode",
    };
  }
  if (gate.decision_mode === "allow") {
    return {
      kind: "proposes",
      headline:
        "Memory store is on and set to Allow, so Raiker stores what it decides is worth remembering without asking each time. Everything it stores appears here.",
      action: null,
    };
  }
  return {
    kind: "proposes",
    headline:
      "Memory store is on. When Raiker decides something is worth remembering it proposes the exact text, and nothing is stored until you approve it.",
    action: null,
  };
}

/** Structural minimum this module needs — kept local so tests need no fixtures. */
export interface CapabilityGateLike {
  capability: string;
  state: string;
  decision_mode: string;
}
