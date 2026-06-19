from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Lifecycle events wired into the runtime today. Config referencing anything else is rejected so
# typos are not silently ignored (per docs/HOOKS_SPEC.md).
HOOK_EVENTS = {
    "SessionStart",
    "SessionEnd",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "PostToolUseFailure",
    "PermissionRequest",
    "PermissionDenied",
}
HANDLER_TYPES = {"command", "builtin"}
HOOK_DECISIONS = {"allow", "deny", "ask", "defer", "no_decision", "add_context_only"}
# Highest authority first. A lower scope can never override a higher-scope deny.
HOOK_SCOPES = ("managed", "user", "project", "local", "plugin", "skill", "session")


class HookConfigError(ValueError):
    pass


@dataclass(frozen=True)
class HookHandler:
    id: str
    type: str
    command: list[str] | None = None
    builtin: str | None = None
    args: list[str] = field(default_factory=list)
    timeout_ms: int = 5000
    decision_authority: bool = False

    def __post_init__(self) -> None:
        if not self.id:
            raise HookConfigError("hook_handler_missing_id")
        if self.type not in HANDLER_TYPES:
            raise HookConfigError(f"unsupported_handler_type:{self.type}")
        if self.type == "command" and (
            not isinstance(self.command, list)
            or not self.command
            or not all(isinstance(part, str) and part for part in self.command)
        ):
            raise HookConfigError("command_handler_requires_argv_list")
        if self.type == "builtin" and not self.builtin:
            raise HookConfigError("builtin_handler_requires_name")
        if self.timeout_ms <= 0:
            raise HookConfigError("hook_timeout_must_be_positive")


@dataclass(frozen=True)
class HookRule:
    event: str
    matcher: str
    handlers: list[HookHandler]
    scope: str
    if_guard: str | None = None

    def __post_init__(self) -> None:
        if self.event not in HOOK_EVENTS:
            raise HookConfigError(f"unknown_hook_event:{self.event}")
        if self.scope not in HOOK_SCOPES:
            raise HookConfigError(f"unknown_hook_scope:{self.scope}")
        if not self.handlers:
            raise HookConfigError("hook_rule_requires_handlers")


@dataclass(frozen=True)
class HookInput:
    event_name: str
    tool_name: str | None = None
    tool_input: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    session_id: str | None = None
    turn_id: str | None = None
    cwd: str | None = None


@dataclass(frozen=True)
class HookOutput:
    decision: str = "no_decision"
    decision_reason: str | None = None
    additional_context: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.decision not in HOOK_DECISIONS:
            raise HookConfigError(f"invalid_hook_decision:{self.decision}")


@dataclass(frozen=True)
class HookOutcome:
    decision: str = "no_decision"
    reasons: list[str] = field(default_factory=list)
    additional_context: list[str] = field(default_factory=list)
    executed: list[str] = field(default_factory=list)
