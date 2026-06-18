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
}
INTENTS = {
    "chat",
    "filesystem_query",
    "code_inspection",
    "code_change_request",
    "local_action_request",
    "unknown",
}
RISK_LEVELS = {"low", "medium", "high", "blocked"}
TOOLS = {"read_file", "list_directory", "glob", "grep", "stat_path", "diff_files", "write_file", "edit_file", "apply_patch", "git_status", "git_diff", "git_log", "shell"}
POLICY_DECISIONS = {"allow", "deny", "needs_approval"}
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
        allowed = {"schema_version", "request_id", "session_id", "turn_id", "client", "user", "prompt", "options"}
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
