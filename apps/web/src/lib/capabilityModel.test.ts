import { describe, expect, it } from "vitest";
import type { CapabilityGate } from "./apiTypes";
import {
  canDisable,
  canEnable,
  enableableTargets,
  explainCapability,
  gateBadge,
  governsItsOwnCapability,
  runtimeBlock,
  groupByPhase,
  hasNoRoute,
  isDeferred,
  isDisabled,
  isGovernedElsewhere,
  realityLabel,
  realityNote,
  requiresStepUpToken,
} from "./capabilityModel";

function gate(partial: Partial<CapabilityGate>): CapabilityGate {
  return {
    capability: "x",
    phase: 1,
    state: "disabled",
    default_state: "disabled",
    source: "static_default",
    runtime_enabled: false,
    allowed_transitions: [],
    can_current_principal_change: false,
    blocked_reason_code: null,
    readiness: {},
    decision_mode: "ask",
    ...partial,
  };
}

describe("capability state → badge mapping", () => {
  it("maps enabled states to implemented / read-only", () => {
    expect(gateBadge(gate({ state: "enabled_read_only" }))).toBe("read-only");
    expect(gateBadge(gate({ state: "enabled_policy_gated" }))).toBe("implemented");
    expect(gateBadge(gate({ state: "enabled_runtime" }))).toBe("implemented");
  });

  it("maps no-executor capabilities to deferred", () => {
    const g = gate({ state: "disabled", blocked_reason_code: "activation_blocked:no_executor" });
    expect(isDeferred(g)).toBe(true);
    expect(gateBadge(g)).toBe("deferred");
  });

  it("maps plain off/planned (with an enable path) to disabled", () => {
    // A merely-gated capability always offers an enable target from the
    // backend; only a gate with no enable path at all counts as deferred.
    const offWithPath = { allowed_transitions: ["disabled", "enabled_policy_gated"] };
    expect(
      gateBadge(gate({ state: "disabled", blocked_reason_code: "disabled_by_capability_gate", ...offWithPath })),
    ).toBe("disabled");
    expect(gateBadge(gate({ state: "planned", ...offWithPath }))).toBe("disabled");
    expect(isDisabled(gate({ state: "planned" }))).toBe(true);
    expect(isDisabled(gate({ state: "enabled_runtime" }))).toBe(false);
  });

  it("treats a disabled gate with no enable path as deferred (live-runtime shape)", () => {
    const g = gate({ state: "disabled", blocked_reason_code: null, allowed_transitions: ["disabled", "planned"] });
    expect(isDeferred(g)).toBe(true);
  });
});

describe("grouping and explanations", () => {
  it("groups by phase in ascending order", () => {
    const groups = groupByPhase([gate({ phase: 3, capability: "b" }), gate({ phase: 1, capability: "a" })]);
    expect(groups.map((g) => g.phase)).toEqual([1, 3]);
  });

  it("explains a deferred capability as future/not implemented", () => {
    const info = explainCapability(gate({ blocked_reason_code: "activation_blocked:no_executor" }));
    expect(info.kind).toBe("deferred");
    expect(info.requirement.toLowerCase()).toContain("no executor");
  });

  it("explains a gated capability with readiness/needs", () => {
    const info = explainCapability(
      gate({
        blocked_reason_code: "disabled_by_capability_gate",
        allowed_transitions: ["disabled", "enabled_policy_gated"],
        readiness: { policy_ready: true, test_ready: false },
      }),
    );
    expect(info.kind).toBe("gated");
    expect(info.requirement.toLowerCase()).toContain("test");
  });
});

describe("enableability for Security Settings", () => {
  it("offers enable targets only from the backend's allowed_transitions", () => {
    expect(enableableTargets(gate({ allowed_transitions: ["disabled", "enabled_policy_gated"] }))).toEqual([
      "enabled_policy_gated",
    ]);
    expect(
      enableableTargets(gate({ allowed_transitions: ["disabled", "planned", "enabled_read_only"] })),
    ).toEqual([]);
  });

  it("canEnable requires authority and a real enabled target", () => {
    const enableable = gate({ can_current_principal_change: true, allowed_transitions: ["disabled", "enabled_runtime"] });
    expect(canEnable(enableable)).toBe(true);
    // No authority → cannot enable.
    expect(canEnable(gate({ allowed_transitions: ["enabled_runtime"] }))).toBe(false);
    // Authority but no enabled target offered (fail-closed/deferred) → cannot enable.
    expect(canEnable(gate({ can_current_principal_change: true, allowed_transitions: ["disabled", "enabled_read_only"] }))).toBe(false);
  });

  // The backend lists every state a capability *may* hold, including the one it
  // already holds, so an enabled gate named its own enabled state as an enable
  // target. The row rendered "Turn on" next to "Turn off", and pressing it would
  // have set the capability to the state it was already in.
  it("canEnable is false once the gate is already enabled", () => {
    const enabled = gate({
      can_current_principal_change: true,
      state: "enabled_runtime",
      allowed_transitions: ["disabled", "enabled_policy_gated", "enabled_runtime"],
    });
    expect(canEnable(enabled)).toBe(false);
    expect(canDisable(enabled)).toBe(true);
    expect(canEnable({ ...enabled, state: "enabled_policy_gated" })).toBe(false);
    expect(canEnable({ ...enabled, state: "disabled" })).toBe(true);
  });

  it("canDisable requires authority and a currently-enabled gate", () => {
    expect(canDisable(gate({ can_current_principal_change: true, state: "enabled_runtime" }))).toBe(true);
    expect(canDisable(gate({ can_current_principal_change: true, state: "disabled" }))).toBe(false);
    expect(canDisable(gate({ can_current_principal_change: false, state: "enabled_runtime" }))).toBe(false);
  });

  it("flags Tier-2 caps as needing a step-up confirmation token", () => {
    expect(requiresStepUpToken("shell_execution")).toBe(true);
    expect(requiresStepUpToken("web_fetch")).toBe(true);
    expect(requiresStepUpToken("mcp_builder_runtime")).toBe(true);
    expect(requiresStepUpToken("mcp_connector_runtime")).toBe(true);
    expect(requiresStepUpToken("audit_export")).toBe(false);
  });

  // BUG-11 — three shut states, three different actions. Telling an owner to
  // "enable it in Capabilities" when the capability is already enabled sends
  // them somewhere that cannot fix it.
  it("names why a runtime-gated surface is blocked, and where to fix it", () => {
    expect(runtimeBlock(gate({ runtime_enabled: true }), "MCP").kind).toBe("none");

    const off = runtimeBlock(
      gate({ state: "disabled", runtime_enabled: false, allowed_transitions: ["enabled_runtime"] }),
      "MCP",
    );
    expect(off.kind).toBe("gate_off");
    expect(off.reason).toMatch(/turned off/i);
    expect(off.href).toBe("#/capabilities");

    const below = runtimeBlock(
      gate({
        state: "enabled_policy_gated",
        runtime_enabled: false,
        allowed_transitions: ["enabled_runtime"],
      }),
      "MCP",
    );
    expect(below.kind).toBe("below_runtime");
    expect(below.reason).toMatch(/enabled, but only at/i);
    // One runtime: there is no mode to activate first, so the only action that
    // raises a capability to runtime level lives in Permissions.
    expect(below.href).toBe("#/capabilities");

    // No executor in this runtime: nowhere to send the owner, so say that
    // rather than offer an action that cannot work.
    const deferred = runtimeBlock(
      gate({ state: "disabled", runtime_enabled: false, allowed_transitions: [] }),
      "MCP",
    );
    expect(deferred.kind).toBe("not_available");
    expect(deferred.href).toBeNull();

    // A gate that could not be read is treated as shut, never as open.
    expect(runtimeBlock(undefined, "MCP").kind).toBe("gate_off");
  });
});

// ── GEP-04: what the switch actually decides ────────────────────────────────
// The page renders every gate as a switch. For fifteen capabilities, flipping it
// changed nothing — either nothing reached the executor, or a different control
// governed the work. These assert the card can tell the owner which it is.

describe("gate reality", () => {
  it("treats a payload with no gate_reality as governing its own capability", () => {
    const g = gate({ capability: "shell_execution" });
    expect(governsItsOwnCapability(g)).toBe(true);
    expect(realityLabel(g)).toBe("");
    expect(realityNote(g)).toBe("");
  });

  it("labels a capability whose work runs under a different control", () => {
    const g = gate({
      capability: "scheduled_routines",
      gate_reality: "governed_elsewhere",
      governance_note: "A scheduled task runs as one whole governed turn.",
    });
    expect(isGovernedElsewhere(g)).toBe(true);
    expect(governsItsOwnCapability(g)).toBe(false);
    expect(realityLabel(g)).toBe("Governed elsewhere");
    expect(realityNote(g)).toBe("A scheduled task runs as one whole governed turn.");
  });

  it("labels a capability nothing in the product reaches", () => {
    const g = gate({
      capability: "reminder_runtime",
      gate_reality: "no_path",
      governance_note: "Reminders have no owner surface and no model tool.",
    });
    expect(hasNoRoute(g)).toBe(true);
    expect(realityLabel(g)).toBe("No route yet");
    expect(realityNote(g)).toBe("Reminders have no owner surface and no model tool.");
  });

  it("shows no note for a switch that means what it says, even if one is sent", () => {
    // Defensive: a note on an own_gate row would read as a caveat on a control
    // that has none, so the model drops it rather than rendering it.
    const g = gate({ gate_reality: "own_gate", governance_note: "stray" });
    expect(realityNote(g)).toBe("");
  });
});
