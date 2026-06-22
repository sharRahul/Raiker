import { describe, expect, it } from "vitest";
import type { CapabilityGate } from "./apiTypes";
import { explainCapability, gateBadge, groupByPhase, isDeferred, isDisabled } from "./capabilityModel";

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

  it("maps plain off/planned to disabled", () => {
    expect(gateBadge(gate({ state: "disabled", blocked_reason_code: "disabled_by_capability_gate" }))).toBe("disabled");
    expect(gateBadge(gate({ state: "planned" }))).toBe("disabled");
    expect(isDisabled(gate({ state: "planned" }))).toBe(true);
    expect(isDisabled(gate({ state: "enabled_runtime" }))).toBe(false);
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
      gate({ blocked_reason_code: "disabled_by_capability_gate", readiness: { policy_ready: true, test_ready: false } }),
    );
    expect(info.kind).toBe("gated");
    expect(info.requirement.toLowerCase()).toContain("test");
  });
});
