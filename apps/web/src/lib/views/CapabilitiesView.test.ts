import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import CapabilitiesView from "./CapabilitiesView.svelte";
import { makeGate, stubFetch } from "../test-helpers";

const GATES = [
  makeGate({
    capability: "shell_execution",
    phase: 3,
    state: "enabled_runtime",
    can_current_principal_change: true,
    allowed_transitions: ["disabled"],
  }),
  makeGate({
    capability: "finance_runtime",
    phase: 3,
    state: "disabled",
    blocked_reason_code: "activation_blocked:no_executor",
  }),
];

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("CapabilitiesView", () => {
  it("renders every gate with friendly labels and honest badges", async () => {
    stubFetch({ "GET /api/capability-gates": GATES });
    render(CapabilitiesView, { principal: "prin_owner" });
    await waitFor(() => {
      expect(screen.getByText("Shell commands")).toBeInTheDocument();
    });
    expect(screen.getByText("Finance")).toBeInTheDocument();
    // Deferred (no executor) is shown as deferred, not enableable.
    expect(screen.getByText("Deferred")).toBeInTheDocument();
  });

  it("loads the decision mode lazily when a capability is expanded", async () => {
    const mock = stubFetch({
      "GET /api/capability-gates": GATES,
      "GET /api/capability-modes/shell_execution": {
        ok: true,
        capability: "shell_execution",
        decision_mode: "ask",
      },
    });
    render(CapabilitiesView, { principal: "prin_owner" });
    await waitFor(() => {
      expect(screen.getByText("Shell commands")).toBeInTheDocument();
    });
    // No decision-mode fetch until expanded.
    expect(
      mock.mock.calls.filter(([u]) => String(u).includes("/api/capability-modes/")),
    ).toHaveLength(0);
    await fireEvent.click(screen.getByRole("button", { name: /shell commands/i }));
    await waitFor(() => {
      expect(screen.getByRole("group", { name: /decision mode/i })).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Ask", pressed: true })).toBeInTheDocument();
    // Disable is offered for the enabled gate; enable is not.
    expect(screen.getByRole("button", { name: /disable gate/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /enable gate/i })).not.toBeInTheDocument();
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
