import { render, screen } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";

const models = vi.fn();

vi.mock("./api", () => ({
  api: {
    models: () => models(),
  },
  ApiError: class ApiError extends Error {
    constructor(readonly status: number) {
      super("err");
    }
  },
}));

const DATA = {
  profiles: [
    {
      profile_id: "raiker-local-llama-cpp",
      provider: "llama.cpp",
      model: "local-gguf",
      default_state: "disabled_until_provider_detected",
      local_only: true,
      requires_network: false,
      endpoint_kind: "local_machine",
      requires_egress_policy: false,
      requires_budget_policy: false,
      runtime_gate: null,
      off_machine: false,
      selected: true,
    },
    {
      profile_id: "openai-hosted",
      provider: "openai",
      model: "<model>",
      default_state: "disabled_until_policy_approved",
      local_only: false,
      requires_network: true,
      endpoint_kind: "remote_hosted",
      requires_egress_policy: true,
      requires_budget_policy: true,
      runtime_gate: "hosted_model_runtime",
      off_machine: true,
      selected: false,
    },
  ],
  current_profile_id: "raiker-local-llama-cpp",
  hosted_model_gate_state: "disabled",
  private_network_model_gate_state: "disabled",
  model_egress_allowlist_configured: false,
  remote_profile_count: 1,
  no_silent_hosted_fallback: true,
};

describe("ModelsView", () => {
  beforeEach(() => {
    models.mockReset().mockResolvedValue(DATA);
  });

  it("renders hosted runtime gate and egress posture without exposing allowlist values", async () => {
    const { default: ModelsView } = await import("./ModelsView.svelte");
    render(ModelsView);

    expect(await screen.findByText(/Model Runtime Gates/i)).toBeInTheDocument();
    expect(screen.getAllByText(/disabled \(fail-closed\)/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/not configured/i)).toBeInTheDocument();
    expect(screen.getByText("openai-hosted")).toBeInTheDocument();
    expect(screen.getByText(/gate: hosted_model_runtime/i)).toBeInTheDocument();
    expect(screen.getByText(/egress policy/i)).toBeInTheDocument();
    expect(screen.queryByText(/api\.openai\.com/i)).not.toBeInTheDocument();
  });
});
