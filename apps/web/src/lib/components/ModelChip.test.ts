import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import type { ModelProfile, ModelsView } from "../apiTypes";
import ModelChip from "./ModelChip.svelte";

function makeProfile(partial: Partial<ModelProfile>): ModelProfile {
  return {
    profile_id: "local-gguf",
    provider: "llama.cpp",
    model: "qwen2.5-7b-instruct",
    default_state: "enabled",
    local_only: true,
    requires_network: false,
    endpoint_kind: "local_process",
    requires_egress_policy: false,
    requires_budget_policy: false,
    runtime_gate: null,
    off_machine: false,
    selected: false,
    prompt_cache_ttl: null,
    ...partial,
  };
}

function makeModels(partial: Partial<ModelsView>): ModelsView {
  return {
    profiles: [],
    current_profile_id: null,
    hosted_model_gate_state: "enabled_runtime",
    private_network_model_gate_state: "enabled_runtime",
    model_egress_allowlist_configured: false,
    remote_profile_count: 0,
    fallback_sequence: [],
    no_silent_hosted_fallback: true,
    ...partial,
  };
}

describe("ModelChip", () => {
  it("renders nothing before the models view has loaded", () => {
    render(ModelChip, { models: null });
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("offers the Models view when no profile is selected", () => {
    render(ModelChip, { models: makeModels({}) });
    const link = screen.getByRole("link", { name: /no model selected/i });
    expect(link).toHaveAttribute("href", "#/models");
  });

  it("shows a local chip for an on-machine profile", () => {
    const models = makeModels({
      profiles: [makeProfile({ selected: true })],
      current_profile_id: "local-gguf",
    });
    render(ModelChip, { models });
    const link = screen.getByRole("link", { name: /local · llama\.cpp/i });
    expect(link).toHaveAttribute("href", "#/models");
    // The tooltip carries the profile, model, and endpoint class verbatim.
    expect(link).toHaveAttribute("title", "local-gguf · qwen2.5-7b-instruct · local_process");
  });

  it("shows a hosted chip with honest egress state", () => {
    const hosted = makeProfile({
      profile_id: "anthropic-hosted",
      provider: "anthropic",
      model: "claude",
      local_only: false,
      requires_network: true,
      endpoint_kind: "remote_hosted",
      off_machine: true,
      selected: true,
    });
    const closed = makeModels({ profiles: [hosted], current_profile_id: "anthropic-hosted" });
    const { unmount } = render(ModelChip, { models: closed });
    expect(screen.getByRole("link", { name: /hosted · anthropic/i })).toHaveTextContent(
      "egress closed",
    );
    unmount();

    const open = makeModels({
      profiles: [hosted],
      current_profile_id: "anthropic-hosted",
      model_egress_allowlist_configured: true,
    });
    render(ModelChip, { models: open });
    expect(screen.getByRole("link", { name: /hosted · anthropic/i })).toHaveTextContent(
      "egress open",
    );
  });

  it("falls back to current_profile_id when no profile is flagged selected", () => {
    const models = makeModels({
      profiles: [makeProfile({})],
      current_profile_id: "local-gguf",
    });
    render(ModelChip, { models });
    expect(screen.getByRole("link", { name: /local · llama\.cpp/i })).toBeInTheDocument();
  });
});
