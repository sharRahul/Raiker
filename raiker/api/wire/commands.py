# SPDX-License-Identifier: Apache-2.0
"""Governed command runs, their output and receipts, and credential deltas."""

from __future__ import annotations

from typing import Any, Literal, NotRequired

from typing_extensions import TypedDict

CommandRunState = Literal[
    "queued", "starting", "running", "finalizing", "succeeded",
    "failed", "timed_out", "cancelled", "contained", "lost",
]


class CommandRunView(TypedDict):
    """A run as its owner sees it: never the template or the principals behind it."""

    run_id: str
    session_id: str
    turn_id: str
    action_id: str
    authority_kind: str
    authority_id: str
    state: CommandRunState
    profile_id: str
    backend: str
    safe_display: str
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


class CommandChunkView(TypedDict):
    run_id: str
    sequence: int
    stream: Literal["stdout", "stderr", "system"]
    text: str
    byte_count: int
    emitted_at: str
    start_byte_offset: int
    end_byte_offset: int


class CommandReceiptView(TypedDict):
    run_id: str
    state: CommandRunState
    exit_code: int | None
    termination_reason: str
    completed_at: str
    evidence: dict[str, Any]
    digest: str


class CommandRunList(TypedDict):
    runs: list[CommandRunView]


class CommandRunDetail(TypedDict):
    run: CommandRunView


class CommandOutput(TypedDict):
    """Output after a sequence number; ``next_after`` is where the next read starts."""

    chunks: list[CommandChunkView]
    next_after: int


class CommandReceiptAnswer(TypedDict):
    receipt: CommandReceiptView | None


class CommandStopped(TypedDict):
    ok: bool
    run: CommandRunView


class CredentialDeltaFile(TypedDict):
    path: str
    kind: str
    size: NotRequired[int]


class CredentialDeltaManifest(TypedDict):
    files: list[CredentialDeltaFile]


class CredentialDeltaView(TypedDict):
    """Safe metadata only; encrypted handles and matcher material stay internal."""

    run_id: str
    environment_profile_id: str
    state: Literal["scanning", "clean", "quarantined", "resolving", "cleanup_failed"]
    manifest: CredentialDeltaManifest
    delta_digest: str
    scan_digest: str
    scan_rule_version: str
    cleanup_status: str
    created_at: str
    recipient_boundary: Literal["disposable_container_tcb"]


class CredentialDeltaList(TypedDict):
    deltas: list[CredentialDeltaView]


class CredentialDeltaDiscarded(TypedDict):
    ok: bool
    receipt: dict[str, Any] | None
