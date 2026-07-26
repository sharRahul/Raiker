import { describe, expect, it } from "vitest";
import { providerErrorGuidance } from "./providerErrors";

describe("providerErrorGuidance", () => {
  it("turns the policy-approval refusal into the Permissions control that unblocks it", () => {
    const guidance = providerErrorGuidance("provider_requires_explicit_policy_approval");
    expect(guidance).not.toBeNull();
    expect(guidance?.href).toBe("#/capabilities");
    expect(guidance?.fix).toMatch(/Hosted models/);
    // The audit vocabulary stays visible next to the plain-language remediation.
    expect(guidance?.code).toBe("provider_requires_explicit_policy_approval");
  });

  it("names the refused host and the exact env var for an egress denial", () => {
    const guidance = providerErrorGuidance("model_egress_denied:api.anthropic.com");
    expect(guidance?.message).toMatch(/api\.anthropic\.com/);
    expect(guidance?.fix).toMatch(/RAIKER_MODEL_EGRESS_ALLOWLIST=api\.anthropic\.com/);
    // The allowlist is process configuration; the dialog must not imply a control it lacks.
    expect(guidance?.href).toBeUndefined();
  });

  it("explains an empty egress allowlist without inventing a host", () => {
    const guidance = providerErrorGuidance("model_egress_denied:no_allowlist");
    expect(guidance?.message).toMatch(/allowlist/);
    expect(guidance?.message).not.toMatch(/no_allowlist/);
  });

  it("routes a missing vault key to Settings", () => {
    expect(providerErrorGuidance("connector_vault_key_unset")?.href).toBe("#/settings");
  });

  it("names the env var in a missing-endpoint-env code", () => {
    expect(providerErrorGuidance("missing_endpoint_env:RAIKER_LLAMA_ENDPOINT")?.fix).toMatch(
      /RAIKER_LLAMA_ENDPOINT/,
    );
  });

  it("returns null for an unknown or absent code so the caller keeps the raw status", () => {
    expect(providerErrorGuidance("something_new_from_the_server")).toBeNull();
    expect(providerErrorGuidance(null)).toBeNull();
    expect(providerErrorGuidance(undefined)).toBeNull();
  });
});
