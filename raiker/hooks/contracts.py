from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Lifecycle events wired into the runtime today. Config referencing anything else is rejected so
# typos are not silently ignored (per docs/architecture/HOOKS_SPEC.md).
HOOK_EVENTS = {
    "SessionStart",
    "SessionEnd",
    "UserPromptSubmit",
    "Stop",
    "StopFailure",
    "PreCompact",
    "PostCompact",
    "PreToolUse",
    "PostToolUse",
    "PostToolUseFailure",
    "PermissionRequest",
    "PermissionDenied",
    "SubagentStart",
    "SubagentStop",
    "TaskCreated",
    "TaskCompleted",
}

#: The events this build actually emits. `HOOK_EVENTS` is what a config file may
#: name; this is what the runtime really dispatches. They are equal on this build
#: (BUG-223) and the machinery that lets them differ is kept, because it is what
#: makes a future gap visible instead of silent.
#:
#: A configured rule that can never run is the worst kind of safeguard: the owner
#: believes a guard is in place and there is nothing to observe that says
#: otherwise. Rather than accept it silently or reject it outright (a config that
#: works on a later build should not fail to parse on this one), the set is
#: published so every surface that lists hooks can mark such a rule as configured
#: but never fired.
#:
#: `tests/test_hooks_surface.py` derives the real call sites from the source and
#: asserts they equal this set, so it cannot drift from the code.
DISPATCHED_HOOK_EVENTS = {
    "SessionStart",
    "SessionEnd",
    "UserPromptSubmit",
    "Stop",
    "StopFailure",
    "PreCompact",
    "PostCompact",
    "PreToolUse",
    "PostToolUse",
    "PostToolUseFailure",
    "PermissionRequest",
    "PermissionDenied",
    "SubagentStart",
    "SubagentStop",
    "TaskCreated",
    "TaskCompleted",
}

#: One line per event, in the owner's language, for the surfaces that list them.
HOOK_EVENT_SUMMARIES = {
    "SessionStart": "A conversation is created.",
    "SessionEnd": "A conversation is archived or deleted.",
    "UserPromptSubmit": "A prompt is submitted, before the turn runs.",
    "Stop": "A turn finished and produced an answer.",
    "StopFailure": "A turn ended without one — it failed, was stopped, or is parked.",
    "PreCompact": "Before older exchanges are compacted out of the context window.",
    "PostCompact": "After compaction, with what it produced.",
    "PreToolUse": "Before policy finalises a tool call. The only event that can change the outcome.",
    "PostToolUse": "A tool call finished successfully.",
    "PostToolUseFailure": "A tool call failed.",
    "PermissionRequest": "An approval is about to be raised.",
    "PermissionDenied": "A tool call was denied.",
    "SubagentStart": "A subagent is about to run, with the objective it was given.",
    "SubagentStop": "A subagent finished, with what it found and whether it succeeded.",
    "TaskCreated": "A task was created.",
    "TaskCompleted": "A task reached a terminal state — done, failed or cancelled.",
}

#: The one event whose decision the runtime honours. Every other event is
#: observation only, so a handler that returns `deny` on `PostToolUse` changes
#: nothing — which the hooks surface has to say rather than imply.
DECIDING_HOOK_EVENTS = {"PreToolUse", "PreCompact"}

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
    #: The file this rule was read from, relative to the workspace.
    #:
    #: Carried on the rule rather than looked up by scope, because scope stopped
    #: identifying a file the moment plugins could contribute (BUG-221): every
    #: installed plugin loads at scope ``plugin``, so "the source for this scope"
    #: would name whichever plugin happened to load first for all of them, and
    #: the Hooks page would credit one plugin with another's rules.
    source: str | None = None

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
