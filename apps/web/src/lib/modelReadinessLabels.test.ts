import { describe, expect, it } from "vitest";
import type { ModelProfile } from "./apiTypes";
import { readinessLabel, setupChoiceLabel } from "./modelReadinessLabels";

function profile(overrides: Partial<ModelProfile> = {}): ModelProfile {
  return {
    profile_id: "p",
    provider: "anthropic",
    model: "<model>",
    default_state: "available",
    local_only: false,
    requires_network: true,
    endpoint_kind: "hosted",
    requires_egress_policy: true,
    requires_budget_policy: false,
    runtime_gate: null,
    off_machine: true,
    selected: false,
    prompt_cache_ttl: null,
    ...overrides,
  } as ModelProfile;
}

describe("readinessLabel", () => {
  it("names each measured state", () => {
    expect(readinessLabel("ready")).toBe("Ready");
    expect(readinessLabel("unreachable")).toBe("Unreachable");
    expect(readinessLabel("authentication_failed")).toBe("Key rejected");
    expect(readinessLabel("quota_exhausted")).toBe("No credit");
    // Aged out, not broken: the server re-takes the check before the turn.
    expect(readinessLabel("stale")).toBe("Re-checks on use");
  });

  it("returns null when the backend sent no state, rather than inventing one", () => {
    expect(readinessLabel(undefined)).toBeNull();
  });
});

describe("setupChoiceLabel", () => {
  // BUG-198 — the wizard rendered `configured` ("this profile names a concrete
  // model string") as "Connected". Five shipped registry profiles carry
  // placeholder model names, so on a host with no llama.cpp binary and no Ollama
  // process the first screen an owner ever sees called them all connected.
  it("never claims a local backend is connected just because it names a model", () => {
    const llama = profile({
      profile_id: "raiker-local-llama-cpp",
      provider: "llama_cpp",
      model: "local-gguf",
      configured: true,
      readiness_state: "not_configured",
      ready: false,
    });
    expect(setupChoiceLabel(llama)).toBe("Not checked yet");
    expect(setupChoiceLabel(llama)).not.toContain("Connected");
  });

  it("says a model must be chosen before anything can be checked", () => {
    expect(setupChoiceLabel(profile({ model: "<model>", configured: false }))).toBe(
      "Choose a model first",
    );
  });

  it("claims readiness only for a backend a check actually passed", () => {
    expect(
      setupChoiceLabel(
        profile({ model: "claude-haiku-4-5-20251001", ready: true, readiness_state: "ready" }),
      ),
    ).toBe("Ready");
  });

  it("names the measured failure rather than flattening it to unconfigured", () => {
    expect(
      setupChoiceLabel(profile({ model: "gpt-4o-mini", readiness_state: "unreachable" })),
    ).toBe("Unreachable");
    expect(
      setupChoiceLabel(profile({ model: "gpt-4o-mini", readiness_state: "quota_exhausted" })),
    ).toBe("No credit");
  });

  it("does not let a stored credential stand in for a reachable provider", () => {
    const stored = profile({
      model: "openai/gpt-4o-mini",
      configured: true,
      connection_configured: true,
      readiness_state: "not_configured",
      ready: false,
    });
    expect(setupChoiceLabel(stored)).toBe("Not checked yet");
  });
});
