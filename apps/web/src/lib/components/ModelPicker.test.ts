import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import type { ModelProfile } from "../apiTypes";
import ModelPicker from "./ModelPicker.svelte";

const profiles: ModelProfile[] = [
  {
    profile_id: "anthropic-haiku",
    provider: "anthropic",
    model: "claude-haiku-4-5-20251001",
    default_state: "enabled",
    local_only: false,
    requires_network: true,
    endpoint_kind: "remote_hosted",
    requires_egress_policy: true,
    requires_budget_policy: true,
    runtime_gate: "hosted_model_runtime",
    off_machine: true,
    selected: true,
    prompt_cache_ttl: null,
  },
  {
    profile_id: "anthropic-sonnet",
    provider: "anthropic",
    model: "claude-sonnet-4-5-20250929",
    default_state: "enabled",
    local_only: false,
    requires_network: true,
    endpoint_kind: "remote_hosted",
    requires_egress_policy: true,
    requires_budget_policy: true,
    runtime_gate: "hosted_model_runtime",
    off_machine: true,
    selected: false,
    prompt_cache_ttl: null,
  },
  {
    profile_id: "openai-gpt",
    provider: "openai",
    model: "gpt-4o-mini",
    default_state: "enabled",
    local_only: false,
    requires_network: true,
    endpoint_kind: "remote_hosted",
    requires_egress_policy: true,
    requires_budget_policy: true,
    runtime_gate: "hosted_model_runtime",
    off_machine: true,
    selected: false,
    prompt_cache_ttl: null,
  },
];

describe("ModelPicker", () => {
  it("groups models under a logo-and-name provider heading", async () => {
    render(ModelPicker, { profiles, selectedProfile: profiles[0], value: profiles[0].profile_id });

    await fireEvent.click(screen.getByRole("button", { name: /model for this turn/i }));

    const anthropic = screen.getByRole("group", { name: "Anthropic models" });
    expect(anthropic).toHaveTextContent("Anthropic");
    expect(anthropic).toHaveTextContent("Haiku 4.5");
    expect(anthropic).toHaveTextContent("Sonnet 4.5");
    expect(screen.getByRole("group", { name: "OpenAI models" })).toHaveTextContent("GPT-4o Mini");
  });
});
