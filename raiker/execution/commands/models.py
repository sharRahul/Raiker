from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


class CommandState(StrEnum):
    QUEUED = "queued"
    STARTING = "starting"
    RUNNING = "running"
    FINALIZING = "finalizing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    CONTAINED = "contained"
    LOST = "lost"


TERMINAL_COMMAND_STATES = frozenset(
    {
        CommandState.SUCCEEDED,
        CommandState.FAILED,
        CommandState.TIMED_OUT,
        CommandState.CANCELLED,
        CommandState.CONTAINED,
        CommandState.LOST,
    }
)

_TRANSITIONS: dict[CommandState, frozenset[CommandState]] = {
    CommandState.QUEUED: frozenset({CommandState.STARTING, CommandState.CANCELLED}),
    CommandState.STARTING: frozenset(
        {CommandState.RUNNING, CommandState.FINALIZING, CommandState.CONTAINED}
    ),
    CommandState.RUNNING: frozenset({CommandState.FINALIZING}),
    CommandState.FINALIZING: TERMINAL_COMMAND_STATES,
}


def can_transition(current: CommandState, target: CommandState) -> bool:
    return target in _TRANSITIONS.get(current, frozenset())


@dataclass(frozen=True)
class CredentialBinding:
    credential_id: str
    environment_name: str

    def __post_init__(self) -> None:
        if not self.credential_id.strip() or not self.environment_name.strip():
            raise ValueError("command_credential_binding_invalid")


@dataclass(frozen=True)
class CommandRequest:
    run_id: str
    owner_principal_id: str
    acting_principal_id: str
    session_id: str
    turn_id: str
    action_id: str
    repository_id: str | None
    workspace_root: Path
    cwd: str
    executable_template: str
    argv_template: tuple[str, ...]
    safe_display: str
    credential_bindings: tuple[CredentialBinding, ...]
    shell: bool
    interactive: bool
    background: bool
    timeout_seconds: float
    max_output_bytes: int
    environment_profile_id: str
    network_policy_id: str | None
    template_digest: str = field(init=False)

    def __post_init__(self) -> None:
        has_shell_template = bool(self.executable_template.strip())
        has_argv_template = bool(self.argv_template)
        if has_shell_template == has_argv_template:
            raise ValueError("command_representation_invalid")
        required = (
            self.run_id,
            self.owner_principal_id,
            self.acting_principal_id,
            self.session_id,
            self.turn_id,
            self.action_id,
            self.environment_profile_id,
        )
        if any(not value.strip() for value in required):
            raise ValueError("command_identity_invalid")
        if self.timeout_seconds <= 0:
            raise ValueError("command_timeout_invalid")
        if self.max_output_bytes <= 0:
            raise ValueError("command_output_limit_invalid")
        if not self.safe_display.strip() or any(char in self.safe_display for char in "\r\n\0"):
            raise ValueError("command_safe_display_invalid")
        if not self._contained_relative_cwd(self.cwd):
            raise ValueError("command_cwd_invalid")
        if has_argv_template and any(not value or "\0" in value for value in self.argv_template):
            raise ValueError("command_argv_invalid")
        material = self.executable_template if has_shell_template else json.dumps(self.argv_template)
        object.__setattr__(self, "workspace_root", Path(self.workspace_root).resolve())
        object.__setattr__(self, "template_digest", hashlib.sha256(material.encode()).hexdigest())

    @staticmethod
    def _contained_relative_cwd(value: str) -> bool:
        if not value or "\0" in value:
            return False
        posix = PurePosixPath(value.replace("\\", "/"))
        windows = PureWindowsPath(value)
        return not posix.is_absolute() and not windows.is_absolute() and ".." not in posix.parts

    def execution_material(self) -> dict[str, Any]:
        return {
            "executable_template": self.executable_template,
            "argv_template": list(self.argv_template),
            "credential_bindings": [
                {
                    "credential_id": binding.credential_id,
                    "environment_name": binding.environment_name,
                }
                for binding in self.credential_bindings
            ],
            "workspace_root": str(self.workspace_root),
            "cwd": self.cwd,
            "shell": self.shell,
            "interactive": self.interactive,
            "background": self.background,
            "timeout_seconds": self.timeout_seconds,
            "max_output_bytes": self.max_output_bytes,
            "network_policy_id": self.network_policy_id,
        }


@dataclass(frozen=True)
class CommandChunk:
    run_id: str
    sequence: int
    stream: str
    text: str
    byte_count: int
    emitted_at: str
    start_byte_offset: int = 0
    end_byte_offset: int = 0

    def __post_init__(self) -> None:
        if self.sequence <= 0 or self.stream not in {"stdout", "stderr", "system"}:
            raise ValueError("command_chunk_invalid")
        if len(self.text.encode("utf-8")) != self.byte_count:
            raise ValueError("command_chunk_byte_count_invalid")
        if self.start_byte_offset < 0 or self.end_byte_offset < 0:
            raise ValueError("command_chunk_offset_invalid")


@dataclass(frozen=True)
class CommandFeatures:
    shell: bool = True
    pty: bool = False
    background: bool = False
    input: bool = False
    process_tree_stop: bool = True
    network_escalation: bool = False
    filtered_network: bool = False
    persistent_environment: bool = False
    persistent: bool = False
    restart_recovery: bool = False
    recoverable: bool = False
    concurrent_runs: bool = False
    credential_delivery: bool = False
    credential_delta_quarantine: bool = False

    def __post_init__(self) -> None:
        if self.credential_delivery and not self.credential_delta_quarantine:
            raise ValueError("credential_delivery_requires_quarantine")


class CommandResolution(StrEnum):
    PENDING = "pending"
    APPLY = "apply"
    DISCARD = "discard"


@dataclass(frozen=True)
class CommandReceipt:
    run_id: str
    state: CommandState
    exit_code: int | None
    termination_reason: str
    completed_at: str
    evidence: dict[str, Any]
    canonical_json: str
    digest: str

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        state: CommandState,
        exit_code: int | None,
        termination_reason: str,
        completed_at: str,
        evidence: dict[str, Any],
    ) -> CommandReceipt:
        if state not in TERMINAL_COMMAND_STATES:
            raise ValueError("command_receipt_state_invalid")
        payload = {
            "completed_at": completed_at,
            "evidence": evidence,
            "exit_code": exit_code,
            "run_id": run_id,
            "state": state.value,
            "termination_reason": termination_reason,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return cls(
            run_id=run_id,
            state=state,
            exit_code=exit_code,
            termination_reason=termination_reason,
            completed_at=completed_at,
            evidence=evidence,
            canonical_json=canonical,
            digest=hashlib.sha256(canonical.encode()).hexdigest(),
        )

    @classmethod
    def from_json(cls, canonical_json: str, digest: str) -> CommandReceipt:
        if hashlib.sha256(canonical_json.encode()).hexdigest() != digest:
            raise ValueError("command_receipt_digest_invalid")
        payload = json.loads(canonical_json)
        return cls(
            run_id=str(payload["run_id"]),
            state=CommandState(payload["state"]),
            exit_code=payload.get("exit_code"),
            termination_reason=str(payload["termination_reason"]),
            completed_at=str(payload["completed_at"]),
            evidence=dict(payload.get("evidence", {})),
            canonical_json=canonical_json,
            digest=digest,
        )


@dataclass(frozen=True)
class StoredCommandRun:
    run_id: str
    owner_principal_id: str
    acting_principal_id: str
    session_id: str
    turn_id: str
    action_id: str
    state: CommandState
    profile_id: str
    backend: str
    safe_display: str
    template_digest: str
    started_at: str | None
    completed_at: str | None
    lease_expires_at: str | None
    exit_code: int | None
    termination_reason: str | None
    stdout_bytes: int
    stderr_bytes: int
    truncated: bool
    redaction_count: int
    receipt_digest: str | None
    created_at: str
    updated_at: str
