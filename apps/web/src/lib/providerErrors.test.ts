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

// BUG-272 — found on a live round: a valid, identity-linked key was refused with
// HTTP 400 and reported as `provider_http_error:http_400`, then rendered as
// "could not be reached". Both send the owner to debug the wrong thing — the
// same shape FIXED-355 removed from a rejected key.
describe("an identity-linked key", () => {
  it("says the key is the wrong kind rather than telling you to rotate it", () => {
    const guidance = providerErrorGuidance("provider_workspace_required");
    expect(guidance).not.toBeNull();
    expect(guidance?.message).toMatch(/identity-linked/i);
    expect(guidance?.fix).toMatch(/not broken/i);
  });

  it("matches through the status detail the provider code carries", () => {
    // The code arrives as `provider_workspace_required:http_400`; the suffix is
    // for the audit trail and must not turn a known code into an unknown one.
    const guidance = providerErrorGuidance("provider_workspace_required:http_400");
    expect(guidance?.message).toMatch(/identity-linked/i);
    // The exact code is kept for correlation, detail and all.
    expect(guidance?.code).toBe("provider_workspace_required:http_400");
  });

  it("still returns null for a code nothing knows about", () => {
    // Callers fall back to the raw status, so nothing is silently swallowed.
    expect(providerErrorGuidance("provider_http_error:http_418")).toBeNull();
  });
});
