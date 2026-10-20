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
  // GCR-46 — the one code in this table that is not about a provider at all.
  // The owner's chosen model is stored and could not be read back, so every
  // other message here would be a lie about a model nothing has judged. It is
  // included because the readiness refusal it produces arrives on the same
  // surface as the rest, and arriving there with no guidance is what made a
  // storage failure look like a model the owner had failed to set up.
  configured_model_store_unavailable: {
    message: "Raiker could not read which model you chose.",
    fix: "This is a storage failure in this workspace, not a problem with the model or your key. Your choice is still saved. Check the workspace database is readable, then try again.",
  },
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
  // *shape* is the problem: an identity-linked key acts inside one workspace,
  // and the provider will not accept it until the request names which.
  //
  // BUG-274 turned that into something the owner can act on. The old fix sent
  // them to fetch a different key, which is a dead end for an owner who has
  // only this one; the connection now carries a Workspace ID field, so the fix
  // is a value they already have rather than a credential they may not.
  provider_workspace_required: {
    message: "This key is identity-linked, so it acts inside one workspace.",
    fix: "Add the workspace ID to this connection — it is beside the key in the provider's console — then connect again. The key you pasted is fine.",
  },
  // BUG-274 — the other half. A workspace *is* named and the provider refused
  // it, so repeating the message above would ask for something already given.
  provider_workspace_invalid: {
    message: "The provider did not recognise the workspace named with this key.",
    fix: "Check the workspace ID on this connection against the one in the provider's console, then connect again.",
  },
  // The key is valid and the provider will not run this model for Raiker:
  // OpenRouter offers some models only to apps on its own list. Sending the
  // owner to rotate a working key was the defect.
  provider_model_refused: {
    message: "The provider accepted your key but will not run this model for Raiker.",
    fix: "Some models are offered only to apps on the provider's own list. Choose another model — your key is fine.",
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
  // Connection-bound authorization: an off-machine model is reached only
  // through a connection the owner saved for it, and only at that
  // connection's own address. These are policy answers, not connection faults.
  model_connection_required: {
    message: "This provider is off this machine and has no saved connection, so Raiker will not reach it.",
    fix: "Connect it on the Models page. Saving the connection is what authorizes its address.",
  },
  model_connection_origin_mismatch: {
    message: "The address this request would use is not the one the saved connection was authorized for.",
    fix: "Reconnect the provider with the address you want Raiker to use.",
  },
  // BUG-349 (D5) — the transport refused to attach a key to a request for an
  // origin other than the connection's. Only an adapter bug reaches this.
  model_credential_origin_mismatch: {
    message: "Raiker refused to send this provider's key to an address other than the connection's own.",
    fix: "This should not happen. Reconnect the provider, and report it if it repeats.",
  },
  model_connection_origin_unbound: {
    message: "The saved connection does not name an address, and this profile has none of its own.",
    fix: "Reconnect the provider and enter its endpoint.",
  },
  endpoint_userinfo_rejected: {
    message: "An endpoint containing a username or password is never used.",
    fix: "Remove the user name and password from the address and paste the key into the key field instead.",
  },
  endpoint_ambiguous_host: {
    message: "That address can be read as more than one host, so Raiker will not use it.",
    fix: "Write the host as a name or a plain dotted IPv4 address, for example 192.168.1.20.",
  },
  environment_credential_unavailable: {
    message: "The environment variable for this provider's key is not set in Raiker's environment.",
    fix: "Paste the key instead, or set the variable and restart raiker-web.",
  },
  environment_credential_with_pasted_key: {
    message: "Choose one: a pasted key, or the key from the environment.",
    fix: "Clear the key field, or untick “Use the key from the environment”.",
  },
};

/**
 * BUG-349 — the dial guard's refusals, by detail. Each is a policy answer
 * about the address a name resolved to, so none of them sends the owner to
 * check their network or open a gate: the gate is open, and the address is
 * the problem.
 */
const DIAL_REFUSALS: Record<string, Omit<ProviderErrorGuidance, "code">> = {
  non_public_address: {
    message:
      "Raiker refused to connect: this hosted provider's name resolved to a private, loopback or link-local address.",
    fix: "A hosted connection only reaches public addresses. This is a policy refusal, not a network fault — check the endpoint and your DNS.",
  },
  public_address_for_private: {
    message: "Raiker refused to connect: this home-lab endpoint's name now resolves to a public internet address.",
    fix: "Check the name. If the server really is on the internet, connect it as a hosted provider over https://.",
  },
  loopback_for_private: {
    message: "Raiker refused to connect: this home-lab endpoint's name resolves to this machine.",
    fix: "Reconnect it as http://localhost:<port> — a server on this machine is a local endpoint.",
  },
  link_local_address: {
    message: "Raiker refused to connect: this endpoint is a link-local address (169.254.x.x or fe80::).",
    fix: "If it is a server you own on a direct cable, reconnect it with “Allow a link-local address” ticked.",
  },
  metadata_address: {
    message: "Raiker refused to connect: that address is a cloud metadata service.",
    fix: "A metadata service is never a model destination, so there is no setting for this. Use your model server's own address.",
  },
  credential_over_http_proxy: {
    message: "Raiker refused to send the key: this plain-HTTP endpoint would go through your proxy, which could read it.",
    fix: "Use an https:// endpoint, or exclude the host from the proxy with NO_PROXY and restart raiker-web.",
  },
};

/** `model_dial_refused:<detail>`. */
function dialRefusalGuidance(code: string): Omit<ProviderErrorGuidance, "code"> {
  const detail = code.slice("model_dial_refused:".length);
  return (
    DIAL_REFUSALS[detail] ?? {
      message: "Raiker refused to connect: the address this provider's name resolved to is not one its connection allows.",
      fix: "This is a policy refusal, not a network fault. Check the endpoint on this card.",
    }
  );
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
  if (reasonCode === "model_dial_refused" || reasonCode.startsWith("model_dial_refused:"))
    return { ...dialRefusalGuidance(reasonCode), code: reasonCode };
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

/**
 * BUG-289 — the last-resort sentence, split by where the destination is.
 *
 * This branch is reached only when the runtime has *no* classified reason: a
 * proxy answering `connect_rejected` is genuinely unclassified, and
 * [BUG-272] is why anything classifiable no longer lands here. What was wrong
 * was not the diagnosis but the advice. "Check that it is running" was written
 * for a local runtime — a thing the owner can start on their own machine — and
 * it was also being handed to somebody whose host cannot reach `openrouter.ai`,
 * about a service they do not operate and cannot start.
 *
 * Neither sentence guesses at a cause. The point of this branch is that there
 * is not one; what differs is which remedies are available to the owner at all.
 */
export function unreachableProviderNote(
  providerName: string,
  offMachine: boolean,
): string {
  return offMachine
    ? `${providerName} could not be reached. Check this device's network access, ` +
        "and any proxy or firewall between it and the provider."
    : `${providerName} could not be reached. Check that it is running and reachable from this device.`;
}
