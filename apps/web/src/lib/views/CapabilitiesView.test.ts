import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import CapabilitiesView from "./CapabilitiesView.svelte";
import { makeGate, stubFetch } from "../test-helpers";

// Decision modes arrive inline on each gate (gate.decision_mode) from the single
// /api/capability-gates read — no per-capability fan-out.
const GATES = [
  makeGate({
    capability: "shell_execution",
    phase: 3,
    state: "enabled_runtime",
    can_current_principal_change: true,
    allowed_transitions: ["disabled"],
    decision_mode: "ask",
  }),
  makeGate({
    capability: "finance_runtime",
    phase: 3,
    state: "disabled",
    blocked_reason_code: "activation_blocked:no_executor",
    decision_mode: "ask",
  }),
];

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("CapabilitiesView", () => {
  it("shows friendly labels and inline decision modes, with no implementation-status badges", async () => {
    stubFetch({ "GET /api/capability-gates": GATES });
    render(CapabilitiesView, { principal: "prin_owner" });
    await waitFor(() => {
      expect(screen.getAllByRole("group", { name: /decision mode/i })).toHaveLength(2);
    });
    expect(screen.getByText("Shell commands")).toBeInTheDocument();
    expect(screen.getByText("Finance")).toBeInTheDocument();

    // Every capability exposes the Ask/Allow/Auto/Deny control inline, defaulting to Ask.
    expect(screen.getAllByRole("button", { name: "Ask", pressed: true })).toHaveLength(2);

    // The implementation-status badges (Implemented / Deferred / Disabled) are gone.
    expect(screen.queryByText("Implemented")).not.toBeInTheDocument();
    expect(screen.queryByText("Deferred")).not.toBeInTheDocument();
    expect(screen.queryByText("Disabled")).not.toBeInTheDocument();
  });

  it("loads the whole matrix in a single gates request (no per-capability fan-out)", async () => {
    const mock = stubFetch({ "GET /api/capability-gates": GATES });
    render(CapabilitiesView, { principal: "prin_owner" });
    await waitFor(() => {
      expect(screen.getAllByRole("group", { name: /decision mode/i })).toHaveLength(2);
    });
    // No GET to the per-capability decision-mode endpoint.
    expect(
      mock.mock.calls.filter(([u]) => String(u).includes("/api/capability-modes/")),
    ).toHaveLength(0);
  });

  it("applies a tightening mode (deny) immediately without a step-up dialog", async () => {
    stubFetch({
      "GET /api/capability-gates": GATES,
      "POST /api/capability-modes/shell_execution/deny": {
        ok: true,
        capability: "shell_execution",
        decision_mode: "deny",
      },
    });
    render(CapabilitiesView, { principal: "prin_owner" });
    const shellGroup = await waitFor(() =>
      screen.getByRole("group", { name: /shell commands/i }),
    );
    await fireEvent.click(within(shellGroup).getByRole("button", { name: "Deny" }));
    await waitFor(() => {
      expect(screen.getByText(/is now set to “Deny”/i)).toBeInTheDocument();
    });
    expect(within(shellGroup).getByRole("button", { name: "Deny", pressed: true })).toBeInTheDocument();
    // No step-up dialog for a tightening change.
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("requires the step-up dialog to loosen a mode (allow)", async () => {
    stubFetch({ "GET /api/capability-gates": GATES });
    render(CapabilitiesView, { principal: "prin_owner" });
    const shellGroup = await waitFor(() =>
      screen.getByRole("group", { name: /shell commands/i }),
    );
    await fireEvent.click(within(shellGroup).getByRole("button", { name: "Allow" }));
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
    expect(screen.getByText(/set shell commands to “allow”/i)).toBeInTheDocument();
  });

  it("filters capabilities by search", async () => {
    stubFetch({ "GET /api/capability-gates": GATES });
    render(CapabilitiesView, { principal: "prin_owner" });
    await waitFor(() => {
      expect(screen.getByText("Shell commands")).toBeInTheDocument();
    });
    await fireEvent.input(screen.getByLabelText(/search capabilities/i), {
      target: { value: "finance" },
    });
    expect(screen.queryByText("Shell commands")).not.toBeInTheDocument();
    expect(screen.getByText("Finance")).toBeInTheDocument();
  });
});
