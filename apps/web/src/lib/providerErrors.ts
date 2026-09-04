/**
 * Plain-language remediation for the governed reason codes the model routes
 * return.
 *
 * Every one of these is a *fail-closed policy outcome*, not a fault: the runtime
 * refuses a hosted or private-network provider until the owner has explicitly
 * opened each gate. The codes themselves are the audit vocabulary and must not
 * change, but showing a bare `provider_requires_explicit_policy_approval` to the
 * person trying to paste an API key tells them nothing about what to do next.
 * This maps each code to the exact control that unblocks it.
 */

export interface ProviderErrorGuidance {
  /** One sentence stating what the runtime refused, in the owner's language. */
  message: string;
  /** The concrete next step. */
  fix: string;
  /** In-app destination that performs `fix`, when one exists. */
  href?: string;
  /** Label for `href`. */
  linkLabel?: string;
  /** The raw governed reason code, kept visible for audit correlation. */
  code?: string;
}

const GUIDANCE: Record<string, Omit<ProviderErrorGuidance, "code">> = {
  provider_requires_explicit_policy_approval: {
    message: "This provider stays off until you open its runtime gate.",
    fix: "Open Permissions, find “Hosted models” (or “Home-lab models” for a private-network endpoint), expand it and choose Turn on. It asks for a reason, a confirmation token — any phrase you type, it records your intent — and a threat-model acknowledgement.",
    href: "#/capabilities",
    linkLabel: "Open Permissions",
  },
  hosted_provider_requires_explicit_policy: {
    message: "Hosted model access is not enabled for your account.",
    fix: "Open Permissions and turn on “Hosted models”.",
    href: "#/capabilities",
    linkLabel: "Open Permissions",
  },
  private_network_provider_requires_explicit_policy: {
    message: "Private-network model access is not enabled for your account.",
    fix: "Open Permissions and turn on “Home-lab models”.",
    href: "#/capabilities",
    linkLabel: "Open Permissions",
  },
  // BUG-272 — the credential is valid and there is nothing to rotate. Its
  // *shape* is the problem: an identity-linked key needs a workspace named on
  // every request, and Raiker's provider calls do not carry one.
  provider_workspace_required: {
    message: "This key is identity-linked, so the provider wants a workspace named with it.",
    fix: "Use a standard API key from the provider's console, or one scoped to a single workspace, then connect again. The key you pasted is not broken — it is the wrong kind for this call.",
  },
  connector_vault_key_unset: {
    message: "There is no vault key, so Raiker cannot encrypt the credential you just entered.",
    fix: "Open Settings → Security & Login, select Generate key, confirm your password and save. Then connect the provider again.",
    href: "#/settings",
    linkLabel: "Open Settings",
  },
  connector_vault_key_invalid: {
    message: "The stored vault key is not a valid Fernet key, so credentials cannot be encrypted.",
    fix: "Open Settings → Security & Login and replace it using Generate key.",
    href: "#/settings",
    linkLabel: "Open Settings",
  },
  test_provider_not_available: {
    message: "Raiker ships no built-in test or mock model provider.",
    fix: "Choose a real local, home-lab, or hosted provider instead.",
  },
  test_only_profile_not_runnable: {
    message: "This profile exists for tests only and is never runnable.",
    fix: "Choose a real local, home-lab, or hosted provider instead.",
  },
  model_name_not_configured: {
    message: "No model is pinned on this profile yet.",
    fix: "Use “Choose model…” on this card and pick or type a model id first.",
  },
  hosted_api_key_missing: {
    message: "A hosted provider needs an API key before Raiker will talk to it.",
    fix: "Paste the provider's key into this dialog.",
  },
  openrouter_api_key_missing: {
    message: "OpenRouter needs an API key before Raiker will talk to it.",
    fix: "Paste your OpenRouter key into this dialog.",
  },
  openrouter_requires_https: {
    message: "OpenRouter is only reachable over HTTPS.",
    fix: "Remove the custom endpoint, or replace it with an https:// URL.",
  },
};

/** `model_egress_denied:<host>` / `model_egress_denied:no_allowlist`. */
function egressGuidance(code: string): Omit<ProviderErrorGuidance, "code"> {
  const detail = code.slice("model_egress_denied:".length);
  const host = detail === "no_allowlist" || detail === "missing_host" ? null : detail;
  return {
    message:
      host === null
        ? "No model endpoint is on the owner egress allowlist, so every off-machine provider fails closed."
        : `${host} is not on the owner egress allowlist, so Raiker refused to reach it.`,
    // The allowlist is process configuration on purpose: it is the last boundary
    // before bytes leave the machine, so it is deliberately not editable from a
    // browser session. Say so plainly rather than implying an in-app control.
    fix: `Restart raiker-web with RAIKER_MODEL_EGRESS_ALLOWLIST set to the hosts you allow, for example RAIKER_MODEL_EGRESS_ALLOWLIST=${host ?? "api.anthropic.com"}. It is process configuration by design and cannot be changed from this browser session.`,
  };
}

/** `missing_endpoint_env:VAR`. */
function endpointEnvGuidance(code: string): Omit<ProviderErrorGuidance, "code"> {
  const variable = code.slice("missing_endpoint_env:".length);
  return {
    message: `This profile reads its endpoint from ${variable}, which is unset.`,
    fix: `Set ${variable} before starting raiker-web, or use “Advanced: custom endpoint” in this dialog.`,
  };
}

/** `provider_api_key_missing:VAR`. */
function apiKeyEnvGuidance(code: string): Omit<ProviderErrorGuidance, "code"> {
  const variable = code.slice("provider_api_key_missing:".length);
  return {
    message: "This provider requires an API key.",
    fix: `Paste the key into this dialog, or set ${variable} before starting raiker-web.`,
  };
}

/**
 * Guidance for one governed reason code, or `null` when the code is unknown —
 * callers must fall back to the raw status so nothing is ever silently swallowed.
 */
export function providerErrorGuidance(
  reasonCode: string | null | undefined,
): ProviderErrorGuidance | null {
  if (!reasonCode) return null;
  // A provider code may carry a `:http_400` detail. The family is what has
  // guidance; the detail is for the audit trail, and stripping it here is what
  // stops a status suffix turning a known code into an unknown one.
  const family = reasonCode.split(":", 1)[0];
  if (GUIDANCE[family] !== undefined && GUIDANCE[reasonCode] === undefined)
    return { ...GUIDANCE[family], code: reasonCode };
  if (reasonCode.startsWith("model_egress_denied:"))
    return { ...egressGuidance(reasonCode), code: reasonCode };
  if (reasonCode.startsWith("missing_endpoint_env:"))
    return { ...endpointEnvGuidance(reasonCode), code: reasonCode };
  if (reasonCode.startsWith("provider_api_key_missing:"))
    return { ...apiKeyEnvGuidance(reasonCode), code: reasonCode };
  if (reasonCode === "missing_endpoint")
    return {
      message: "This profile has no endpoint configured.",
      fix: "Use “Advanced: custom endpoint” in this dialog to supply one.",
      code: reasonCode,
    };
  const known = GUIDANCE[reasonCode];
  return known ? { ...known, code: reasonCode } : null;
}
