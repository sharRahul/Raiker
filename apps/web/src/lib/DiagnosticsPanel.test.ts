import { render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import type { Diagnostics } from "./apiTypes";

const FIXTURE: Diagnostics = {
  runtime_mode: "local_single_user_runtime",
  production_ready_local_single_user_runtime: true,
  summary: {},
  counts: { sessions: 2, events: 17, checkpoints: 3, tasks: 1 },
  disabled_capabilities: ["shell_execution", "email_runtime"],
  readiness: {
    owner_bootstrapped: true,
    runtime_gate_manager_available: true,
    dangerous_capabilities_disabled: false,
  },
  missing_config: ["No model profile is selected."],
  provider_health: [
    {
      profile_id: "raiker-local-llama-cpp",
      provider: "llama.cpp",
      model: "local",
      endpoint_kind: "http",
      local_only: true,
      requires_network: false,
      selected: true,
      status: "selected",
      detail: "local provider; reachability not probed here",
    },
  ],
  scope_note: "Status reflects the local single-user runtime only.",
};

vi.mock("./api", () => ({
  api: { diagnostics: vi.fn().mockResolvedValue(FIXTURE) },
  ApiError: class ApiError extends Error {},
}));

describe("DiagnosticsPanel", () => {
  it("renders readiness, missing config, provider health, disabled caps and the scope note", async () => {
    const { default: DiagnosticsPanel } = await import("./DiagnosticsPanel.svelte");
    render(DiagnosticsPanel);

    // Scope note (no overclaim beyond the local single-user runtime).
    expect(await screen.findByText(/local single-user runtime only/i)).toBeInTheDocument();
    // Readiness rows.
    expect(screen.getByText(/owner bootstrapped/i)).toBeInTheDocument();
    // Missing config.
    expect(screen.getByText(/No model profile is selected/i)).toBeInTheDocument();
    // Provider health (config-derived, not probed).
    expect(screen.getByText("raiker-local-llama-cpp")).toBeInTheDocument();
    expect(screen.getByText(/not probed from the browser/i)).toBeInTheDocument();
    // Disabled capabilities.
    expect(screen.getByText("shell_execution")).toBeInTheDocument();
  });
});
