import { render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import type { CapabilityGate } from "./apiTypes";

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

const FIXTURE: CapabilityGate[] = [
  gate({ capability: "file_read", phase: 1, state: "enabled_read_only" }),
  gate({ capability: "shell_execution", phase: 3, blocked_reason_code: "activation_blocked:no_executor" }),
  gate({
    capability: "graph_indexing",
    phase: 3,
    blocked_reason_code: "disabled_by_capability_gate",
    can_current_principal_change: true,
  }),
];

vi.mock("./api", () => ({
  api: { capabilityGates: vi.fn().mockResolvedValue(FIXTURE) },
  ApiError: class ApiError extends Error {},
}));

describe("CapabilityMatrix", () => {
  it("renders disabled and deferred capabilities with the right badges", async () => {
    const { default: CapabilityMatrix } = await import("./CapabilityMatrix.svelte");
    render(CapabilityMatrix);

    // Enabled read-only capability.
    expect(await screen.findByText("Read-only")).toBeInTheDocument();
    // No-executor capability is deferred; gated capability is disabled.
    expect(await screen.findByText("Deferred")).toBeInTheDocument();
    expect((await screen.findAllByText("Disabled")).length).toBeGreaterThan(0);
    // Off capabilities link to Security Settings for enablement (no inline enable here).
    expect((await screen.findAllByText(/Enable in Security Settings/)).length).toBeGreaterThan(0);
  });
});
