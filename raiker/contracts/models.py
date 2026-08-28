from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any, ClassVar

from raiker.models.tool_registry import CONTRACT_TOOL_NAMES

SCHEMA_VERSION = "1.0"

CLIENT_TYPES = {
    "cli",
    "tui",
    "desktop",
    "web_ui",
    "dashboard",
    "ide",
    "voice",
    "hotkeys",
    "rest",
    "webhooks",
    "email",
    "slack",
    "teams",
    "discord",
    "signal",
    "browser_extension",
    "apple_mobile",
    "android_mobile",
    "mobile_companion",
    "test_harness",
}
PLANNING_MODES = {"auto", "always", "never_safe_only"}
#: ``dont_ask`` (BUG-219) is the unattended posture: anything not already
#: permitted by a standing rule is **denied** rather than queued, because a
#: scheduled routine at 06:00 cannot answer a prompt and parking is not the same
#: as declining. It adds no enforcement — `deny` is a decision the runtime
#: already honours — and it can never widen a gate.
APPROVAL_MODES = {"manual", "auto", "skip", "dont_ask"}
VOICE_INPUT_MODES = {"typed", "dictated", "mixed"}
#: Which conversation surface produced a prompt. It selects the operating
#: protocol the turn is run under and nothing else: a surface can never widen
#: what a turn may do, and every capability, gate and approval is unchanged by
#: it. An unknown value is refused rather than silently treated as "chat".
PROMPT_SURFACES = {"chat", "build"}
_LEGACY_APPROVAL_MODE_ALIASES = {
    "interactive": "manual",
    "allow_safe_only": "auto",
    "deny_risky": "manual",
}
# Effectively unbounded: a turn ends when the model finishes or the provider's
# context/token budget runs out, not because of this counter. It exists only as
# a hard runaway-loop fail-safe; callers may still pass a lower explicit bound.
DEFAULT_MAX_TOOL_CALLS = 10_000
EVENT_TYPES = {
    "global_command_invoked",
    "terminal_client_started",
    "tui_started",
    "tui_ready",
    "tui_exited",
    "tui_prompt_submitted",
    "tui_command_submitted",
    "ui_action_submitted",
    "prompt_received",
    "prompt_normalised",
    "intent_classified",
    "risk_classified",
    "context_gathered",
    # Prior turns of this conversation replayed to the model. Counts only —
    # message count and character total — never the transcript itself.
    "conversation_history_replayed",
    # Automatic 90% model-context compaction. Metadata only: source-turn count
    # and token estimates, or a governed reason code on safe fallback. The
    # summary itself remains in the encrypted workspace store.
    "compacted_context_created",
    "compacted_context_failed",
    # Deterministic, bounded relationship extraction after a completed turn.
    # Payloads are counts/reason codes only; candidate text stays encrypted.
    "memory_relationship_extraction_completed",
    "memory_relationship_extraction_failed",
    # B2 — a turn parked for an approval, and the same turn picking up again
    # once the owner resolved it. Counts and ids only; the parked conversation
    # stays in the encrypted store and never enters an event payload.
    "turn_suspended_for_approval",
    "turn_suspension_failed",
    "turn_resumed_after_approval",
    "retrieval_augmentation",
    "plan_created",
    "plan_skipped",
    # B6 — the agent's own plan for the work. `agent_plan_updated` carries the
    # ordered steps the model wrote with `update_plan`, which is what the live
    # checklist renders; `agent_plan_replayed` records that a standing plan was
    # carried into a later turn (character count only). The steps are the
    # model's own short statements of intent, never workspace content.
    "agent_plan_updated",
    "agent_plan_replayed",
    # B7 — a bounded, read-only subagent finished. Metadata only: its name, its
    # contract id, the steps it ran and the read-only tools it used. The
    # findings themselves reach the calling model and nothing else.
    "subagent_completed",
    # B4 — tool calls a turn proposed but did not run, with the counts and the
    # boundary that stopped them (budget, approval, or policy).
    "model_tool_calls_dropped",
    # ADD-02 — tool calls held behind an approval boundary rather than dropped.
    # Counts and the parked call's place in its batch; the calls themselves are
    # parked with the turn and drained one decision at a time on resume.
    "model_tool_calls_queued",
    # BUG-52 — one call in a batch policy refused while the rest of the batch
    # carried on. Streamed, unlike the durable `policy_decision`, because a
    # refusal that no longer ends the turn would otherwise leave the transcript
    # silent about a call the model asked for and never got. Tool name and
    # governed reason codes only; no arguments and no workspace content.
    "model_tool_call_refused",
    # C6/C4 — the material this turn read, ledgered so the answer can name it.
    # Metadata only: how many sources were recorded, their ids, their kinds and
    # the tools that produced them. The titles the transcript renders and the
    # passages the inspector opens are content and stay in the encrypted store,
    # served only over the session-authorized read route.
    "turn_sources_recorded",
    "action_proposed",
    "action_validated",
    "policy_decision",
    "approval_requested",
    "approval_received",
    "approval_denied",
    # Composer-selected unattended approval policies. These attest that an
    # otherwise ordinary, governed action was executed under the owner's
    # persisted setting; they do not relax runtime gates or critical holds.
    "approval_auto_executed",
    # BUG-218 — `auto` promises a review, so it records when the review said no.
    # The action falls back to the ordinary approval queue; this event is the
    # evidence that Auto declined to grant it, with the path that did not match.
    "approval_auto_withheld",
    "approval_preview_skipped",
    # Approval execution relay (Workstream A). `approval_executed` records that a
    # previously human-approved action was re-governed and run through its own
    # capability's executor, carrying a metadata-only posture snapshot (A4).
    # `approval_execution_denied` records a relay refusal (posture degraded, or
    # the re-governed target was blocked/failed) with the same posture snapshot.
    "approval_executed",
    "approval_execution_denied",
    # Production critical-risk classification (Workstream F / F6, ZT-7). Recorded
    # when the in-code classification table elevates a governed action to the
    # critical floor; metadata only (criterion code, ZT ref, declared risk).
    "critical_action_classified",
    # Critical approval lifecycle (Workstream F / F7, ZT-7). A critical action's
    # resting state is deny; these record the full "notify → manual human decision
    # → deny/execute" path (each carrying a posture snapshot): `created`/`notified`
    # when it is parked and the owner is told; `resolved` (approved or rejected);
    # `step_up_required` when approving needs fresh verification; `expired` when
    # the TTL lapses; `denied` for a non-human/degraded resolution attempt.
    "critical_approval_created",
    "critical_approval_notified",
    "critical_approval_resolved",
    "critical_approval_step_up_required",
    "critical_approval_expired",
    "critical_approval_denied",
    # Scoped standing approval grants (Workstream F / F3, ZT-5). Lifecycle events
    # for the grant engine — created/denied/revoked are the human decisions, and
    # `standing_grant_applied` records that an active grant satisfied an
    # AI-proposed action's approval requirement (with the grant id + posture).
    "standing_grant_created",
    "standing_grant_denied",
    "standing_grant_revoked",
    "standing_grant_applied",
    "tool_started",
    "tool_completed",
    "tool_failed",
    "verification_started",
    "verification_completed",
    "memory_candidate_reviewed",
    "memory_record_created",
    "memory_record_forgotten",
    # MEM-04 — eidetic capture. `eidetic_observation_skipped` is emitted when
    # the *bookkeeping* failed, which is a different fact from an observation
    # the runtime deliberately refused on sensitivity: that one is a row in
    # `eidetic_observations` carrying its own reason, because the owner has to
    # be able to see it in Memory rather than only in the audit log.
    "eidetic_observation_skipped",
    "response_created",
    "checkpoint_created",
    # Checkpoint pre-image capture (Workstream B / B1). `checkpoint_captured`
    # records that a workspace-file mutation's pre-image was snapshot into the
    # content-addressed blob store before the mutation ran — metadata only
    # (content-address, size, status), never file content. `checkpoint_capture_failed`
    # records a best-effort capture that could not be persisted; it never blocks
    # the underlying mutation.
    "checkpoint_captured",
    "checkpoint_capture_failed",
    "turn_closed",
    "machine_identity_issued",
    "machine_identity_rotated",
    "machine_identity_refused",
    "machine_identity_deactivated",
    "error_recorded",
    "turn_state_changed",
    "model_profile_loaded",
    "model_launch_requested",
    "model_launch_completed",
    "model_launch_failed",
    "model_request_started",
    "model_request_completed",
    "model_request_failed",
    "model_output_chunk",
    "model_request_cancelled",
    "model_health_check_started",
    "model_health_check_completed",
    "model_provider_rejected_by_policy",
    "model_fallback_engaged",
    # BUG-72 — one re-attempt on the same model after a transport failure. It is
    # its own type rather than a second `model_request_started`, so the audit
    # trail distinguishes "the turn asked twice" from "the turn asked twice
    # because the first attempt never reached the provider".
    "model_request_retried",
    "model_profile_selected",
    "model_capabilities_inspected",
    "reasoning_setting_changed",
    "reasoning_setting_rejected",
    "model_tool_call_rejected",
    # BUG-21 — the price registry's audit trail. An administrator override is
    # never anonymous: who set it, for which exact model, and why. The rates
    # themselves live in the registry, which is effective-dated and append-only;
    # these events record that a human changed what the product charges against.
    "model_price_override_recorded",
    "model_price_override_cleared",
    "model_price_synchronised",
    # BUG-22 — a transcript left the runtime as a file. Metadata only: format,
    # message and file counts, and the redaction policy applied. The transcript
    # itself is never written into an event payload.
    "session_transcript_exported",
    # BUG-28 — a file this conversation holds left the runtime as bytes. Metadata
    # only: which attachment, its name, type and size. The bytes themselves are
    # never written into an event payload.
    "attachment_downloaded",
    "runtime_error_recorded",
    # A chat moved into or out of an organizing project. The move grants
    # nothing; it changes only the bounded context the chat receives.
    "session_project_changed",
    # A chat's organizing title changed. Renaming grants nothing.
    "session_renamed",
    # A chat was soft-archived (moved out of the default active list) or
    # restored. Reversible; never deletes transcripts, events, or permissions.
    "session_archived",
    "session_unarchived",
    # An owner added or removed an MCP connection profile (local or remote). The
    # payload is redacted metadata only (name, transport, host) — never a token.
    "mcp_connection_added",
    "mcp_connection_removed",
    # Installed-skill lifecycle. A skill is instruction text, so these record
    # what the owner installed, renamed, turned on or off, and removed — the
    # payload is metadata (name, source, checksum, sizes), never the document.
    # `skills_indexed` records how many active skills a turn advertised.
    "skill_installed",
    "skill_imported",
    "skill_built",
    "skill_renamed",
    "skill_activated",
    "skill_command_changed",
    "skill_deactivated",
    "skill_deleted",
    "skills_indexed",
    # The Knowledge Map's access to one folder on this machine was granted or
    # withdrawn. The payload carries the path deliberately: what an owner opened
    # to the graph, and when, is the whole substance of the record — and
    # revoking removes every source indexed under it, which is a change the
    # audit log has to be able to explain afterwards.
    "brain_source_folder_granted",
    "brain_source_folder_revoked",
    # A repository reference was connected to, or removed from, the Build
    # workspace: a workspace-contained local subpath, or a GitHub `owner/repo`
    # coordinate. The payload is the reference only — never a credential — and
    # the reference grants nothing: local paths stay workspace-contained, and
    # GitHub reads stay governed by the `connector_github_runtime` gate.
    "code_repo_connected",
    "code_repo_disconnected",
    # B9 — the repository code map was built from scratch, or refreshed for the
    # paths an approved write touched. The payload is counts and reasons only —
    # file/symbol/edge totals, what the scan skipped, and which bound it hit —
    # never a path's content and never a symbol's text.
    "code_map_indexed",
    "code_map_refreshed",
    # Per-session MCP monitoring (Phase B). A governed MCP session completed —
    # redacted telemetry only (counts, hosts, byte totals, outcome). An anomaly
    # rule tripped — a redacted finding was raised (never a payload or token).
    "mcp_session_completed",
    "mcp_anomaly_detected",
    # Containment (Phase C). A connection was paused (revocable circuit breaker —
    # auto on a high-severity anomaly, or the owner's one-call stop), resumed
    # (back to active), or killed (instant kill switch). Redacted metadata only
    # (server_id, source, redacted reason) — never a payload or token.
    "mcp_connection_paused",
    "mcp_connection_resumed",
    "mcp_connection_killed",
    # Capability-agnostic monitoring and containment (BUG-76, BUG-77). The same
    # three facts the MCP stream records, for every other capability family:
    # an anomaly rule tripped on a connector/plugin/subagent/execution subject;
    # a subject was contained (the revocable pause a high-severity anomaly or a
    # consecutive-failure threshold trips, or the owner's stop) or cleared; and
    # a call was refused because its subject is contained. Redacted metadata
    # only — capability, subject id, counts and a stated reason.
    "capability_anomaly_detected",
    "capability_contained",
    "capability_containment_cleared",
    "capability_call_refused",
    # A source this turn read contained text shaped like a prompt-injection
    # attempt (BUG-81). Advisory and provenance-only: the refusal path stays the
    # tool gate. The payload names the rules that matched, their counts, and the
    # source's own locator — never the matched text.
    "prompt_injection_suspected",
    # A delegated subagent result was bound to the spawn that produced it, or
    # could not be and was refused (BUG-78). Identifiers and a digest only — the
    # findings themselves reach the calling model and nowhere else.
    "subagent_result_verified",
    "subagent_result_refused",
    "task_created",
    # BUG-64 — explicit owner intent that makes a parked task due. Creation is
    # its own event and never implies this one for model-proposed work.
    "task_run_requested",
    "task_started",
    "task_progress",
    "task_paused",
    "task_cancelled",
    "task_completed",
    "task_failed",
    # A run stopped at an approval boundary. Distinct from `task_failed`: the
    # work did not go wrong, it is waiting for the owner's decision, and the
    # payload always states which one and why (BUG-09).
    "task_blocked",
    # A task's own run finished while work it delegated has not (BUG-220).
    # Distinct from `task_completed` because it is not one, and distinct from
    # `task_blocked` because no decision of the owner's moves it: what moves it
    # is the last child landing. The payload states how many are outstanding.
    "task_waiting_for_children",
    # A granted approval is being replayed into a parked run, and the same run
    # could not be continued automatically (BUG-25). The pair is what makes an
    # approval's effect readable after the fact: the decision, the attempt to
    # act on it, and — when the attempt could not proceed — the stated reason.
    "task_resume_started",
    "task_resume_blocked",
    "side_question_received",
    "side_question_answered",
    "interrupt_received",
    "safe_boundary_reached",
    "task_steered",
    # B17/C13 — the owner's two controls over a turn that is already running.
    # `turn_stopped` records that a running turn ended early because the owner
    # asked it to, with the boundary it stopped at and how much it had done;
    # `turn_steered` records that the owner's own words entered the running turn
    # at that boundary. Character counts only — the instruction itself is a user
    # message and lives in the conversation, not in the audit payload.
    "turn_stopped",
    "turn_steered",
    "checkpoint_restore_planned",
    "checkpoint_fork_planned",
    "phase3.workspace.inspection.requested",
    "phase3.plugin.manifest.validated",
    "phase3.plugin.registration.planned",
    "phase3.plugin.registration.denied",
    "phase3.client.contract.inspected",
    "hook_matched",
    "hook_executed",
    "hook_decision",
    "hook_failed",
    "hook_timeout",
    "hook_context_added",
    "review_started",
    "review_completed",
    "review_failed",
    "review_proposals_created",
    "proposal_lifecycle_created",
    "proposal_lifecycle_status_changed",
    "proposal_lifecycle_listed",
    "proposal_lifecycle_viewed",
    "proposal_approval_preview_created",
    "proposal_approval_preview_listed",
    "proposal_approval_preview_viewed",
    "managed_policy_applied",
    "managed_policy_override",
    "user_created",
    "user_deactivated",
    "role_created",
    "role_deleted",
    "user_role_granted",
    "user_role_revoked",
    "session_user_bound",
    "audit_export_created",
    "event_integrity_verified",
    "plugin_checksum_verified",
    "plugin_signature_verified",
    "plugin_marketplace_install_recorded",
    "hosted_routine_created",
    "hosted_routine_deleted",
    "budget_record_created",
    "budget_threshold_exceeded",
    "retention_policy_applied",
    "backup_manifest_created",
    "channel_paired",
    "channel_unpaired",
    "channel_message_received",
    "channel_message_routed",
    "channel_routing_changed",
    "channel_message_rejected",
    "approval_relay_requested",
    "approval_relay_approved",
    "approval_relay_denied",
    "approval_relay_denied_by_default",
    "subagent_contract_created",
    "subagent_spawn_denied",
    "team_ledger_created",
    "team_work_proposed",
    "team_execution_denied",
    "remote_execution_planned",
    "remote_execution_denied",
    "execution_budget_recorded",
    "execution_cleanup_planned",
    "desktop_app_launched",
    "desktop_workspace_rendered",
    "web_app_launched",
    "web_api_request_authenticated",
    "dashboard_widget_rendered",
    "mobile_app_launched",
    "mobile_approval_submitted",
    "mobile_approval_rejected_stale",
    "plugin_code_execution_planned",
    "plugin_code_execution_started",
    "plugin_code_execution_completed",
    "plugin_code_execution_denied",
    "graph_runtime_index_requested",
    "graph_runtime_index_started",
    "graph_runtime_index_completed",
    "graph_runtime_index_denied",
    "semantic_memory_write_requested",
    "semantic_memory_write_approved",
    "semantic_memory_write_completed",
    "semantic_memory_write_denied",
    "ide_extension_connected",
    "ide_action_routed",
    "vector_embedding_created",
    "vector_search_performed",
    "vector_index_flushed",
    "graph_symbol_extracted",
    "graph_dependency_discovered",
    "graph_index_flushed",
    "project_graph_built",
    "project_graph_queried",
    "skill_candidate_proposed",
    "skill_candidate_reviewed",
    "skill_candidate_recorded",
    "runtime_mode_activation_requested",
    "runtime_mode_activated",
    "runtime_mode_disabled",
    "capability_transition_requested",
    "capability_transition_approved",
    "capability_enabled",
    "capability_disabled",
    "capability_transition_denied",
    "capability_decision_mode_set",
    "threat_model_acknowledged",
    "runtime_readiness_checked",
    "owner_bootstrap_requested",
    "owner_bootstrap_created",
    "owner_bootstrap_denied",
    "owner_recovery_requested",
    "owner_recovery_created",
    "owner_recovery_denied",
    "owner_recovery_old_owner_deactivated",
    "principal_resolved",
    "principal_resolution_failed",
    "action_executed",
    "action_failed",
    "attachment_image_included",
    "attachment_image_withheld",
    "reminder_delivered",
    "reminder_paused",
    "reminder_cancelled",
    "reminder_retried",
}
INTENTS = {
    "chat",
    "filesystem_query",
    "code_inspection",
    "code_change_request",
    "local_action_request",
    "unknown",
}
RISK_LEVELS = {"low", "medium", "high", "critical", "blocked"}
# Derived, not restated: a tool that is registered is a tool this contract
# knows. The previous hand-maintained set was one of the twelve places a new
# tool had to be written into, and the only symptom of forgetting was a
# contract-validation failure a long way from the omission.
TOOLS = set(CONTRACT_TOOL_NAMES)
POLICY_DECISIONS = {"allow", "deny", "needs_approval", "allow_managed"}
MANAGED_POLICY_EFFECTS = {"allow", "deny"}
TOOL_STATUSES = {"success", "failed", "denied", "approval_required"}
# B17/C13 — `stopped` is its own outcome. A turn the owner ended at a safe
# boundary did not fail and was not denied: it did some of the work, kept what it
# had already said, and stopped because it was told to. Reporting that as
# `failed` would have blamed the runtime for the owner's decision.
RESPONSE_STATUSES = {"completed", "needs_approval", "denied", "failed", "stopped"}
INTERFACE_STATUS = {"equal_primary_when_enabled"}


class ContractValidationError(ValueError):
    pass


def _require(value: Any, field_name: str) -> None:
    if value is None or value == "":
        raise ContractValidationError(f"missing_required_field:{field_name}")


def _one_of(value: str, allowed: set[str], field_name: str) -> None:
    if value not in allowed:
        raise ContractValidationError(f"invalid_{field_name}:{value}")


# BUG-73 — the sentence a turn shows *while* it is parked on an approval.
#
# It used to be persisted as that turn's assistant response, which is how one
# conversation ended, durably, reading "Approval required for local action. No
# command was executed." beneath the chip for the file the approval had just
# written. The write had happened, was checkpointed, and had changed the
# filesystem; the transcript said otherwise, and a reload did not correct it.
#
# Two things changed. It now *reads* as a state rather than as a verdict on
# execution, and it is no longer stored as an answer at all: `close_turn` refuses
# to persist it (see `AgentGateway._persisted_summary`), so a resume replaces it
# by construction and an interrupted resume leaves the parked state showing
# rather than a false claim. Naming both here is what lets the persistence layer
# recognise the notice wherever it was produced — including the old wording,
# which a workspace written before this change can still be carrying.
PARKED_FOR_APPROVAL_NOTICE = "Waiting for your decision. Nothing has run yet."
LEGACY_PARKED_FOR_APPROVAL_NOTICE = (
    "Approval required for local action. No command was executed."
)


# BUG-70 — the only decision modes a *turn* may name for itself. Both tighten:
# `ask` turns an unprompted run into a decision, `deny` refuses the call
# outright. `allow` and `auto` are absent on purpose — they loosen, and loosening
# is a change to standing authority that belongs to the Permissions step-up, not
# to a composer chip.
TURN_TIGHTENING_MODES = {"ask", "deny"}


def validated_turn_capability_modes(value: Mapping[str, str] | None) -> dict[str, str]:
    """Normalise and validate a turn-scoped capability posture.

    Rejects an unknown capability and any mode that is not one of
    :data:`TURN_TIGHTENING_MODES`, so an over-permissive value cannot ride in on
    a prompt body and be silently ignored somewhere downstream — it fails the
    envelope, which is where a caller can see it.
    """
    if not value:
        return {}
    if not isinstance(value, Mapping):
        raise ContractValidationError("invalid_capability_modes")
    from raiker.phase_gates import ALL_CAPABILITIES

    cleaned: dict[str, str] = {}
    for capability, mode in value.items():
        if not isinstance(capability, str) or capability not in ALL_CAPABILITIES:
            raise ContractValidationError(f"unknown_capability:{capability}")
        if not isinstance(mode, str) or mode not in TURN_TIGHTENING_MODES:
            raise ContractValidationError(f"invalid_turn_capability_mode:{mode}")
        cleaned[capability] = mode
    return cleaned


def normalize_approval_mode(value: str) -> str:
    normalized = _LEGACY_APPROVAL_MODE_ALIASES.get(value, value)
    _one_of(normalized, APPROVAL_MODES, "approval_mode")
    return normalized


def normalize_input_mode(value: object) -> str:
    """Validate client-reported prompt provenance without inferring audio facts."""
    if not isinstance(value, str) or value not in VOICE_INPUT_MODES:
        raise ContractValidationError(f"invalid_input_mode:{value}")
    return value


def normalize_prompt_surface(value: object) -> str:
    """Validate which composer a prompt came from.

    The surface is advisory about *how to work*, never about *what is allowed*.
    It is still validated here rather than coerced, because a turn whose surface
    the runtime guessed would put a Build operating protocol on a Chat turn (or
    the reverse) without anything in the audit trail saying so.
    """
    if not isinstance(value, str) or value not in PROMPT_SURFACES:
        raise ContractValidationError(f"invalid_prompt_surface:{value}")
    return value


def _schema(value: str) -> None:
    if value != SCHEMA_VERSION:
        raise ContractValidationError(f"unsupported_schema_version:{value}")


@dataclass(frozen=True)
class ClientMetadata:
    type: str
    name: str
    version: str
    interface_status: str = "equal_primary_when_enabled"

    def __post_init__(self) -> None:
        _one_of(self.type, CLIENT_TYPES, "client_type")
        _require(self.name, "client.name")
        _require(self.version, "client.version")
        _one_of(self.interface_status, INTERFACE_STATUS, "interface_status")


@dataclass(frozen=True)
class UserMetadata:
    id: str = "local_user"
    display_name: str | None = None

    def __post_init__(self) -> None:
        _require(self.id, "user.id")


@dataclass(frozen=True)
class PromptPayload:
    text: str
    attachments: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require(self.text, "prompt.text")


@dataclass(frozen=True)
class PromptOptions:
    planning_mode: str = "auto"
    approval_mode: str = "manual"
    # Empty means "the operator's selected model" (persisted via /model use);
    # an explicit profile id binds this turn only. Never defaults to a test provider.
    model_profile: str = ""
    # Optional concrete model for the chosen profile, for providers whose profile
    # ships a placeholder model or serves several models. Only meaningful together
    # with model_profile; provider policy (gates, egress, keys) is still enforced
    # downstream, so naming a model never grants access to its provider.
    model: str = ""
    # Per-turn only; exact support is resolved against the chosen provider/model
    # by the runtime and never mutates the persisted model selection.
    reasoning_effort: str | None = None
    max_tool_calls: int = DEFAULT_MAX_TOOL_CALLS
    # BUG-70 — a **turn-scoped** capability posture, and deliberately a
    # one-directional one. Build's Plan / Edit / Auto chips used to POST four
    # `/api/capability-modes/<cap>/<mode>` changes, which rewrote the owner's
    # *standing* permissions — globally, permanently, and without the step-up
    # (recorded reason, threat-model acknowledgement) the Permissions page
    # demands for the identical transition. A control presented as a per-turn
    # posture must not be a silent edit of four high-risk permissions.
    #
    # So a turn may only ever *tighten* itself: `ask` and `deny` are the only
    # accepted values, and the standing mode still governs everything this map
    # does not name. A turn can therefore never grant itself authority the owner
    # has not already given it, which is why this needs no ceremony of its own.
    capability_modes: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _one_of(self.planning_mode, PLANNING_MODES, "planning_mode")
        object.__setattr__(self, "approval_mode", normalize_approval_mode(self.approval_mode))
        object.__setattr__(
            self, "capability_modes", validated_turn_capability_modes(self.capability_modes)
        )
        if self.reasoning_effort is not None and (
            not isinstance(self.reasoning_effort, str) or not self.reasoning_effort
        ):
            raise ContractValidationError("invalid_reasoning_effort")
        if self.max_tool_calls < 0:
            raise ContractValidationError("invalid_max_tool_calls")


@dataclass(frozen=True)
class PromptEnvelope:
    request_id: str
    session_id: str
    turn_id: str
    client: ClientMetadata
    user: UserMetadata
    prompt: PromptPayload
    options: PromptOptions
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        for field_name in ("request_id", "session_id", "turn_id"):
            _require(getattr(self, field_name), field_name)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PromptEnvelope:
        allowed = {
            "schema_version",
            "request_id",
            "session_id",
            "turn_id",
            "client",
            "user",
            "prompt",
            "options",
        }
        unknown = set(data) - allowed
        if unknown:
            raise ContractValidationError(f"unknown_fields:{sorted(unknown)}")
        return cls(
            schema_version=data["schema_version"],
            request_id=data["request_id"],
            session_id=data["session_id"],
            turn_id=data["turn_id"],
            client=ClientMetadata(**data["client"]),
            user=UserMetadata(**data.get("user", {"id": "local_user"})),
            prompt=PromptPayload(**data["prompt"]),
            options=PromptOptions(**data["options"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class UIActionEnvelope:
    action_id: str
    session_id: str
    turn_id: str
    client: ClientMetadata
    action_type: str
    payload: dict[str, Any]
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.action_id, "action_id")
        _require(self.action_type, "action_type")


@dataclass(frozen=True)
class ChannelMessageEnvelope:
    channel_message_id: str
    connector_id: str
    channel_type: str
    session_id: str
    sender: dict[str, Any]
    message: dict[str, Any]
    routing: dict[str, Any]
    received_at: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.channel_message_id, "channel_message_id")
        _one_of(self.channel_type, CLIENT_TYPES, "channel_type")


@dataclass(frozen=True)
class AgentEvent:
    event_id: str
    timestamp: str
    session_id: str
    turn_id: str | None
    event_type: str
    actor: str
    payload: dict[str, Any]
    parent_event_id: str | None = None
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.event_id, "event_id")
        _require(self.timestamp, "timestamp")
        _require(self.session_id, "session_id")
        _one_of(self.event_type, EVENT_TYPES, "event_type")
        _require(self.actor, "actor")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ToolAction:
    action_id: str
    tool_name: str
    arguments: dict[str, Any]
    risk_level: str
    requires_approval: bool
    proposed_by: str = "agent_runtime"
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.action_id, "action_id")
        _require(self.tool_name, "tool_name")
        _one_of(self.risk_level, RISK_LEVELS, "risk_level")
        _require(self.proposed_by, "proposed_by")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PolicyDecision:
    decision_id: str
    action_id: str
    decision: str
    reasons: list[str]
    requires_user_approval: bool
    policy_version: str = "phase1-static-v1"
    risk_level: str | None = None
    timestamp: str | None = None
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.decision_id, "decision_id")
        _require(self.action_id, "action_id")
        _one_of(self.decision, POLICY_DECISIONS, "decision")
        if not self.reasons:
            raise ContractValidationError("missing_policy_reasons")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ToolResult:
    action_id: str
    tool_name: str
    status: str
    output: dict[str, Any] | None
    error: dict[str, Any] | None
    started_at: str
    completed_at: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.action_id, "action_id")
        _require(self.tool_name, "tool_name")
        _one_of(self.status, TOOL_STATUSES, "status")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentResponse:
    request_id: str
    session_id: str
    turn_id: str
    status: str
    message: str
    events_path: str | None = None
    checkpoint_path: str | None = None
    client: ClientMetadata | None = None
    approval: dict[str, Any] | None = None
    last_event_id: str | None = None
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _one_of(self.status, RESPONSE_STATUSES, "response_status")
        _require(self.message, "message")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Checkpoint:
    checkpoint_id: str
    session_id: str
    turn_id: str
    created_at: str
    runtime_state: str
    summary: str
    last_event_id: str
    memory_candidates: list[dict[str, Any]] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.checkpoint_id, "checkpoint_id")
        _require(self.session_id, "session_id")
        _require(self.turn_id, "turn_id")
        _require(self.created_at, "created_at")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ModelProfile:
    profile_id: str
    provider: str
    model: str
    build_phase: str
    default_state: str
    tui_launch_action: str
    local_only: bool
    requires_network: bool
    raw: dict[str, Any] = field(default_factory=dict)
    schema_version: ClassVar[str] = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for field_name in ("profile_id", "provider", "model", "build_phase", "default_state"):
            _require(getattr(self, field_name), field_name)


@dataclass(frozen=True)
class ConnectorProfile:
    connector_id: str
    channel_type: str
    display_name: str
    build_phase: str
    default_state: str
    transport: str
    auth_method: str
    interface_status: str
    requires_pairing: bool
    requires_sender_allowlist: bool
    requires_network: bool
    setup_ui: str
    capability_policy_template: str
    raw: dict[str, Any] = field(default_factory=dict)
    schema_version: ClassVar[str] = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for field_name in (
            "connector_id",
            "channel_type",
            "display_name",
            "build_phase",
            "default_state",
            "transport",
            "auth_method",
            "interface_status",
            "setup_ui",
            "capability_policy_template",
        ):
            _require(getattr(self, field_name), field_name)
        _one_of(self.interface_status, INTERFACE_STATUS, "interface_status")


TASK_STATUSES = {
    "queued",
    "running",
    # A granted approval being replayed into a run that parked on it (BUG-25).
    # Distinct from `running` on purpose: the owner needs to see their decision
    # take effect, and "running" on a card that was waiting a moment ago does
    # not say that the approval is what moved it.
    "continuing",
    "waiting_for_approval",
    "waiting_for_user_answer",
    # BUG-220 - a task whose own run finished while work it delegated has not.
    # Distinct from `completed` because it is not finished, and distinct from
    # `waiting_for_approval` because no decision of the owner's moves it: what
    # moves it is the last child landing.
    "waiting_for_children",
    "paused",
    "cancelling",
    "cancelled",
    "completed",
    "failed",
}


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    session_id: str
    title: str
    objective: str
    status: str
    created_at: str
    updated_at: str
    parent_turn_id: str | None = None
    parent_task_id: str | None = None
    current_step: str | None = None
    progress_percent: int | None = None
    completed_at: str | None = None
    summary: str | None = None
    priority: str | None = None
    scheduled_at: str | None = None
    recurrence: str | None = None
    reminder_at: str | None = None
    # Project-scoped schedules: the organizing project the task/schedule was
    # created under. None for a task created outside any project.
    project_id: str | None = None
    model_profile: str | None = None
    model: str | None = None
    attachments: list[dict[str, Any]] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.task_id, "task_id")
        _require(self.session_id, "session_id")
        _require(self.title, "title")
        _require(self.objective, "objective")
        _one_of(self.status, TASK_STATUSES, "task_status")


SIDE_QUESTION_STATUSES = {"answered"}
INTERRUPT_ACTION_TYPES = {"pause", "cancel", "steer", "resume"}


@dataclass(frozen=True)
class SideQuestionTurn:
    child_turn_id: str
    parent_turn_id: str
    session_id: str
    question: str
    answer: str
    status: str = "answered"
    read_only: bool = True
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.child_turn_id, "child_turn_id")
        _require(self.parent_turn_id, "parent_turn_id")
        _require(self.session_id, "session_id")
        _require(self.question, "question")
        _require(self.answer, "answer")
        _one_of(self.status, SIDE_QUESTION_STATUSES, "side_question_status")
        if not self.read_only:
            raise ContractValidationError("side_question_must_be_read_only")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class InterruptAction:
    action_id: str
    task_id: str
    session_id: str
    action_type: str
    reason: str
    steer_text: str | None = None
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.action_id, "action_id")
        _require(self.task_id, "task_id")
        _require(self.session_id, "session_id")
        _one_of(self.action_type, INTERRUPT_ACTION_TYPES, "interrupt_action_type")
        _require(self.reason, "reason")
        if self.action_type == "steer" and not self.steer_text:
            raise ContractValidationError("missing_steer_text")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class User:
    user_id: str
    display_name: str | None
    email: str | None
    is_active: bool
    created_at: str
    updated_at: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.user_id, "user_id")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Role:
    role_id: str
    name: str
    description: str | None
    is_system_role: bool
    created_at: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.role_id, "role_id")
        _require(self.name, "role_name")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class UserRoleAssignment:
    assignment_id: str
    user_id: str
    role_id: str
    granted_at: str
    granted_by: str | None
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.assignment_id, "assignment_id")
        _require(self.user_id, "user_id")
        _require(self.role_id, "role_id")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HostedRoutine:
    routine_id: str
    name: str
    routine_type: str
    schedule: str | None
    endpoint: str | None
    enabled: bool
    created_by: str
    created_at: str
    updated_at: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.routine_id, "routine_id")
        _require(self.name, "name")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BudgetRecord:
    budget_id: str
    name: str
    max_cost: float
    current_cost: float
    currency: str
    scope: str
    enabled: bool
    created_by: str
    created_at: str
    updated_at: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.budget_id, "budget_id")
        _require(self.name, "name")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetentionPolicy:
    policy_id: str
    target_type: str
    retention_days: int
    legal_hold: bool
    enabled: bool
    created_by: str
    created_at: str
    updated_at: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.policy_id, "policy_id")
        _require(self.target_type, "target_type")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BackupManifest:
    manifest_id: str
    backup_type: str
    scope_json: str
    path: str | None
    checksum: str | None
    size_bytes: int | None
    created_by: str
    created_at: str
    encryption_key_id: str | None = None
    retention_until: str | None = None
    legal_hold: bool = False
    erasure_requested_at: str | None = None
    erased_at: str | None = None
    restore_verified_at: str | None = None
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.manifest_id, "manifest_id")
        _require(self.backup_type, "backup_type")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PluginInstallRecord:
    record_id: str
    plugin_id: str
    version: str
    trust_level: str
    checksum: str | None
    signature: str | None
    source_url: str | None
    commit_sha: str | None
    permissions_json: str
    status: str
    installed_at: str
    installed_by: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.record_id, "record_id")
        _require(self.plugin_id, "plugin_id")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExportManifest:
    export_id: str
    manifest_hash: str
    scope_json: str
    redacted: bool
    event_count: int
    first_event_id: str | None
    last_event_id: str | None
    first_timestamp: str | None
    last_timestamp: str | None
    export_path: str | None
    exported_by: str
    created_at: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.export_id, "export_id")
        _require(self.manifest_hash, "manifest_hash")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ManagedPolicyRule:
    rule_id: str
    effect: str
    tool_pattern: str
    arguments_json: str | None
    priority: int
    enabled: bool
    reason: str
    created_by: str
    created_at: str
    updated_at: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.rule_id, "rule_id")
        _one_of(self.effect, MANAGED_POLICY_EFFECTS, "managed_policy_effect")
        _require(self.tool_pattern, "tool_pattern")
        _require(self.reason, "reason")
        _require(self.created_by, "created_by")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesktopAppSession:
    session_id: str
    app_version: str
    window_state: str
    connected_at: str
    last_active_at: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.session_id, "session_id")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WebApiSession:
    token_id: str
    session_id: str
    client_type: str
    created_at: str
    expires_at: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.token_id, "token_id")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PluginExecutionRecord:
    execution_id: str
    plugin_id: str
    version: str
    trust_level: str
    permissions_json: str
    entrypoint: str
    status: str
    started_at: str | None
    completed_at: str | None
    created_by: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.execution_id, "execution_id")
        _require(self.plugin_id, "plugin_id")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GraphIndexRecord:
    index_id: str
    workspace_root: str
    status: str
    nodes_count: int
    edges_count: int
    started_at: str | None
    completed_at: str | None
    created_by: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.index_id, "index_id")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticMemoryWriteRecord:
    write_id: str
    content_summary: str
    embedding_model: str
    vector_count: int
    status: str
    approved_by: str | None
    created_at: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.write_id, "write_id")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IdeExtensionSession:
    session_id: str
    extension_version: str
    ide_type: str
    connected_at: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.session_id, "session_id")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


CHANNEL_RELAY_STATUSES = {"pending", "approved", "denied", "expired"}
SUBAGENT_STATUSES = {"created", "running", "completed", "failed", "cancelled"}
TEAM_STATUSES = {"created", "active", "completed", "cancelled"}


@dataclass(frozen=True)
class ChannelPairing:
    pairing_id: str
    connector_id: str
    channel_type: str
    display_name: str
    paired_at: str
    paired_by: str
    enabled: bool
    sender_allowlist_json: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.pairing_id, "pairing_id")
        _require(self.connector_id, "connector_id")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ApprovalRelayRecord:
    relay_id: str
    pairing_id: str
    action_id: str
    status: str
    requested_at: str
    resolved_at: str | None
    resolved_by: str | None
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.relay_id, "relay_id")
        _require(self.pairing_id, "pairing_id")
        _one_of(self.status, CHANNEL_RELAY_STATUSES, "relay_status")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SubagentContract:
    subagent_id: str
    parent_task_id: str
    name: str
    mode: str
    allowed_tools_json: str
    max_depth: int
    max_runtime_seconds: int
    max_cost: float
    created_by: str
    created_at: str
    status: str
    # C1: per-spawn budget dimensions (0 = unset on legacy rows). Persisted so a
    # subagent's enforced resource envelope is auditable after the run.
    max_steps: int = 0
    max_tool_calls: int = 0
    max_tokens: int = 0
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.subagent_id, "subagent_id")
        _require(self.parent_task_id, "parent_task_id")
        _one_of(self.status, SUBAGENT_STATUSES, "subagent_status")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TeamLedger:
    team_id: str
    name: str
    mode: str
    members_json: str
    max_depth: int
    max_cost: float
    created_by: str
    created_at: str
    status: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.team_id, "team_id")
        _one_of(self.status, TEAM_STATUSES, "team_status")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RemoteExecutionProfile:
    profile_id: str
    profile_type: str
    name: str
    config_json: str
    enabled: bool
    created_by: str
    created_at: str
    updated_at: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.profile_id, "profile_id")
        _one_of(self.profile_type, {"container", "ssh", "vps", "kubernetes", "cloud", "sandbox"}, "remote_execution_type")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionBudget:
    budget_id: str
    name: str
    max_cost: float
    current_cost: float
    currency: str
    profile_id: str
    enabled: bool
    created_by: str
    created_at: str
    updated_at: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.budget_id, "budget_id")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VectorRecord:
    vector_id: str
    content_hash: str
    content_preview: str
    embedding_model: str
    dimensions: int
    scope: str
    sensitivity: str
    created_at: str
    # JSON-encoded list[float] of the embedding vector; None for legacy/metadata-
    # only records that store no vector.
    embedding: str | None = None
    owner_principal_id: str = ""
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.vector_id, "vector_id")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SymbolNode:
    symbol_id: str
    name: str
    kind: str
    file_path: str
    line_number: int
    module: str
    parent_symbol_id: str | None
    doc_preview: str | None
    created_at: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.symbol_id, "symbol_id")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DependencyEdge:
    edge_id: str
    source_symbol_id: str
    target_symbol_id: str
    dep_type: str
    file_path: str
    line_number: int
    created_at: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.edge_id, "edge_id")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProjectGraph:
    graph_id: str
    workspace_root: str
    module_count: int
    dependency_count: int
    built_at: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.graph_id, "graph_id")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SkillCandidate:
    candidate_id: str
    name: str
    description: str
    source_workflow_json: str
    suggested_tools_json: str
    provenance: str
    status: str
    created_by: str
    created_at: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _schema(self.schema_version)
        _require(self.candidate_id, "candidate_id")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
