import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { CapabilityGate, RuntimeMode } from "./apiTypes";

const capabilityGates = vi.fn();
const runtimeMode = vi.fn();
const setCapabilityState = vi.fn();
const disableCapability = vi.fn();
const activateRuntimeMode = vi.fn();
const disableRuntimeMode = vi.fn();

vi.mock("./api", () => ({
  api: {
    capabilityGates: () => capabilityGates(),
    runtimeMode: () => runtimeMode(),
    setCapabilityState: (cap: string, body: unknown) => setCapabilityState(cap, body),
    disableCapability: (cap: string, reason: string) => disableCapability(cap, reason),
    activateRuntimeMode: (m: string, r: string) => activateRuntimeMode(m, r),
    disableRuntimeMode: (r: string) => disableRuntimeMode(r),
  },
  ApiError: class ApiError extends Error {
    constructor(
      readonly status: number,
      readonly reasonCode: string | null,
    ) {
      super("err");
    }
  },
}));

function gate(partial: Partial<CapabilityGate>): CapabilityGate {
  return {
    capability: "x",
    phase: 3,
    state: "disabled",
    default_state: "disabled",
    source: "static_default",
    runtime_enabled: false,
    allowed_transitions: [],
    can_current_principal_change: true,
    blocked_reason_code: null,
    readiness: {},
    ...partial,
  };
}

const MODE: RuntimeMode = {
  mode_name: "local_single_user_runtime",
  status: "active",
  activated_by: "principal_rahul",
  activated_at: "2026-06-22T17:00:00Z",
  reason: "",
  allowed_modes: ["local_single_user_runtime", "local_single_user_safe"],
};

const GATES: CapabilityGate[] = [
  // Supported, enableable by the owner.
  gate({
    capability: "audit_export",
    phase: 3,
    allowed_transitions: ["disabled", "enabled_policy_gated"],
  }),
  // Fail-closed / deferred: no enabled targets offered.
  gate({
    capability: "vector_embedding_runtime",
    phase: 3,
    allowed_transitions: ["disabled", "planned", "enabled_read_only"],
  }),
  // Not permitted for this principal.
  gate({
    capability: "shell_execution",
    phase: 3,
    can_current_principal_change: false,
    blocked_reason_code: "only_runtime_gate_manager_can_manage_gates",
  }),
];

describe("SecuritySettingsPanel", () => {
  beforeEach(() => {
    capabilityGates.mockReset().mockResolvedValue(GATES);
    runtimeMode.mockReset().mockResolvedValue(MODE);
    setCapabilityState.mockReset().mockResolvedValue({ ok: true });
    disableCapability.mockReset();
    activateRuntimeMode.mockReset();
    disableRuntimeMode.mockReset();
  });

  it("shows the deferred Secret Settings notice and has NO secret input fields", async () => {
    const { default: Panel } = await import("./SecuritySettingsPanel.svelte");
    const { container } = render(Panel, { props: { principal: "principal_rahul" } });

    expect(await screen.findByText(/Secret storage is not implemented/i)).toBeInTheDocument();
    // No password / secret inputs anywhere on the security surface.
    expect(container.querySelectorAll('input[type="password"]').length).toBe(0);
    const named = container.querySelectorAll(
      'input[name*="secret" i], input[name*="password" i], input[name*="api" i], input[name*="token" i]',
    );
    expect(named.length).toBe(0);
  });

  it("offers Enable for a supported gate and forwards reason via the step-up dialog", async () => {
    const { default: Panel } = await import("./SecuritySettingsPanel.svelte");
    render(Panel, { props: { principal: "principal_rahul" } });

    // The supported gate row has an Enable control.
    const enableButtons = await screen.findAllByRole("button", { name: /^enable$/i });
    expect(enableButtons.length).toBeGreaterThan(0);
    await fireEvent.click(enableButtons[0]);

    // Step-up dialog requires a reason before confirming.
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toBeInTheDocument();
    const confirm = screen.getByRole("button", { name: /confirm change/i });
    expect(confirm).toBeDisabled();

    await fireEvent.input(screen.getByLabelText(/reason/i), { target: { value: "enable export" } });
    expect(confirm).toBeEnabled();
    await fireEvent.click(confirm);

    await waitFor(() =>
      expect(setCapabilityState).toHaveBeenCalledWith("audit_export", {
        target_state: "enabled_policy_gated",
        reason: "enable export",
        confirmation_token: undefined,
      }),
    );
  });

  it("renders a fail-closed cap as un-enableable with the explainer (no Enable control, no call)", async () => {
    const { default: Panel } = await import("./SecuritySettingsPanel.svelte");
    render(Panel, { props: { principal: "principal_rahul" } });

    expect(await screen.findByText("vector_embedding_runtime")).toBeInTheDocument();
    // The explainer's "To enable" line appears for the deferred cap.
    expect(screen.getAllByText(/To enable/i).length).toBeGreaterThan(0);
    // Exactly one Enable button (the supported gate); the deferred cap has none.
    expect(screen.getAllByRole("button", { name: /^enable$/i }).length).toBe(1);
  });

  it("hides controls and explains when the principal is not authorised", async () => {
    const { default: Panel } = await import("./SecuritySettingsPanel.svelte");
    render(Panel, { props: { principal: "principal_rahul" } });

    expect(await screen.findByText("shell_execution")).toBeInTheDocument();
    expect(screen.getByText(/Not permitted for your principal/i)).toBeInTheDocument();
  });

  it("requires a Tier-2 confirmation token before enabling shell/network caps", async () => {
    // Owner can change a Tier-2 cap that offers an enabled target.
    capabilityGates.mockResolvedValue([
      gate({
        capability: "web_fetch",
        phase: 2,
        allowed_transitions: ["disabled", "enabled_runtime"],
      }),
    ]);
    const { default: Panel } = await import("./SecuritySettingsPanel.svelte");
    render(Panel, { props: { principal: "principal_rahul" } });

    await fireEvent.click(await screen.findByRole("button", { name: /^enable$/i }));
    await fireEvent.input(screen.getByLabelText(/reason/i), { target: { value: "need it" } });
    // Reason alone is not enough — the token + threat ack are required for Tier-2.
    expect(screen.getByRole("button", { name: /confirm change/i })).toBeDisabled();
    expect(screen.getByLabelText(/confirmation token/i)).toBeInTheDocument();
  });
});
