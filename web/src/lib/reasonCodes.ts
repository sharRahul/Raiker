// Plain-English copy for backend machine reason_codes. The authority router's are
// the `AuthorityReason` catalogue (raiker/runtime/authority/reason_codes.py), and
// tests/test_reason_code_catalogue.py fails when a catalogue code has no copy here
// or a key here names a code the backend never sends.
// Never hide an unknown code — fall back to the raw code plus a generic explanation.

interface ReasonCopy {
  plain: string;
  remediation: string;
}

const REASON_CODES: Record<string, ReasonCopy> = {
  // BUG-285 — the refusals a *turn* can meet before its stream opens, said as
  // the scope decision that refused it — never as a status number or "could not
  // reach the runtime", which sends an owner to check a service that is up.
  chat_has_no_project_scope: {
    plain: "This conversation is not filed under a project, so it cannot use one's files.",
    remediation: "Choose a project in the composer, or ask without one.",
  },
  build_requires_project: {
    plain: "Build works inside a project, and this turn named none.",
    remediation: "Choose a project in the composer before sending.",
  },
  build_project_not_found: {
    plain: "The project this turn named is not one you have.",
    remediation: "Choose a project that exists in the composer.",
  },
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
  only_runtime_gate_manager_can_manage_gates: {
    plain: "Only a runtime gate manager can change runtime modes and gates.",
    remediation: "Sign in as the owner, who holds that role.",
  },
  only_runtime_gate_manager_can_enable_gates: {
    plain: "Only a runtime gate manager can turn a capability on.",
    remediation: "Sign in as the owner, who holds that role.",
  },
  // Standing grants (router.py).
  grant_target_is_critical: {
    plain: "A critical action can't be allowed ahead of time.",
    remediation: "It is approved one action at a time, every time.",
  },
  only_human_may_revoke_grant: {
    plain: "Only a person can withdraw a standing permission.",
    remediation: "Sign in as the owner to revoke it.",
  },
  grant_not_found_or_already_revoked: {
    plain: "That permission is already gone.",
    remediation: "Nothing to revoke; refresh to see the current list.",
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
  // Project organisation (dashboard.create_project). Organising refusals, not
  // authority ones — and the two an owner actually meets.
  duplicate_project_name: {
    plain: "A project already has that name.",
    remediation: "Choose a different name, or open the one that exists.",
  },
  duplicate_project_root: {
    plain: "That folder is already attached to a project.",
    remediation: "Open the project that holds it, or choose another folder.",
  },
  // UX-PROJ-05/06/07 — the project lifecycle's refusals, each naming the
  // destination or step that was wrong.
  project_move_into_itself: {
    plain: "A project cannot be moved inside itself.",
    remediation: "Choose another folder, or Top level.",
  },
  project_move_into_descendant: {
    plain: "That folder is inside the project you are moving.",
    remediation: "Choose a folder outside this project, or Top level.",
  },
  project_move_into_archived: {
    plain: "That folder is archived.",
    remediation: "Restore it first, or choose another folder.",
  },
  project_parent_archived: {
    plain: "This project's parent folder is archived.",
    remediation: "Restore the parent first; this project comes back with it.",
  },
  project_delete_requires_step_up: {
    plain: "Deleting a project's folder needs your password again.",
    remediation: "Enter your password (or authenticator code) to confirm it is you.",
  },
  project_delete_confirmation_required: {
    plain: "The delete was not confirmed.",
    remediation: "Type the project's name to confirm.",
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
  invalid_decision_mode: {
    plain: "That decision mode isn't one Raiker has.",
    remediation: "Choose one of the modes the capability offers.",
  },
  decision_mode_requires_executor: {
    plain: "This capability has nothing that can run it yet, so it can't be allowed without asking.",
    remediation: "Keep it on Ask until it can run.",
  },
  execution_failed: {
    plain: "The executor failed.",
    remediation: "See the inner reason code.",
  },
  activation_blocked: {
    plain: "Activation is blocked.",
    remediation: "Satisfy the activation requirement first.",
  },
  // §13.2 item 6 — the page showed a value another tab or device has changed.
  capability_conflict: {
    plain: "This permission was changed somewhere else since this page loaded, so nothing was changed.",
    remediation: "The page now shows the current setting; choose again if you still want to change it.",
  },
  project_conflict: {
    plain: "This project was changed somewhere else since the page loaded, so nothing was changed.",
    remediation: "Close this and reopen the project to see where it is now.",
  },
  channel_conflict: {
    plain: "This channel was changed somewhere else since the page loaded, so nothing was changed.",
    remediation: "The page now shows its current settings; change it again if you still want to.",
  },
  mcp_server_conflict: {
    plain: "This MCP server was renamed somewhere else since the page loaded, so nothing was changed.",
    remediation: "The page now shows its current name; try again if you still want the change.",
  },
  mcp_tool_changed: {
    plain: "The server changed how it describes this tool since the page showed it, so nothing was accepted.",
    remediation: "Read what the server says now, then accept again if you still want it offered.",
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
