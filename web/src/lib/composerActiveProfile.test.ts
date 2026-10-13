/**
 * BUG-314 — a model reached by search is described as itself, not as the default.
 */
import { describe, expect, it } from "vitest";
import type { ModelProfile } from "./apiTypes";
import { activeComposerProfile, blocksSending, readinessForSelection } from "./modelReadiness.svelte";

const profile = (over: Partial<ModelProfile>): ModelProfile =>
  ({
    profile_id: "openrouter-policy-gated",
    provider: "openrouter",
    model: "openai/gpt-4o-mini",
    selected: false,
    connection_configured: true,
    ready: true,
    readiness_state: "ready",
    readiness_reason_code: "model_ready",
    context_window_tokens: 128_000,
    ...over,
  }) as ModelProfile;

const defaultModel = profile({ selected: true });

describe("the composer's active model", () => {
  it("is the quick-list entry when the bound pair is in it", () => {
    expect(activeComposerProfile([defaultModel], "openrouter-policy-gated", "openai/gpt-4o-mini")).toBe(
      defaultModel,
    );
  });

  it("is the default when nothing is bound", () => {
    expect(activeComposerProfile([defaultModel], "", "")).toBe(defaultModel);
  });

  it("is the searched model, unchecked and with no borrowed window, when it is not", () => {
    const active = activeComposerProfile(
      [defaultModel],
      "openrouter-policy-gated",
      "anthropic/claude-3.5-haiku",
    );
    expect(active?.model).toBe("anthropic/claude-3.5-haiku");
    expect(active?.provider).toBe("openrouter");
    expect(active?.ready).toBe(false);
    expect(active?.readiness_summary).toBe("Checked when you send.");
    expect(active?.context_window_tokens).toBeNull();
    // A connected provider's unchecked model does not block Send: the server
    // checks it before admitting the turn.
    expect(blocksSending(readinessForSelection(active))).toBe(false);
  });

  it("finds a provider outside the quick list in the registry", () => {
    const anthropic = profile({
      profile_id: "anthropic-hosted",
      provider: "anthropic",
      model: "claude-haiku-4-5",
      selected: false,
    });
    const active = activeComposerProfile([defaultModel], "anthropic-hosted", "claude-opus-4-1", [
      defaultModel,
      anthropic,
    ]);
    expect(active?.provider).toBe("anthropic");
    expect(active?.model).toBe("claude-opus-4-1");
  });
});
