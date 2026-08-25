import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import type { ModelProfile } from "../apiTypes";
import { resetModelSetup, setupDialog } from "../modelReadiness.svelte";
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
  it("dismisses with Escape and restores focus to the model trigger", async () => {
    render(ModelPicker, {
      profiles,
      selectedProfile: profiles[0],
      value: profiles[0].profile_id,
    });
    const trigger = screen.getByRole("button", { name: /model for this turn/i });
    await fireEvent.click(trigger);
    const menu = screen.getByRole("menu", { name: /model/i });
    screen.getByRole("menuitemradio", { name: /Sonnet 4.5/i }).focus();

    await fireEvent.keyDown(menu, { key: "Escape" });

    expect(screen.queryByRole("menu", { name: /model/i })).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("groups models under a logo-and-name provider heading", async () => {
    render(ModelPicker, {
      profiles,
      selectedProfile: profiles[0],
      value: profiles[0].profile_id,
    });

    await fireEvent.click(
      screen.getByRole("button", { name: /model for this turn/i }),
    );

    const anthropic = screen.getByRole("group", { name: "Anthropic models" });
    expect(anthropic).toHaveTextContent("Anthropic");
    expect(anthropic).toHaveTextContent("Haiku 4.5");
    expect(anthropic).toHaveTextContent("Sonnet 4.5");
    expect(
      screen.getByRole("group", { name: "OpenAI models" }),
    ).toHaveTextContent("GPT-4o Mini");
  });

  it("distinguishes two configured models on the same provider profile", async () => {
    const sameProvider = [
      {
        ...profiles[0],
        profile_id: "anthropic-hosted",
        model: "claude-haiku-4-5-20251001",
      },
      {
        ...profiles[1],
        profile_id: "anthropic-hosted",
        model: "claude-sonnet-4-5-20250929",
      },
    ];
    render(ModelPicker, {
      profiles: sameProvider,
      selectedProfile: sameProvider[0],
      profileId: "anthropic-hosted",
      model: "claude-haiku-4-5-20251001",
    });

    await fireEvent.click(
      screen.getByRole("button", { name: /model for this turn/i }),
    );
    await fireEvent.click(
      screen.getByRole("menuitemradio", { name: /Sonnet 4.5/i }),
    );

    expect(
      screen.getByRole("button", { name: /model for this turn: Sonnet 4.5/i }),
    ).toBeInTheDocument();
  });

  it("keeps an unready model out of selection and opens its repair action", async () => {
    resetModelSetup();
    const ready: ModelProfile = {
      ...profiles[0],
      ready: true,
      readiness_state: "ready",
    };
    const stopped: ModelProfile = {
      ...profiles[2],
      provider: "ollama",
      ready: false,
      readiness_state: "runtime_stopped",
      readiness_summary: "Ollama is not reachable.",
      readiness_reason_code: "local_runtime_unreachable",
      readiness_remediation: "Start Ollama, then check again.",
    };
    render(ModelPicker, {
      profiles: [ready, stopped],
      selectedProfile: ready,
      profileId: ready.profile_id,
      model: ready.model,
    });

    await fireEvent.click(
      screen.getByRole("button", { name: /model for this turn/i }),
    );

    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.getByText("Needs setup")).toBeInTheDocument();
    expect(
      screen.queryByRole("menuitemradio", { name: /GPT-4o Mini/i }),
    ).not.toBeInTheDocument();
    await fireEvent.click(
      screen.getByRole("button", { name: "Set up Ollama for GPT-4o Mini" }),
    );
    expect(setupDialog.open).toBe(true);
    expect(setupDialog.profile?.profile_id).toBe(stopped.profile_id);
    expect(
      screen.getByRole("button", { name: /model for this turn: Haiku 4.5/i }),
    ).toBeInTheDocument();
  });
});
