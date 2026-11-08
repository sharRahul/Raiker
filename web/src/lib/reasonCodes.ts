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

  // UX-4 (beta plan) — every literal refusal an API route sends has copy here
  // or beside the control that meets it; tests/test_route_reason_copy.py fails
  // when a route adds one without it.
  // Approvals and questions.
  approval_not_found: { plain: "This approval no longer exists.", remediation: "Reopen Approvals to see what is still waiting." },
  approval_is_a_question: { plain: "This item is a question, not an approval.", remediation: "Answer it with one of its options." },
  approval_is_not_a_question: { plain: "This item is an approval, not a question.", remediation: "Approve or reject it instead." },
  not_a_critical_approval: { plain: "This approval does not need the extra confirmation step.", remediation: "Approve or reject it as usual." },
  unknown_question: { plain: "That question is no longer waiting for an answer.", remediation: "Reopen Approvals to see what is still waiting." },
  unknown_option: { plain: "That answer is not one of the question's options.", remediation: "Choose one of the options shown." },
  single_select_question: { plain: "This question takes one answer.", remediation: "Choose a single option." },
  no_answer_given: { plain: "No answer was chosen.", remediation: "Choose or type an answer, then send it." },
  answer_too_long: { plain: "The answer is longer than the question allows.", remediation: "Shorten it and send it again." },
  action_has_no_hunks: { plain: "This change has no parts that can be chosen one by one.", remediation: "Approve or reject the whole change." },
  hunk_selection_requires_approval: { plain: "Choosing parts of a change is only possible while it waits for approval.", remediation: "Reopen the approval and choose again." },
  no_hunk_accepted: { plain: "No part of the change was selected.", remediation: "Select at least one part, or reject the change." },
  suspended_turn_produced_no_events: { plain: "The paused turn did not continue after the decision.", remediation: "Open the conversation and send the request again." },
  connector_intent_already_consumed: { plain: "This connector action was already carried out once.", remediation: "Check the connection's activity before asking again." },
  connector_intent_principal_mismatch: { plain: "This connector action belongs to a different account.", remediation: "Approve it from the account that asked for it." },
  // Messaging channels.
  channel_approval_relay_already_resolved: { plain: "This approval was already decided.", remediation: "Nothing more is needed." },
  channel_approval_relay_mismatch: { plain: "The reply does not match the approval it answers.", remediation: "Decide it in Raiker's Approvals page." },
  channel_approval_relay_not_enabled: { plain: "Approving from this channel is turned off.", remediation: "Decide it in Raiker, or turn on approvals for the channel." },
  channel_inbound_disabled: { plain: "Messages from this channel are turned off.", remediation: "Turn on incoming messages in the channel's settings." },
  channel_signature_expired: { plain: "The channel's message was signed too long ago to trust.", remediation: "Send the message again." },
  channel_signature_invalid: { plain: "The channel's message signature did not verify.", remediation: "Check the channel's signing secret." },
  channel_signature_required: { plain: "The channel's message was not signed.", remediation: "Set the signing secret on both sides." },
  invalid_channel_secret: { plain: "The channel secret is not valid.", remediation: "Copy the secret again and save it." },
  connector_write_requires_local_approval: { plain: "A change through a connection can only be approved in Raiker itself.", remediation: "Open Approvals in Raiker to decide it." },
  critical_approval_requires_local_step_up: { plain: "This approval needs confirmation on this computer.", remediation: "Open Approvals in Raiker and confirm it there." },
  principal_not_resolved: { plain: "Raiker could not tell which account sent this.", remediation: "Link the channel to your account again." },
  // Sign-in and scope.
  login_required: { plain: "You are signed out.", remediation: "Sign in again." },
  scope_insufficient: { plain: "This sign-in is not allowed to do that.", remediation: "Sign in on this computer with full access." },
  mfa_required_for_vault: { plain: "Opening the vault needs your second sign-in step.", remediation: "Set up or complete two-step sign-in in Settings → Security." },
  tray_bootstrap_invalid: { plain: "The tray's one-time sign-in expired or was already used.", remediation: "Restart Raiker from the tray." },
  tray_owner_unavailable: { plain: "The tray could not find the owner account.", remediation: "Open Raiker and finish setup first." },
  chatgpt_subscription_signed_out: { plain: "The ChatGPT subscription is signed out.", remediation: "Sign in again from Models." },
  // Requests that were repeated or arrived out of order.
  idempotency_key_in_progress: { plain: "The same request is still being handled.", remediation: "Wait a moment; it will finish on its own." },
  idempotency_key_invalid: { plain: "The request carried a malformed retry key.", remediation: "Reload the page and try again." },
  control_command_stale: { plain: "A newer control for this turn arrived first, so this one was ignored.", remediation: "Nothing more is needed." },
  control_command_sequence_invalid: { plain: "The control arrived out of order.", remediation: "Reload the conversation and try again." },
  interrupt_target_not_found: { plain: "The turn to interrupt has already ended.", remediation: "Nothing more is needed." },
  retry_source_not_in_session: { plain: "The answer to retry is not in this conversation.", remediation: "Open the conversation it belongs to and retry there." },
  // Things that are gone.
  session_not_found: { plain: "This conversation no longer exists.", remediation: "Open another one from Sessions." },
  unknown_session: { plain: "This conversation no longer exists.", remediation: "Open another one from Sessions." },
  turn_not_found: { plain: "That message is no longer in the conversation.", remediation: "Reload the conversation." },
  unknown_turn: { plain: "That message is no longer in the conversation.", remediation: "Reload the conversation." },
  task_not_found: { plain: "This task no longer exists.", remediation: "Reopen Tasks to see the current list." },
  goal_not_found: { plain: "This goal no longer exists.", remediation: "Reopen Tasks to see the current list." },
  memory_not_found: { plain: "This memory no longer exists.", remediation: "Reopen Memory to see what is kept." },
  library_pin_not_found: { plain: "This pin was already removed.", remediation: "Reopen Library to see what is pinned." },
  library_pin_not_a_block: { plain: "Only a block of an answer can be pinned.", remediation: "Pin a code block, table or chart instead." },
  library_kind_unknown: { plain: "Library has no section of that kind.", remediation: "Choose one of Library's sections." },
  session_delete_confirmation_required: { plain: "Deleting a conversation needs confirmation.", remediation: "Confirm the deletion in the dialog." },
  execution_environment_not_found: { plain: "This execution environment no longer exists.", remediation: "Reopen Settings → Advanced to see the current list." },
  execution_environment_not_probeable: { plain: "This environment cannot be checked from here.", remediation: "Check it on the machine it runs on." },
  invalid_execution_config: { plain: "That execution setting is not valid.", remediation: "Check the values and save again." },
  invalid_enabled: { plain: "The on/off value was not understood.", remediation: "Turn it on or off again." },
  model_context_capacity_invalid: { plain: "That context size is outside what the model supports.", remediation: "Choose a size within the range shown." },
  github_owner_and_repo_required: { plain: "A GitHub owner and repository are both needed.", remediation: "Enter them as owner/repository." },
  repo_path_required: { plain: "A repository folder is needed.", remediation: "Choose the project's folder." },
  routine_delivery_channel_unknown: { plain: "That delivery channel is not set up.", remediation: "Set the channel up in Connections first." },
  routine_delivery_needs_consent: { plain: "Sending a routine's results there needs your consent.", remediation: "Allow delivery to that channel, then save." },
  routine_delivery_not_found: { plain: "This delivery no longer exists.", remediation: "Reopen the routine to see its deliveries." },
  credential_delta_decision_required: { plain: "No decision was chosen for the credential change.", remediation: "Choose Allow or Deny." },
  credential_delta_not_found: { plain: "This credential change was already decided.", remediation: "Nothing more is needed." },
  storage_full: { plain: "The disk Raiker writes to is full, so nothing from that request was saved.", remediation: "Free some disk space, then try again. Everything saved before is intact." },
  workspace_path_unchanged: { plain: "That file is the same in the copy and in your project.", remediation: "Choose a file listed as changed." },
  audit_export_empty: { plain: "There is nothing to export for that range.", remediation: "Choose a wider range." },
  audit_export_file_missing: { plain: "The export file is no longer on disk.", remediation: "Export again." },
  no_files: { plain: "No file was attached.", remediation: "Choose at least one file." },
  too_many_files: { plain: "Too many files were added at once.", remediation: "Add fewer files at a time." },
  memory_text_too_long: { plain: "The memory is longer than Raiker keeps in one entry.", remediation: "Shorten it, or split it into two memories." },
  embedding_model_not_offered: { plain: "That embedding model is not one this installation offers.", remediation: "Choose one from the list in Settings → Advanced → Memory." },
  voice_item_unknown: { plain: "Raiker's voice catalogue has no such item.", remediation: "Reopen Settings → Voice to see what can be installed." },
  // Design and images.
  base_version_required: { plain: "The edit did not say which version it changes.", remediation: "Reload the design and edit again." },
  design_proposal_already_decided: { plain: "This proposal was already accepted or declined.", remediation: "Nothing more is needed." },
  design_proposal_nothing_selected: { plain: "No part of the proposal was selected.", remediation: "Select at least one change, or decline it." },
  invalid_decision: { plain: "That decision was not understood.", remediation: "Accept or decline." },
  nothing_to_update: { plain: "The edit changed nothing.", remediation: "Make a change, then save." },
  unknown_design_document: { plain: "This design no longer exists.", remediation: "Open another from Design." },
  unknown_deleted_design_document: { plain: "This deleted design can no longer be restored.", remediation: "Nothing more can be done for it." },
  unknown_design_export: { plain: "This export no longer exists.", remediation: "Export the design again." },
  unknown_design_proposal: { plain: "This proposal no longer exists.", remediation: "Ask for a new one." },
  unknown_design_version: { plain: "This version of the design no longer exists.", remediation: "Choose one from the version list." },
  unknown_version_in_lineage: { plain: "That version is not part of this image's history.", remediation: "Choose one from the image's versions." },
  unknown_generation: { plain: "This image no longer exists.", remediation: "Generate it again." },
  unknown_deleted_generation: { plain: "This deleted image can no longer be restored.", remediation: "Generate it again." },
  image_bytes_missing: { plain: "The image file is missing from disk.", remediation: "Generate the image again." },
};

/** Copy for a code only when Raiker has words for it — never the generic fallback. */
export function knownReasonCopy(code: string | null | undefined): ReasonCopy | null {
  if (!code) return null;
  return REASON_CODES[code] ?? PREFIX_CODES[code.split(":", 1)[0]] ?? null;
}

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
