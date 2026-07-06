from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, ClassVar

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
APPROVAL_MODES = {"interactive", "deny_risky", "allow_safe_only"}
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
    "retrieval_augmentation",
    "plan_created",
    "plan_skipped",
    "action_proposed",
    "action_validated",
    "policy_decision",
    "approval_requested",
    "approval_received",
    "approval_denied",
    "tool_started",
    "tool_completed",
    "tool_failed",
    "verification_started",
    "verification_completed",
    "memory_candidate_reviewed",
    "memory_record_created",
    "memory_record_forgotten",
    "response_created",
    "checkpoint_created",
    "turn_closed",
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
    "model_profile_selected",
    "model_capabilities_inspected",
    "reasoning_setting_changed",
    "reasoning_setting_rejected",
    "model_tool_call_rejected",
    "runtime_error_recorded",
    "task_created",
    "task_started",
    "task_progress",
    "task_paused",
    "task_cancelled",
    "task_completed",
    "task_failed",
    "side_question_received",
    "side_question_answered",
    "interrupt_received",
    "safe_boundary_reached",
    "task_steered",
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
TOOLS = {
    "read_file",
    "list_directory",
    "glob",
    "grep",
    "stat_path",
    "diff_files",
    "write_file",
    "edit_file",
    "apply_patch",
    "git_status",
    "git_diff",
    "git_log",
    "memory_write",
    "memory_search",
    "memory_forget",
    "memory_list",
    "memory_get",
    "shell",
}
POLICY_DECISIONS = {"allow", "deny", "needs_approval", "allow_managed"}
MANAGED_POLICY_EFFECTS = {"allow", "deny"}
TOOL_STATUSES = {"success", "failed", "denied", "approval_required"}
RESPONSE_STATUSES = {"completed", "needs_approval", "denied", "failed"}
INTERFACE_STATUS = {"equal_primary_when_enabled"}


class ContractValidationError(ValueError):
    pass


def _require(value: Any, field_name: str) -> None:
    if value is None or value == "":
        raise ContractValidationError(f"missing_required_field:{field_name}")


def _one_of(value: str, allowed: set[str], field_name: str) -> None:
    if value not in allowed:
        raise ContractValidationError(f"invalid_{field_name}:{value}")


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
    approval_mode: str = "interactive"
    model_profile: str = "mock-test"
    max_tool_calls: int = 10

    def __post_init__(self) -> None:
        _one_of(self.planning_mode, PLANNING_MODES, "planning_mode")
        _one_of(self.approval_mode, APPROVAL_MODES, "approval_mode")
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
    "waiting_for_approval",
    "waiting_for_user_answer",
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
