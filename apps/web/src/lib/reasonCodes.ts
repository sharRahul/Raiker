// Plain-English copy for backend machine reason_codes (transcribed from the runtime
// authority sources, e.g. raiker/runtime/authority/router.py and routes_prompts.py).
// Never hide an unknown code — fall back to the raw code plus a generic explanation.

interface ReasonCopy {
  plain: string;
  remediation: string;
}

const REASON_CODES: Record<string, ReasonCopy> = {
  // Principal / role / scope denials (router.py).
  principal_not_active: {
    plain: "Your account/principal is not active.",
    remediation: "A human owner must re-activate it.",
  },
  principal_expired: {
    plain: "Your principal has expired.",
    remediation: "Re-bootstrap or renew the principal.",
  },
  ai_cannot_approve_own_action: {
    plain: "An AI can't approve its own action.",
    remediation: "Another authorised human must approve.",
  },
  ai_cannot_grant_roles: {
    plain: "An AI can't grant/assign roles.",
    remediation: "A human owner must grant roles.",
  },
  ai_cannot_manage_runtime_gates: {
    plain: "An AI can't change runtime modes/gates.",
    remediation: "A human runtime_gate_manager must do this.",
  },
  ai_cannot_enable_runtime_gate: {
    plain: "An AI can't enable a runtime gate.",
    remediation: "A human runtime_gate_manager must do this.",
  },
  // Capability-gate / mode / transition denials (router.py).
  disabled_by_capability_gate: {
    plain: "This capability is turned off.",
    remediation: "Enable it on the Capabilities page (if supported).",
  },
  unknown_capability_gate: {
    plain: "This capability isn't recognised.",
    remediation: "No such gate; nothing to enable.",
  },
  // Policy / execution outcomes (route_action).
  denied_by_policy: {
    plain: "Policy blocked this action.",
    remediation: "See the policy reason; the UI can't override it.",
  },
  critical_action_requires_human_confirmation: {
    plain: "Critical action needs a human.",
    remediation: "A human must confirm; AI is blocked.",
  },
  approval_required: {
    plain: "This needs human approval first.",
    remediation: "Route to Approvals (resolution is metadata-only).",
  },
  risk_acceptance_required: {
    plain: "You must accept the risk first.",
    remediation: "Review and accept the risk in the action detail.",
  },
  "execution_unavailable:no_executor": {
    plain: "No runtime exists for this — it's deferred.",
    remediation: "Not available in the local single-user runtime.",
  },
  // Interrupt / STOP authority (routes_prompts.py).
  human_principal_required: {
    plain: "Only a human can stop tasks.",
    remediation: "Sign in as the human owner principal.",
  },
};

// Codes that carry a variable suffix after ":" (e.g. domain_scope_denied:{scope}).
const PREFIX_CODES: Record<string, ReasonCopy> = {
  cannot_assign_human_role_to_ai: {
    plain: "An AI principal can't hold a human-only role.",
    remediation: "Only a human can hold this role.",
  },
  domain_scope_denied: {
    plain: "This action's domain isn't in your granted scopes.",
    remediation: "Grant the domain scope to the principal.",
  },
  unknown_runtime_mode: {
    plain: "That runtime mode doesn't exist.",
    remediation: "Pick a valid mode.",
  },
  unknown_capability: {
    plain: "That capability doesn't exist.",
    remediation: "Pick a valid capability.",
  },
  invalid_target_state: {
    plain: "That target state isn't allowed.",
    remediation: "Choose an allowed transition.",
  },
  execution_failed: {
    plain: "The executor failed.",
    remediation: "See the inner reason code.",
  },
  activation_blocked: {
    plain: "Activation is blocked.",
    remediation: "Satisfy the activation requirement first.",
  },
};

/** Resolve a machine reason_code to plain-English copy, never hiding the raw code. */
export function explainReasonCode(code: string | null | undefined): {
  code: string;
  plain: string;
  remediation: string | null;
} | null {
  if (!code) return null;
  const exact = REASON_CODES[code];
  if (exact) return { code, plain: exact.plain, remediation: exact.remediation };
  const prefix = code.split(":", 1)[0];
  const known = PREFIX_CODES[prefix];
  if (known) return { code, plain: known.plain, remediation: known.remediation };
  // Unknown code: surface it raw plus a generic explanation.
  return {
    code,
    plain: `The runtime reported: ${code}.`,
    remediation: null,
  };
}
