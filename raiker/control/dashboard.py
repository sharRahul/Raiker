from __future__ import annotations

import difflib
import json
import os
import re
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from raiker.approval_previews import redact_secret_like_text
from raiker.contracts.ids import new_id, utc_now
from raiker.control.dtos import ControlResult
from raiker.control.service import RuntimeControlService
from raiker.events.export import generate_export
from raiker.events.writer import EventLogWriter
from raiker.memory.store import get_memory, list_memory
from raiker.models.endpoint_policy import MODEL_EGRESS_ALLOWLIST_ENV
from raiker.models.exceptions import ModelProviderError, ProviderPolicyError, safe_error
from raiker.models.factory import ModelProviderFactory
from raiker.models.policy_state import (
    HOSTED_MODEL_GATE,
    PRIVATE_NETWORK_MODEL_GATE,
    provider_runtime_policy_from_gates,
)
from raiker.models.registry import ModelProfileRegistry, profile_with_model
from raiker.models.router import ModelRouter
from raiker.models.session_state import TERMINAL_MODEL_SESSION_ID, ModelSessionState
from raiker.runtime.authority.models import PrincipalType
from raiker.runtime.authority.router import CAPABILITY_GATE_MAP
from raiker.security.credentials import CredentialLifecycle, CredentialLifecycleView
from raiker.security.monitoring import SecurityMonitor
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager
from raiker.tasks.scheduler import RECURRING_INTERVALS
from raiker.tools.filesystem import FilesystemSafetyError, proposed_write_snapshot

# Capability states that mean the gate is off / fail-closed.
_DISABLED_STATES = {"disabled", "planned"}

# Cadences a task/schedule may carry. `background` runs one governed cycle now;
# the recurring cadences re-arm after every cycle so a standing agent keeps
# working until the owner stops it. An unknown cadence is refused rather than
# silently stored as a one-shot, which would make a "keep going" schedule stop
# after its first run.
TASK_RECURRENCES = frozenset({"background", *RECURRING_INTERVALS})

# GitHub coordinate shapes. Validation is strict and local — a repository
# reference is stored only when it *could* name a real repository, and no
# network call is made to find out.
_GITHUB_NAME = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,98}[A-Za-z0-9_])?")
_GITHUB_REF = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._/-]{0,98}[A-Za-z0-9_-])?")


@dataclass(frozen=True)
class CodeRepoView:
    """One repository a coding chat can be pointed at.

    A row is a *reference*, not an integration: it stores no credential, opens no
    network connection, and grants no capability. A ``local`` repository is a
    workspace-contained subpath — anything resolving outside the workspace is
    refused (fail closed) — and its files reach a turn as bounded, untrusted
    context through the same governed attachment path as any other workspace
    path. A ``github`` repository records the ``owner/repo`` coordinate only; the
    content is read through the brokered ``github_read`` tool, which stays
    subject to the ``connector_github_runtime`` gate and its decision mode, so
    a reference here never becomes read access on its own.
    """

    repo_id: str
    kind: str
    label: str
    selected: bool
    created_at: str
    local_subpath: str | None = None
    local_exists: bool = False
    github_owner: str | None = None
    github_repo: str | None = None
    branch: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CodeReposView:
    """Every repository reference for one account, plus the honest read posture.

    ``github_gate_state``/``github_decision_mode`` report what the
    ``connector_github_runtime`` gate currently permits, so the interface can say
    whether a connected GitHub repository is actually readable instead of
    implying it is.
    """

    repos: tuple[CodeRepoView, ...]
    selected_repo_id: str | None
    github_gate_state: str
    github_decision_mode: str
    github_token_configured: bool
    note: str = (
        "References only. Connecting a repository grants no capability: a local folder "
        "stays workspace-contained, and every GitHub read still runs through the brokered "
        "github_read tool under the connector_github_runtime gate and its decision mode — "
        "a disabled gate fails closed no matter what is connected here."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "repos": [repo.to_dict() for repo in self.repos],
            "selected_repo_id": self.selected_repo_id,
            "github_gate_state": self.github_gate_state,
            "github_decision_mode": self.github_decision_mode,
            "github_token_configured": self.github_token_configured,
            "note": self.note,
        }


@dataclass(frozen=True)
class SessionView:
    session_id: str
    title: str | None
    status: str
    created_at: str
    updated_at: str
    turn_count: int
    # Conversation organisation: a per-session pin/bookmark flag. Organizing
    # label only — grants nothing and changes no authority.
    pinned: bool = False
    # Conversation organisation remainder: per-session tags. Organizing labels
    # only — like `pinned` and `projects`, they grant nothing and change no
    # gate, policy, or authority. The tuple is the normalized, ordered set
    # (deduplicated, lowercase, length/count-capped).
    tags: tuple[str, ...] = ()
    # The organizing project this chat currently sits in, or None. A chat can
    # be moved in or out; the project grants nothing and only bounds the
    # context the chat receives.
    project_id: str | None = None
    # Soft-archive state (Control Deck task 3). Archiving is a reversible
    # organizing action — it moves a chat out of the default active list but
    # never deletes transcripts, events, checkpoints, or permissions.
    archived: bool = False
    archived_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class McpServerView:
    """Owner-scoped view of one local stdio MCP server profile (Control Deck
    task 4). ``command`` is the argv (interpreter + workspace-relative script);
    it is never a secret or a remote endpoint. Read-only — building or
    connecting a server is a governed runtime action, not a REST mutation."""

    server_id: str
    name: str
    command: tuple[str, ...]
    template: str | None
    transport: str
    status: str
    created_at: str
    last_connected_at: str | None = None
    # Tool names discovered by the last successful handshake (names only —
    # never arguments or output).
    tools: tuple[str, ...] = ()
    tool_count: int = 0
    # Remote (http) connection details. `endpoint_url` is the owner-added URL;
    # `auth_ref` names where the owner token lives (an env var name) — never the
    # token itself. Both are null for a local stdio connection.
    endpoint_url: str | None = None
    auth_ref: str | None = None
    # Containment state (Phase C): `active` | `paused` | `killed`. `paused` is the
    # revocable circuit breaker (auto on a high-severity anomaly, or the owner's
    # one-call stop); `killed` is the instant kill switch. `paused_reason` /
    # `paused_at` are redacted metadata (a rule code + summary, a timestamp).
    monitor_state: str = "active"
    paused_reason: str | None = None
    paused_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SecurityFindingView:
    """Owner-scoped view of one redacted security finding (monitored MCP
    connections, Phase B/C). ``redacted_detail`` holds redacted metadata only
    (labels, counts, hostnames, added/removed tool names) — never a raw value."""

    finding_id: str
    source: str
    severity: str
    code: str
    summary: str
    redacted_detail: dict[str, Any]
    subject_id: str | None
    state: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NotificationView:
    """Owner-scoped view of one notification (Phase C). Redacted human-readable
    copy only; ``finding_id`` / ``subject_id`` link back to what raised it."""

    notification_id: str
    kind: str
    title: str
    body: str
    finding_id: str | None
    subject_id: str | None
    read: bool
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class McpSessionView:
    """Owner-scoped, redacted monitor row for one MCP connection session."""

    session_row_id: str
    server_id: str
    transport: str
    operation: str
    hosts: tuple[str, ...]
    tool_calls: int
    bytes_in: int
    bytes_out: int
    error_count: int
    outcome: str
    started_at: str
    ended_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TurnView:
    turn_id: str
    session_id: str
    turn_type: str
    status: str
    prompt_text: str | None
    created_at: str
    completed_at: str | None
    summary: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SessionDetailView:
    session: SessionView
    turns: tuple[TurnView, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"session": self.session.to_dict(), "turns": [t.to_dict() for t in self.turns]}


@dataclass(frozen=True)
class EventView:
    event_id: str
    session_id: str
    turn_id: str | None
    event_type: str
    actor: str
    timestamp: str
    risk_level: str | None
    summary: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BrainNodeView:
    node_id: str
    node_type: str
    label: str
    status: str
    detail: str | None = None
    progress_percent: int | None = None
    is_real: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BrainEdgeView:
    source: str
    target: str
    relationship: str
    is_active: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BrainView:
    generated_at: str
    nodes: tuple[BrainNodeView, ...]
    edges: tuple[BrainEdgeView, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "illustrative_motion_notice": (
                "Animated pulses indicate visual activity only; every node and connection is stored runtime data."
            ),
        }


@dataclass(frozen=True)
class MemoryControlView:
    """User-facing view of one approved memory entry.

    Carries the governance metadata the user needs to trust, scope, and
    control the memory: provenance, sensitivity, confidence, retention, and
    an organizing pin flag. The text is the stored memory text (the same
    data the governed memory store already persists); no new authority is
    granted by exposing it through this read.
    """

    memory_id: str
    text: str
    scope: str
    sensitivity: str
    memory_type: str
    created_at: str
    tags: tuple[str, ...]
    source: str
    provenance: dict[str, Any]
    confidence: float
    trust_score: float
    retention: str
    approval_state: str
    pinned: bool
    search_enabled: bool = True
    expires_at: str | None = None
    archived_at: str | None = None
    source_event_id: str = ""
    created_by: str = ""
    valid_from: str | None = None
    valid_until: str | None = None
    supersedes_memory_id: str | None = None
    remembered_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "text": self.text,
            "scope": self.scope,
            "sensitivity": self.sensitivity,
            "memory_type": self.memory_type,
            "created_at": self.created_at,
            "tags": list(self.tags),
            "source": self.source,
            "provenance": dict(self.provenance),
            "confidence": self.confidence,
            "trust_score": self.trust_score,
            "retention": self.retention,
            "approval_state": self.approval_state,
            "pinned": self.pinned,
            "search_enabled": self.search_enabled,
            "expires_at": self.expires_at,
            "archived_at": self.archived_at,
            "source_event_id": self.source_event_id,
            "created_by": self.created_by,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "supersedes_memory_id": self.supersedes_memory_id,
            "remembered_reason": self.remembered_reason,
        }


@dataclass(frozen=True)
class MemorySettingsView:
    incognito: bool

    def to_dict(self) -> dict[str, Any]:
        return {"incognito": self.incognito}


@dataclass(frozen=True)
class TurnDetailView:
    turn: TurnView
    events: tuple[EventView, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"turn": self.turn.to_dict(), "events": [e.to_dict() for e in self.events]}


@dataclass(frozen=True)
class CheckpointView:
    checkpoint_id: str
    session_id: str
    turn_id: str | None
    task_id: str | None
    checkpoint_type: str
    created_at: str
    summary: str | None
    last_event_id: str | None
    # "Rewind metadata" — flags only; restore execution is not implemented in this runtime.
    can_restore_state: bool
    can_restore_files: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProjectView:
    # A project is an organizing scope, not an authority: it names a
    # workspace-contained subpath and groups sessions/checkpoints. Selecting or
    # creating one grants nothing.
    project_id: str
    name: str
    root_subpath: str
    created_at: str
    session_count: int
    selected: bool
    # Nested projects/folders: parent reference, materialized path, soft-archive state
    parent_id: str | None = None
    path: str = "/"
    is_archived: bool = False
    archived_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProjectsListView:
    projects: tuple[ProjectView, ...]
    active_project_id: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "projects": [p.to_dict() for p in self.projects],
            "active_project_id": self.active_project_id,
        }


@dataclass(frozen=True)
class ProjectDetailView:
    project: ProjectView
    sessions: tuple[SessionView, ...]
    checkpoints: tuple[CheckpointView, ...]
    context: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project.to_dict(),
            "sessions": [s.to_dict() for s in self.sessions],
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            "context": dict(self.context),
        }


@dataclass(frozen=True)
class TaskView:
    task_id: str
    session_id: str
    status: str
    title: str
    objective: str
    current_step: str | None
    progress_percent: int | None
    created_at: str
    updated_at: str
    completed_at: str | None
    summary: str | None
    priority: str | None = None
    scheduled_at: str | None = None
    recurrence: str | None = None
    reminder_at: str | None = None
    parent_task_id: str | None = None
    # Project-scoped schedules: the organizing project this task was created
    # under, or None when it was created outside every project.
    project_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ModelProfileView:
    profile_id: str
    provider: str
    model: str
    default_state: str
    local_only: bool
    requires_network: bool
    endpoint_kind: str
    requires_egress_policy: bool
    requires_budget_policy: bool
    runtime_gate: str | None
    off_machine: bool
    selected: bool
    connection_configured: bool = False
    # Prompt-cache TTL breakpoint the provider uses for this profile ("5m"/"1h"),
    # or None when the provider/profile does not cache. Read-only status.
    prompt_cache_ttl: str | None = None
    # Context capacity and pricing are configuration-owned facts. They stay
    # unset for placeholder or provider-discovered models rather than guessed.
    context_window_tokens: int | None = None
    configured: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProviderModelListView:
    """On-demand, user-initiated listing of the models a provider serves.

    ``status`` is honest: "available" only when the provider actually answered;
    policy denials and unreachable/unsupported backends return an empty list —
    the view never fabricates model names.
    """

    profile_id: str
    provider: str
    status: str  # "available" | "policy_denied" | "unsupported" | "unavailable"
    reason_code: str | None
    models: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "provider": self.provider,
            "status": self.status,
            "reason_code": self.reason_code,
            "models": list(self.models),
        }


@dataclass(frozen=True)
class ModelsView:
    profiles: tuple[ModelProfileView, ...]
    # Profiles with a concrete configured model are the only choices surfaced
    # by the conversational composer. The full list remains for Models setup.
    chat_profiles: tuple[ModelProfileView, ...]
    current_profile_id: str | None
    hosted_model_gate_state: str
    private_network_model_gate_state: str
    model_egress_allowlist_configured: bool
    remote_profile_count: int
    # User-owned ordered model fallback sequence (profile ids). When the selected
    # provider is unavailable, the runtime walks this list in order; each candidate
    # is still gated by provider policy, so hosted access is never granted silently.
    fallback_sequence: tuple[str, ...] = ()
    # The runtime never silently falls back to hosted providers; hosted runtime is not enabled.
    no_silent_hosted_fallback: bool = True
    # Concrete model bound by the current selection (the persisted per-profile
    # model override when present, else the selected profile's own model).
    # None when nothing is selected or the selection is an unresolved placeholder.
    current_model: str | None = None
    # User-owned advisor model (web-app task 2): the profile a local model may
    # consult through the governed `consult_advisor` tool. Persisting it grants
    # nothing — the consult is gated by advisor_model_runtime + decision mode +
    # provider policy at call time.
    advisor_profile_id: str | None = None
    advisor_model_gate_state: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "profiles": [p.to_dict() for p in self.profiles],
            "chat_profiles": [p.to_dict() for p in self.chat_profiles],
            "current_profile_id": self.current_profile_id,
            "current_model": self.current_model,
            "advisor_profile_id": self.advisor_profile_id,
            "advisor_model_gate_state": self.advisor_model_gate_state,
            "hosted_model_gate_state": self.hosted_model_gate_state,
            "private_network_model_gate_state": self.private_network_model_gate_state,
            "model_egress_allowlist_configured": self.model_egress_allowlist_configured,
            "remote_profile_count": self.remote_profile_count,
            "fallback_sequence": list(self.fallback_sequence),
            "no_silent_hosted_fallback": self.no_silent_hosted_fallback,
        }


@dataclass(frozen=True)
class ConnectorView:
    """Read-only status of one governed service connector (web-app task 4).

    Every field is derived from stored/config state — this view never reaches
    the network and never exposes a credential value (only whether one is set).
    A connector is usable in chat only when its capability gate is enabled AND
    its decision mode is raised to ``allow`` AND the owner credential is set AND
    its host is on the connector egress allowlist; each condition is reported
    honestly so the owner can see exactly what is still fail-closed.
    """

    connector_id: str
    display_name: str
    capability: str
    gate_state: str
    capability_enabled: bool
    decision_mode: str
    # Owner credential presence only — the value (an API token) is never read out.
    credential_env: str
    credential_configured: bool
    egress_host: str
    egress_allowed: bool
    # Read-only summary of what actions this connector exposes and their kind.
    actions: tuple[str, ...]
    kind: str = "read_only"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConnectionsView:
    connectors: tuple[ConnectorView, ...]
    # True when the owner has set RAIKER_CONNECTOR_EGRESS_ALLOWLIST at all.
    connector_egress_allowlist_configured: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "connectors": [c.to_dict() for c in self.connectors],
            "connector_egress_allowlist_configured": self.connector_egress_allowlist_configured,
        }


@dataclass(frozen=True)
class ProviderHealthView:
    profile_id: str
    provider: str
    model: str
    endpoint_kind: str
    local_only: bool
    requires_network: bool
    selected: bool
    # Derived from configuration only — reachability is NOT probed here (no network side effects
    # on a read). Live reachability is checked on demand via the CLI (`/model-health`).
    status: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DiagnosticsView:
    runtime_mode: str
    production_ready_local_single_user_runtime: bool
    summary: dict[str, Any]
    disabled_capabilities: tuple[str, ...]
    counts: dict[str, int]
    # M6 additions — an honest readiness/diagnostics surface derived from stored state only.
    readiness: dict[str, Any] = field(default_factory=dict)
    missing_config: tuple[str, ...] = ()
    provider_health: tuple[ProviderHealthView, ...] = ()
    scope_note: str = "Status reflects the local single-user runtime only."

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_mode": self.runtime_mode,
            "production_ready_local_single_user_runtime": self.production_ready_local_single_user_runtime,
            "summary": dict(self.summary),
            "disabled_capabilities": list(self.disabled_capabilities),
            "counts": dict(self.counts),
            "readiness": dict(self.readiness),
            "missing_config": list(self.missing_config),
            "provider_health": [p.to_dict() for p in self.provider_health],
            "scope_note": self.scope_note,
        }


@dataclass(frozen=True)
class ApprovalView:
    approval_id: str
    action_id: str
    status: str
    tool_name: str
    capability: str
    risk_level: str
    session_id: str
    turn_id: str | None
    created_at: str
    age_seconds: int | None
    requires_approval: bool
    # The browser displays this server-reported snapshot; the resolve endpoint
    # re-checks the TTL before recording any decision.
    expires_at: str | None
    is_expired: bool
    # Resolving an approval records a decision; it never executes the action.
    executes_action: bool = False
    # Critical approvals use the elevated, human-only RuntimeAuthority lifecycle.
    critical: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ApprovalDetailView:
    approval: ApprovalView
    # Redacted, metadata-only preview of the proposed action's arguments.
    arguments: dict[str, Any]
    # Unified diff for file-mutation proposals (write_file/edit_file); None otherwise.
    diff: str | None
    diff_path: str | None
    # "file_diff" | "patch" | "arguments" — tells the UI how to render the preview.
    preview_kind: str
    metadata_only_notice: str = (
        "Approval resolution is metadata-only. Recording a decision does NOT execute the action."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "approval": self.approval.to_dict(),
            "arguments": dict(self.arguments),
            "diff": self.diff,
            "diff_path": self.diff_path,
            "preview_kind": self.preview_kind,
            "metadata_only_notice": self.metadata_only_notice,
        }


@dataclass(frozen=True)
class AuthSessionView:
    # The only response that intentionally contains a token. Never logged; held in memory by the SPA.
    token: str
    session_id: str
    principal_id: str
    expires_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AuthError:
    ok: bool = False
    reason_code: str = "auth_failed"
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DashboardService:
    """Read-only governed views for the web UI. Reuses storage and control services; never mutates."""

    def __init__(self, workspace_root: str | Path = ".") -> None:
        self.workspace_root = Path(workspace_root)
        self.store = SQLiteStore(self.workspace_root)
        self.control = RuntimeControlService(self.workspace_root)

    def _workspace_source(self, raw_path: str) -> tuple[str, Path]:
        candidate = raw_path.strip()
        if not candidate or len(candidate) > 512:
            raise ValueError("invalid_brain_source_path")
        root = self.workspace_root.resolve()
        path = (root / candidate).resolve()
        if path != root and root not in path.parents:
            raise ValueError("brain_source_outside_workspace")
        if not path.exists():
            raise ValueError("brain_source_not_found")
        return str(path.relative_to(root)), path

    def add_brain_source(self, raw_path: str, *, owner_principal_id: str) -> dict[str, Any]:
        relative_path, _path = self._workspace_source(raw_path)
        self.store.add_brain_source(owner_principal_id, relative_path)
        return {"ok": True, "path": relative_path}

    def remove_brain_source(self, raw_path: str, *, owner_principal_id: str) -> dict[str, Any]:
        try:
            relative_path, _path = self._workspace_source(raw_path)
        except ValueError:
            relative_path = raw_path.strip()
        self.store.remove_brain_source(owner_principal_id, relative_path)
        return {"ok": True, "path": relative_path}

    # ── Code workspace repositories ─────────────────────────────────────
    # The Build workspace points a coding chat at a repository. Connecting one is
    # governance-neutral bookkeeping: a local folder must resolve inside the
    # workspace (fail closed), a GitHub repository records only its `owner/repo`
    # coordinate, and neither stores a credential nor grants a capability. GitHub
    # content still reaches a turn only through the brokered `github_read` tool
    # under the `connector_github_runtime` gate, which is disabled/fail-closed
    # until the owner enables it.

    def list_code_repos(self, *, owner_principal_id: str) -> CodeReposView:
        from raiker.runtime.connectors import GITHUB_TOKEN_ENV

        gate = self.control.get_capability_gate("connector_github_runtime", owner_principal_id)
        rows = self.store.list_code_repos(owner_principal_id)
        return CodeReposView(
            repos=tuple(self._code_repo_view(row) for row in rows),
            selected_repo_id=next(
                (str(row["repo_id"]) for row in rows if row.get("selected")), None
            ),
            github_gate_state=gate.state if gate is not None else "unknown",
            github_decision_mode=gate.decision_mode if gate is not None else "ask",
            github_token_configured=bool(os.environ.get(GITHUB_TOKEN_ENV, "").strip()),
        )

    def _code_repo_view(self, row: dict[str, Any]) -> CodeRepoView:
        local_subpath = row.get("local_subpath")
        exists = False
        if local_subpath:
            candidate = (self.workspace_root / str(local_subpath)).resolve()
            root = self.workspace_root.resolve()
            exists = (candidate == root or root in candidate.parents) and candidate.is_dir()
        return CodeRepoView(
            repo_id=str(row["repo_id"]),
            kind=str(row["kind"]),
            label=str(row["label"]),
            selected=bool(row.get("selected")),
            created_at=str(row["created_at"]),
            local_subpath=str(local_subpath) if local_subpath else None,
            local_exists=exists,
            github_owner=str(row["github_owner"]) if row.get("github_owner") else None,
            github_repo=str(row["github_repo"]) if row.get("github_repo") else None,
            branch=str(row["branch"]) if row.get("branch") else None,
        )

    def connect_local_repo(
        self, raw_path: str, *, owner_principal_id: str, user_id: str | None = None
    ) -> ControlResult:
        """Reference a workspace-contained folder as a repository.

        Reuses the same containment check as every other workspace path read:
        a path that resolves outside the workspace, or does not exist, is refused.
        """
        try:
            relative_path, path = self._workspace_source(raw_path)
        except ValueError as exc:
            reason = str(exc).replace("brain_source", "repo")
            return ControlResult(ok=False, reason_code=reason)
        if not path.is_dir():
            return ControlResult(ok=False, reason_code="repo_not_a_directory")
        repo_id = new_id("repo_")
        label = Path(relative_path).name or relative_path
        if not self.store.insert_code_repo(
            repo_id=repo_id,
            owner_principal_id=owner_principal_id,
            kind="local",
            label=label,
            local_subpath=relative_path,
        ):
            return ControlResult(ok=False, reason_code="repo_already_connected")
        self._record_repo_event(
            "code_repo_connected",
            owner_principal_id,
            user_id,
            {"repo_id": repo_id, "kind": "local", "local_subpath": relative_path},
        )
        return ControlResult(
            ok=True, data={"repo_id": repo_id, "kind": "local", "local_subpath": relative_path}
        )

    def connect_github_repo(
        self,
        owner: str,
        repo: str,
        branch: str | None,
        *,
        owner_principal_id: str,
        user_id: str | None = None,
    ) -> ControlResult:
        """Record a GitHub `owner/repo` coordinate. Performs no network call.

        Reads against it later go through the brokered ``github_read`` tool, so a
        disabled ``connector_github_runtime`` gate still fails closed.
        """
        clean_owner = owner.strip()
        clean_repo = repo.strip()
        clean_branch = (branch or "").strip() or None
        if not _GITHUB_NAME.fullmatch(clean_owner) or not _GITHUB_NAME.fullmatch(clean_repo):
            return ControlResult(ok=False, reason_code="invalid_github_repo")
        if clean_branch is not None and not _GITHUB_REF.fullmatch(clean_branch):
            return ControlResult(ok=False, reason_code="invalid_github_branch")
        repo_id = new_id("repo_")
        if not self.store.insert_code_repo(
            repo_id=repo_id,
            owner_principal_id=owner_principal_id,
            kind="github",
            label=f"{clean_owner}/{clean_repo}",
            github_owner=clean_owner,
            github_repo=clean_repo,
            branch=clean_branch,
        ):
            return ControlResult(ok=False, reason_code="repo_already_connected")
        self._record_repo_event(
            "code_repo_connected",
            owner_principal_id,
            user_id,
            {
                "repo_id": repo_id,
                "kind": "github",
                "github_owner": clean_owner,
                "github_repo": clean_repo,
                "branch": clean_branch or "",
            },
        )
        return ControlResult(
            ok=True,
            data={
                "repo_id": repo_id,
                "kind": "github",
                "label": f"{clean_owner}/{clean_repo}",
                "branch": clean_branch,
            },
        )

    def disconnect_code_repo(
        self, repo_id: str, *, owner_principal_id: str, user_id: str | None = None
    ) -> ControlResult:
        """Forget a repository reference. Never touches the folder or the remote."""
        if not self.store.delete_code_repo(owner_principal_id, repo_id):
            return ControlResult(ok=False, reason_code="unknown_repo")
        self._record_repo_event(
            "code_repo_disconnected", owner_principal_id, user_id, {"repo_id": repo_id}
        )
        return ControlResult(ok=True, data={"repo_id": repo_id})

    def select_code_repo(
        self, repo_id: str | None, *, owner_principal_id: str
    ) -> ControlResult:
        """Point the Build workspace at one repository, or at none with ``None``."""
        if repo_id is not None and self.store.load_code_repo(owner_principal_id, repo_id) is None:
            return ControlResult(ok=False, reason_code="unknown_repo")
        self.store.select_code_repo(owner_principal_id, repo_id)
        return ControlResult(ok=True, data={"selected_repo_id": repo_id})

    def _record_repo_event(
        self,
        event_type: str,
        owner_principal_id: str,
        user_id: str | None,
        payload: dict[str, Any],
    ) -> None:
        """Audit one repository reference change in the account's Inbox session.

        The Inbox session is created the same way scheduled work creates it, so
        the record is visible to the account that made the change rather than
        landing in a session nobody can read.
        """
        from raiker.events.types import make_event

        session_id = f"sess_inbox_{owner_principal_id}"
        self.store.create_session(
            session_id, str(self.store.paths.workspace_root), title="Inbox", user_id=user_id
        )
        EventLogWriter(self.store).append(
            make_event(
                session_id=session_id,
                turn_id=None,
                event_type=event_type,
                actor="dashboard_service",
                payload={**payload, "principal_id": owner_principal_id},
            )
        )

    # ── Sessions / turns ────────────────────────────────────────────────
    def list_sessions(
        self,
        limit: int = 50,
        project_id: str | None = None,
        user_id: str | None = None,
        include_archived: bool = False,
    ) -> list[SessionView]:
        return [
            self._session_view(row)
            for row in self.store.list_sessions(
                limit=limit,
                project_id=project_id,
                user_id=user_id,
                include_archived=include_archived,
            )
        ]

    def brain_view(self, *, principal_id: str, user_id: str | None) -> BrainView:
        """A redacted, read-only relationship graph for the authenticated user."""
        sessions = self.list_sessions(limit=100, user_id=user_id)
        session_ids = {session.session_id for session in sessions}
        tasks = self.list_tasks(user_id=user_id)
        task_ids = {task.task_id for task in tasks}
        tasks_by_id = {task.task_id: task for task in tasks}
        events = [
            self._event_view(row)
            for row in self.store.list_event_index(limit=250)
            if str(row.get("session_id", "")) in session_ids
        ]
        approvals = [
            self._approval_view(row)
            for row in self.store.list_approvals()
            if str(row.get("session_id", "")) in session_ids
        ]
        subagents = [
            row for row in self.store.list_subagent_contracts()
            if str(row.get("parent_task_id", "")) in task_ids
        ]
        memories = list_memory(
            workspace_root=self.workspace_root, store=self.store, limit=100,
            owner_principal_id=principal_id,
        )
        backups = [
            row for row in self.store.list_backup_manifests()
            if str(row.get("created_by", "")) == principal_id
        ]
        nodes = [BrainNodeView(f"principal:{principal_id}", "user", "You", "active")]
        edges: list[BrainEdgeView] = []
        for session in sessions:
            node_id = f"session:{session.session_id}"
            nodes.append(BrainNodeView(node_id, "session", session.title or "Untitled session", session.status))
            edges.append(BrainEdgeView(f"principal:{principal_id}", node_id, "owns"))
        for task in tasks:
            node_id = f"task:{task.task_id}"
            nodes.append(BrainNodeView(node_id, "task", task.title or "Untitled task", task.status, task.current_step, task.progress_percent))
            edges.append(BrainEdgeView(f"session:{task.session_id}", node_id, "tracks", task.status == "running"))
            if task.scheduled_at:
                schedule_id = f"schedule:{task.task_id}"
                nodes.append(BrainNodeView(schedule_id, "schedule", "Scheduled work", "waiting", task.scheduled_at))
                edges.append(BrainEdgeView(schedule_id, node_id, "starts"))
        for agent in subagents:
            node_id = f"agent:{agent['subagent_id']}"
            parent_task = tasks_by_id.get(str(agent["parent_task_id"]))
            nodes.append(
                BrainNodeView(
                    node_id,
                    "agent",
                    str(agent["name"]),
                    str(agent["status"]),
                    parent_task.title if parent_task else None,
                )
            )
            edges.append(BrainEdgeView(f"task:{agent['parent_task_id']}", node_id, "delegates", str(agent["status"]) == "running"))
        event_ids = {event.event_id for event in events}
        for event in events:
            node_id = f"event:{event.event_id}"
            nodes.append(BrainNodeView(node_id, "tool", event.event_type.replace("_", " "), "recorded", event.summary))
            edges.append(BrainEdgeView(f"session:{event.session_id}", node_id, "recorded"))
        for memory in memories:
            node_id = f"memory:{memory.memory_id}"
            nodes.append(BrainNodeView(node_id, "memory", f"Memory · {memory.scope}", "available", memory.sensitivity))
            if memory.source_event_id in event_ids:
                edges.append(BrainEdgeView(f"event:{memory.source_event_id}", node_id, "remembered"))
        for approval in approvals:
            node_id = f"approval:{approval.approval_id}"
            nodes.append(BrainNodeView(node_id, "approval", approval.tool_name, approval.status, approval.capability))
            edges.append(BrainEdgeView(f"session:{approval.session_id}", node_id, "requires"))
        for backup in backups:
            node_id = f"backup:{backup['manifest_id']}"
            nodes.append(BrainNodeView(node_id, "backup", "Backup", "verified" if backup.get("restore_verified_at") else "catalogued"))
            edges.append(BrainEdgeView(f"principal:{principal_id}", node_id, "backs_up"))
        root = self.workspace_root.resolve()
        for source in self.store.list_brain_sources(principal_id):
            try:
                relative_path, path = self._workspace_source(source)
            except ValueError:
                continue
            source_id = f"source:{relative_path}"
            source_type = "folder" if path.is_dir() else "file"
            nodes.append(BrainNodeView(source_id, source_type, path.name or relative_path, "selected", relative_path))
            edges.append(BrainEdgeView(f"principal:{principal_id}", source_id, "added"))
            if path.is_dir():
                try:
                    children = sorted(path.iterdir(), key=lambda child: child.name.casefold())[:100]
                except OSError:
                    children = []
                for child in children:
                    child_path = child.resolve().relative_to(root).as_posix()
                    child_id = f"source:{child_path}"
                    child_type = "folder" if child.is_dir() else "file"
                    nodes.append(BrainNodeView(child_id, child_type, child.name, "available", child_path))
                    edges.append(BrainEdgeView(source_id, child_id, "contains"))
        return BrainView(utc_now(), tuple(nodes), tuple(edges))

    def get_session(
        self, session_id: str, user_id: str | None = None
    ) -> SessionDetailView | None:
        row = self.store.load_session(session_id)
        if row is None:
            return None
        # Isolation: an account cannot read another account's session. Legacy
        # sessions (no owner) remain visible to any authenticated account.
        owner = row.get("user_id")
        if user_id is not None and owner is not None and str(owner) != user_id:
            return None
        turns = tuple(self._turn_view(t) for t in self.store.list_turns(session_id))
        return SessionDetailView(session=self._session_view(row), turns=turns)

    def search_sessions(self, query: str, user_id: str | None = None) -> list[SessionView]:
        return [self._session_view(row) for row in self.store.search_sessions(query.strip(), user_id)]

    def get_turn(self, turn_id: str, user_id: str | None = None) -> TurnDetailView | None:
        row = self.store.load_turn(turn_id)
        if row is None:
            return None
        session = self.store.load_session(str(row["session_id"]))
        if session is None:
            return None
        owner = session.get("user_id")
        if user_id is not None and owner is not None and str(owner) != user_id:
            return None
        events = tuple(
            self._event_view(e) for e in self.store.list_event_index(turn_id=turn_id, limit=500)
        )
        return TurnDetailView(turn=self._turn_view(row), events=events)

    # ── Session organisation (pin/bookmark + delete) ──────────────────────
    # These are organizing actions, governance-neutral like projects: pinning
    # or deleting a session grants nothing and changes no gate, policy, or
    # authority. Deletion is human-only and respects the same user/session
    # visibility boundary as every governed read — an account cannot delete
    # another account's session, and legacy unattributed sessions remain
    # deletable by any authenticated human.

    def set_session_pinned(
        self,
        session_id: str,
        pinned: bool,
        acting_principal_id: str | None,
    ) -> ControlResult:
        """Pin (or unpin) a session for the authenticated local human.

        Pinned sessions surface first in the Sessions list. Pinning is an
        organizing label only — it grants nothing.
        """
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        user_id = principal.delegated_by_user_id
        if not self.store.set_session_pinned(session_id, pinned, user_id=user_id):
            return ControlResult(ok=False, reason_code=f"unknown_session:{session_id}")
        return ControlResult(
            ok=True, data={"session_id": session_id, "pinned": pinned}
        )

    # ── Safe session rename / archive lifecycle (Control Deck task 3) ────────
    # Renaming and archiving are organizing actions only — they grant nothing
    # and change no gate, policy, or authority. Both are human-only and respect
    # the same user/session visibility boundary as set_session_pinned: an
    # account cannot rename or archive another account's session. Archiving is
    # reversible and never deletes transcripts, events, checkpoints, or
    # permissions; deletion remains a separate, confirmed, destructive path.

    _TITLE_MAX_LEN = 200

    def _normalize_title(self, title: str) -> tuple[str | None, str | None]:
        """Return (normalized_title, reason_code). reason_code is None when the
        title is acceptable. Trim, collapse internal whitespace (so control
        characters and newlines cannot smuggle into a display label), reject
        empty, and cap length."""
        if not isinstance(title, str):
            return None, "invalid_title:not_a_string"
        normalized = re.sub(r"\s+", " ", title.strip())
        if not normalized:
            return None, "invalid_title:empty"
        if len(normalized) > self._TITLE_MAX_LEN:
            return None, f"invalid_title:too_long:{len(normalized)}"
        return normalized, None

    def rename_session(
        self, session_id: str, title: str, acting_principal_id: str | None
    ) -> ControlResult:
        """Rename one session (human-only).

        The title is normalized (trim, collapse whitespace, length cap) and
        rejected with ``invalid_title:*`` when empty or too long. Renaming is an
        organizing label only — it grants nothing. Respects user/session
        visibility: an account cannot rename another account's session.
        """
        normalized, reason = self._normalize_title(title)
        if reason is not None or normalized is None:
            return ControlResult(ok=False, reason_code=reason)
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        user_id = principal.delegated_by_user_id
        session = self.store.load_session(session_id)
        previous_title = str(session["title"]) if session and session.get("title") else None
        if not self.store.rename_session(session_id, normalized, user_id=user_id):
            return ControlResult(ok=False, reason_code=f"unknown_session:{session_id}")
        from raiker.events.types import make_event

        EventLogWriter(self.store).append(
            make_event(
                session_id=session_id,
                turn_id=None,
                event_type="session_renamed",
                actor="dashboard_service",
                payload={
                    "session_id": session_id,
                    "from_title": previous_title,
                    "to_title": normalized,
                },
            )
        )
        return ControlResult(
            ok=True, data={"session_id": session_id, "title": normalized}
        )

    def set_session_archived(
        self, session_id: str, archived: bool, acting_principal_id: str | None
    ) -> ControlResult:
        """Archive or restore one session (human-only).

        Archiving moves a chat out of the default active list and is fully
        reversible; it never deletes transcripts, events, checkpoints, or
        permissions. Respects user/session visibility: an account cannot
        archive another account's session.
        """
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        user_id = principal.delegated_by_user_id
        if not self.store.set_session_archived(session_id, archived, user_id=user_id):
            return ControlResult(ok=False, reason_code=f"unknown_session:{session_id}")
        from raiker.events.types import make_event

        EventLogWriter(self.store).append(
            make_event(
                session_id=session_id,
                turn_id=None,
                event_type="session_archived" if archived else "session_unarchived",
                actor="dashboard_service",
                payload={"session_id": session_id, "archived": archived},
            )
        )
        return ControlResult(
            ok=True, data={"session_id": session_id, "archived": archived}
        )

    # ── Governed local MCP server profiles (Control Deck task 4) ─────────────
    def list_mcp_servers(self, principal_id: str) -> list[McpServerView]:
        """Owner-scoped, read-only list of the caller's local MCP server
        profiles. Building or connecting a server is a governed runtime action
        (through the authority/executor path), never a plain REST mutation, so
        this surface is read-only by design."""
        return [
            McpServerView(
                server_id=str(row["server_id"]),
                name=str(row["name"]),
                command=tuple(str(part) for part in row.get("command", [])),
                template=row.get("template"),
                transport=str(row.get("transport", "stdio")),
                status=str(row.get("status", "created")),
                created_at=str(row.get("created_at", "")),
                last_connected_at=row.get("last_connected_at"),
                tools=tuple(str(t) for t in row.get("tools", [])),
                tool_count=int(row.get("tool_count", 0) or 0),
                endpoint_url=row.get("endpoint_url"),
                auth_ref=row.get("auth_ref"),
                monitor_state=str(row.get("monitor_state") or "active"),
                paused_reason=row.get("paused_reason"),
                paused_at=row.get("paused_at"),
            )
            for row in self.store.list_mcp_servers(principal_id)
        ]

    def create_mcp_server(
        self, acting_principal_id: str | None, name: str, template: str
    ) -> ControlResult:
        """Governed build of a local stdio MCP server (delegates to the
        control service so the capability gate / policy / audit path applies)."""
        return self.control.create_mcp_server(acting_principal_id, name, template)

    def create_remote_mcp_server(
        self, acting_principal_id: str | None, name: str, endpoint_url: str, auth_ref: str | None
    ) -> ControlResult:
        """Add an owner-scoped remote (HTTP) MCP connection (delegates)."""
        return self.control.create_remote_mcp_server(
            acting_principal_id, name, endpoint_url, auth_ref
        )

    def connect_mcp_server(
        self, acting_principal_id: str | None, server_id: str
    ) -> ControlResult:
        """Governed test-connect of a stored MCP server (delegates)."""
        return self.control.connect_mcp_server(acting_principal_id, server_id)

    def rename_mcp_server(
        self, acting_principal_id: str | None, server_id: str, name: str
    ) -> ControlResult:
        """Owner-scoped, human-only rename of one MCP server profile."""
        return self.control.rename_mcp_server(acting_principal_id, server_id, name)

    def delete_mcp_server(
        self, acting_principal_id: str | None, server_id: str
    ) -> ControlResult:
        """Owner-scoped, human-only delete of one MCP server profile."""
        return self.control.delete_mcp_server(acting_principal_id, server_id)

    # ── Containment + findings + notifications (Phase C) ─────────────────────
    def pause_mcp_server(
        self, acting_principal_id: str | None, server_id: str, reason: str | None = None
    ) -> ControlResult:
        """Owner-scoped, human-only one-call stop of a connection (delegates)."""
        return self.control.pause_mcp_server(acting_principal_id, server_id, reason)

    def resume_mcp_server(
        self, acting_principal_id: str | None, server_id: str
    ) -> ControlResult:
        """Owner-scoped, human-only resume of a paused/killed connection."""
        return self.control.resume_mcp_server(acting_principal_id, server_id)

    def kill_mcp_server(
        self, acting_principal_id: str | None, server_id: str, reason: str | None = None
    ) -> ControlResult:
        """Owner-scoped, human-only instant kill switch (delegates)."""
        return self.control.kill_mcp_server(acting_principal_id, server_id, reason)

    def list_mcp_findings(
        self, principal_id: str, server_id: str | None = None
    ) -> list[SecurityFindingView]:
        """Owner-scoped redacted findings, newest first, optionally scoped to one
        connection. Read-only view — never exposes a raw value."""
        return [
            SecurityFindingView(
                finding_id=str(row["finding_id"]),
                source=str(row.get("source", "")),
                severity=str(row.get("severity", "")),
                code=str(row.get("code", "")),
                summary=str(row.get("summary", "")),
                redacted_detail=dict(row.get("redacted_detail", {}) or {}),
                subject_id=row.get("subject_id"),
                state=str(row.get("state", "open")),
                created_at=str(row.get("created_at", "")),
            )
            for row in self.store.list_security_findings(
                principal_id, source="mcp_monitor", subject_id=server_id
            )
        ]

    def list_notifications(
        self, principal_id: str, unread_only: bool = False
    ) -> list[NotificationView]:
        """Owner-scoped notifications, newest first."""
        return [
            NotificationView(
                notification_id=str(row["notification_id"]),
                kind=str(row.get("kind", "")),
                title=str(row.get("title", "")),
                body=str(row.get("body", "")),
                finding_id=row.get("finding_id"),
                subject_id=row.get("subject_id"),
                read=bool(row.get("read", 0)),
                created_at=str(row.get("created_at", "")),
            )
            for row in self.store.list_notifications(principal_id, unread_only=unread_only)
        ]

    def list_security_credentials(self, principal_id: str) -> list[CredentialLifecycleView]:
        return CredentialLifecycle(self.store).list(principal_id)

    def verify_security_credential(self, principal_id: str, provider: str) -> CredentialLifecycleView:
        return CredentialLifecycle(self.store).verify_replacement(principal_id, provider)

    def scan_security(self, principal_id: str) -> list[SecurityFindingView]:
        SecurityMonitor(self.store, self.workspace_root).scan_configured_paths(principal_id)
        return self.list_security_findings(principal_id)

    def check_security_health(self, principal_id: str) -> list[dict[str, Any]]:
        SecurityMonitor(self.store, self.workspace_root).check_vault_health(principal_id)
        return self.list_security_health(principal_id)

    def list_security_health(self, principal_id: str) -> list[dict[str, Any]]:
        """Return the last recorded monitor state without performing a check."""
        return self.store.list_security_monitor_state(principal_id)

    def check_password_breach(
        self, principal_id: str, password: str, *, enabled: bool
    ) -> list[SecurityFindingView]:
        SecurityMonitor(self.store, self.workspace_root).check_password_breach(
            principal_id, password, enabled=enabled
        )
        return self.list_security_findings(principal_id)

    def list_security_findings(self, principal_id: str) -> list[SecurityFindingView]:
        return [
            SecurityFindingView(
                finding_id=str(row["finding_id"]), source=str(row.get("source", "")),
                severity=str(row.get("severity", "")), code=str(row.get("code", "")),
                summary=str(row.get("summary", "")),
                redacted_detail=dict(row.get("redacted_detail", {}) or {}),
                subject_id=row.get("subject_id"), state=str(row.get("state", "open")),
                created_at=str(row.get("created_at", "")),
            )
            for row in self.store.list_security_findings(principal_id)
        ]

    def list_mcp_sessions(self, principal_id: str, server_id: str) -> list[McpSessionView]:
        """Owner-scoped, redacted recent monitor sessions for one MCP connection."""
        return [
            McpSessionView(
                session_row_id=str(row["session_row_id"]),
                server_id=str(row["server_id"]),
                transport=str(row["transport"]),
                operation=str(row["operation"]),
                hosts=tuple(str(host) for host in row.get("hosts", [])),
                tool_calls=int(row["tool_calls"]),
                bytes_in=int(row["bytes_in"]),
                bytes_out=int(row["bytes_out"]),
                error_count=int(row["error_count"]),
                outcome=str(row["outcome"]),
                started_at=str(row["started_at"]),
                ended_at=row.get("ended_at"),
            )
            for row in self.store.list_mcp_session_logs(server_id, principal_id, limit=10)
        ]

    def mark_notification_read(
        self, notification_id: str, principal_id: str
    ) -> ControlResult:
        """Owner-scoped mark-as-read for one notification."""
        ok = self.store.mark_notification_read(notification_id, principal_id)
        return ControlResult(ok=ok, reason_code=None if ok else "unknown_notification")

    def delete_session(
        self, session_id: str, acting_principal_id: str | None
    ) -> ControlResult:
        """Permanently delete one session and its cascaded rows (human-only).

        Respects user/session visibility: an account cannot delete another
        account's session. The per-session events transcript file is removed.
        """
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        user_id = principal.delegated_by_user_id
        if not self.store.delete_session(session_id, user_id=user_id):
            return ControlResult(ok=False, reason_code=f"unknown_session:{session_id}")
        return ControlResult(ok=True, data={"session_id": session_id})

    def delete_sessions(self, session_ids: list[str], acting_principal_id: str | None) -> ControlResult:
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        if not self.store.delete_sessions(session_ids, user_id=principal.delegated_by_user_id):
            return ControlResult(ok=False, reason_code="unknown_or_unauthorized_session")
        return ControlResult(ok=True, data={"session_ids": session_ids})

    def set_session_project(
        self, session_id: str, project_id: str | None, acting_principal_id: str | None
    ) -> ControlResult:
        """Move one chat into a project, or out of every project (human-only).

        A project is an organizing scope: the move grants nothing and changes
        no gate, policy, or authority. It changes only the bounded context the
        chat receives — project instructions, shared attachments, and the
        opt-in approved-memory boundary. Moving out (``project_id=None``)
        removes all of it from the next turn's context. Respects user/session
        visibility: an account cannot move another account's chat.
        """
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        user_id = self.store.principal_user_id(principal.principal_id)
        if project_id is not None and self.store.load_project(project_id, user_id=user_id) is None:
            return ControlResult(ok=False, reason_code=f"unknown_project:{project_id}")
        session = self.store.load_session(session_id)
        previous_project_id = str(session["project_id"]) if session and session.get("project_id") else None
        if not self.store.set_session_project(session_id, project_id, user_id=user_id):
            return ControlResult(ok=False, reason_code=f"unknown_session:{session_id}")
        from raiker.events.types import make_event

        EventLogWriter(self.store).append(
            make_event(
                session_id=session_id,
                turn_id=None,
                event_type="session_project_changed",
                actor="dashboard_service",
                payload={
                    "session_id": session_id,
                    "from_project_id": previous_project_id,
                    "to_project_id": project_id,
                },
            )
        )
        return ControlResult(
            ok=True, data={"session_id": session_id, "project_id": project_id}
        )

    # ── Session tags (conversation organisation remainder) ──────────────────
    # A tag is an organizing label only (like the per-session `pinned` flag
    # and the `projects` table) — it grants nothing and changes no gate,
    # policy, or authority. Mutations are human-only and respect the same
    # user/session visibility boundary as set_session_pinned / delete_session
    # — an account cannot retag another account's session. Normalization is
    # applied here so the storage layer never sees an unvalidated tag: trim,
    # collapse internal whitespace, lowercase, allow `[a-z0-9][a-z0-9 _-]*`,
    # 1..32 chars each, max 12 tags per session, dedupe, drop empties.

    _TAG_MAX_LEN = 32
    _TAG_MAX_COUNT = 12
    _TAG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9 &._-]*$")

    def _normalize_tags(self, tags: list[str]) -> tuple[tuple[str, ...], str | None]:
        """Return (normalized, reason_code). reason_code is None when the
        tag set is acceptable."""
        seen: set[str] = set()
        out: list[str] = []
        for raw in tags:
            if not isinstance(raw, str):
                return (), "invalid_tag:not_a_string"
            tag = re.sub(r"\s+", " ", raw.strip()).lower()
            if not tag:
                continue
            if len(tag) > self._TAG_MAX_LEN:
                return (), f"invalid_tag:too_long:{tag[:16]}"
            if not self._TAG_PATTERN.match(tag):
                return (), f"invalid_tag:bad_chars:{tag[:16]}"
            if tag not in seen:
                seen.add(tag)
                out.append(tag)
        if len(out) > self._TAG_MAX_COUNT:
            return (), f"invalid_tag:too_many:{len(out)}"
        return tuple(out), None

    def set_session_tags(
        self,
        session_id: str,
        tags: list[str],
        acting_principal_id: str | None,
    ) -> ControlResult:
        """Replace the tag set for one session (human-only).

        Tags are organizing labels only — they grant nothing. The supplied
        list is normalized (trim, lowercase, dedupe, length/count caps) and
        stored as the session's full tag set. Respects user/session
        visibility: an account cannot retag another account's session.
        """
        normalized, reason = self._normalize_tags(tags)
        if reason is not None:
            return ControlResult(ok=False, reason_code=reason)
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        user_id = principal.delegated_by_user_id
        if not self.store.set_session_tags(session_id, list(normalized), user_id=user_id):
            return ControlResult(ok=False, reason_code=f"unknown_session:{session_id}")
        return ControlResult(
            ok=True,
            data={"session_id": session_id, "tags": list(normalized)},
        )

    # ── Reliable memory controls (backlog item 3) ──────────────────────────
    # The user-facing surface over the EXISTING governed memory store — list
    # with provenance/scope/sensitivity, pin (organizing label only), forget
    # (human-only, reuses the governed forget path), and an incognito opt-out
    # boundary that withholds approved project memory from the turn context.
    # No second memory system is created; these read/control the same store
    # the memory_write/memory_forget tools already use.

    def list_memories(
        self, scope: str | None = None, *, acting_principal_id: str | None = None
    ) -> list[MemoryControlView]:
        """List approved memories with their governance metadata + pin state."""
        pinned_ids = self.store.list_pinned_memory_ids()
        entries = list_memory(
            workspace_root=self.workspace_root,
            scope=scope,
            limit=200,
            store=self.store,
            include_search_disabled=True,
            owner_principal_id=acting_principal_id,
        )
        views = [
            MemoryControlView(
                memory_id=e.memory_id,
                text=e.text,
                scope=e.scope,
                sensitivity=e.sensitivity,
                memory_type=e.memory_type,
                created_at=e.created_at,
                tags=e.tags,
                source=e.source,
                provenance=e.provenance,
                confidence=e.confidence,
                trust_score=e.trust_score,
                retention=e.retention,
                approval_state=e.approval_state,
                pinned=e.memory_id in pinned_ids,
                search_enabled=e.search_enabled,
                expires_at=e.expires_at,
                archived_at=e.archived_at,
                source_event_id=e.source_event_id,
                created_by=e.created_by,
                valid_from=e.valid_from,
                valid_until=e.valid_until,
                supersedes_memory_id=e.supersedes_memory_id,
                remembered_reason=e.remembered_reason,
            )
            for e in entries
        ]
        if acting_principal_id:
            self.store.record_memory_lifecycle_event(
                "workspace_memory_control", "admin_access", acting_principal_id,
                {"operation": "list", "scope": scope, "memory_count": len(views)},
            )
        return views

    def set_memory_pinned(
        self, memory_id: str, pinned: bool, acting_principal_id: str | None
    ) -> ControlResult:
        """Pin (or unpin) a memory. Organizing label only — grants nothing."""
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        if get_memory(memory_id, workspace_root=self.workspace_root, owner_principal_id=principal.principal_id) is None:
            return ControlResult(ok=False, reason_code=f"unknown_memory:{memory_id}")
        self.store.set_memory_pinned(memory_id, pinned)
        return ControlResult(ok=True, data={"memory_id": memory_id, "pinned": pinned})

    def forget_memory_controlled(
        self, memory_id: str, acting_principal_id: str | None
    ) -> ControlResult:
        """Forget a memory through the governed path (human-only).

        Reuses the existing ``forget_memory`` store function which writes a
        tombstone and marks the db row forgotten. No new authority is
        granted — the human owner may always forget their own memories.
        """
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        from raiker.memory.store import MemoryForgetGovernance, forget_memory

        governance = MemoryForgetGovernance(
            source_event_id=new_id("evt_"),
            source_session_id="",
            source_turn_id=None,
            source_type="user_ui",
            deleted_by=principal.principal_id,
        )
        ok = forget_memory(
            memory_id,
            workspace_root=self.workspace_root,
            store=self.store,
            governance=governance,
            owner_principal_id=principal.principal_id,
        )
        if not ok:
            return ControlResult(ok=False, reason_code=f"unknown_memory:{memory_id}")
        self.store.record_memory_lifecycle_event(memory_id, "forget", principal.principal_id)
        return ControlResult(ok=True, data={"memory_id": memory_id})

    def set_memory_archived(self, memory_id: str, archived: bool, acting_principal_id: str | None) -> ControlResult:
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        from raiker.memory.store import set_memory_archived
        entry = set_memory_archived(memory_id, archived=archived, workspace_root=self.workspace_root, store=self.store, owner_principal_id=acting_principal_id)
        if entry is None:
            return ControlResult(ok=False, reason_code=f"unknown_memory:{memory_id}")
        self.store.record_memory_lifecycle_event(memory_id, "archive" if archived else "restore", acting_principal_id or "")
        return ControlResult(ok=True, data={"memory_id": memory_id, "archived": archived})

    def preview_memory_purge(self, memory_id: str, acting_principal_id: str | None) -> ControlResult:
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        from raiker.memory.store import get_memory
        memory = get_memory(memory_id, workspace_root=self.workspace_root, include_expired=True, include_archived=True, owner_principal_id=acting_principal_id)
        if memory is None:
            return ControlResult(ok=False, reason_code=f"unknown_memory:{memory_id}")
        return ControlResult(ok=True, data={"memory_id": memory_id, "artifacts": [str(self.workspace_root / ".raiker" / "memory" / f"{memory_id}.md")], "backup_disposition": "retained backups are not immediately erased", "requires_confirmation": memory_id})

    def purge_memory(self, memory_id: str, confirmation: str | None, acting_principal_id: str | None) -> ControlResult:
        preview = self.preview_memory_purge(memory_id, acting_principal_id)
        if not preview.ok:
            return preview
        if confirmation != memory_id:
            return ControlResult(ok=False, reason_code="memory_purge_confirmation_required")
        from raiker.contracts.ids import utc_now
        path = self.workspace_root / ".raiker" / "memory" / f"{memory_id}.md"
        path.unlink(missing_ok=True)
        projections = self.store.list_memory_projections(memory_id)
        self.store.deactivate_memory_projections(memory_id)
        self.store.delete_approved_memory(memory_id, owner_principal_id=acting_principal_id)
        disposition = {**preview.data, "projections": projections, "completed_storage_locations": ["markdown_export", "sqlite_approved_memory", "sqlite_fts", "projection_mappings"]}
        self.store.create_memory_purge_record(new_id("pur_"), memory_id, acting_principal_id or "", utc_now(), disposition)
        self.store.record_memory_lifecycle_event(memory_id, "purge", acting_principal_id or "", disposition)
        return ControlResult(ok=True, data={"memory_id": memory_id, "purged": True, "backup_disposition": preview.data["backup_disposition"]})

    def edit_memory_controlled(self, memory_id: str, text: str, acting_principal_id: str | None) -> ControlResult:
        return self._update_memory_controlled(
            memory_id, text=text, search_enabled=None, acting_principal_id=acting_principal_id
        )

    def correct_memory_controlled(
        self, memory_id: str, text: str, reason: str, acting_principal_id: str | None
    ) -> ControlResult:
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        from raiker.memory.store import MemoryGovernance, correct_memory

        replacement = correct_memory(
            memory_id, text, workspace_root=self.workspace_root, store=self.store,
            remembered_reason=reason,
            owner_principal_id=self.store.account_scope(acting_principal_id),
            governance=MemoryGovernance(
                source_event_id=new_id("evt_"), source_session_id="", source_turn_id=None,
                source_type="human_correction", confidence=1.0, trust_score=1.0,
                retention="until_forget", approval_state="approved", created_by=acting_principal_id or "",
            ),
        )
        if replacement is None:
            return ControlResult(ok=False, reason_code="invalid_memory_correction")
        self.store.record_memory_lifecycle_event(memory_id, "correct", acting_principal_id or "", {"replacement_memory_id": replacement.memory_id, "reason": reason})
        return ControlResult(ok=True, data={"memory_id": replacement.memory_id, "supersedes_memory_id": memory_id})

    def set_memory_search_enabled(self, memory_id: str, search_enabled: bool, acting_principal_id: str | None) -> ControlResult:
        return self._update_memory_controlled(
            memory_id, text=None, search_enabled=search_enabled, acting_principal_id=acting_principal_id
        )

    def set_memory_expiry(self, memory_id: str, expires_at: str | None, acting_principal_id: str | None) -> ControlResult:
        return self._update_memory_controlled(
            memory_id,
            text=None,
            search_enabled=None,
            expires_at=expires_at,
            update_expires_at=True,
            acting_principal_id=acting_principal_id,
        )

    def export_memories(self, acting_principal_id: str | None) -> ControlResult:
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        memories = [m.to_dict() for m in self.list_memories(acting_principal_id=acting_principal_id)]
        self.store.record_memory_lifecycle_event(
            "workspace_memory_export", "export", acting_principal_id or "", {"memory_count": len(memories)}
        )
        return ControlResult(ok=True, data={"memories": memories})

    def import_memories(self, memories: list[dict[str, Any]], acting_principal_id: str | None) -> ControlResult:
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        from raiker.memory.store import MemoryGovernance, update_memory, write_memory
        for item in memories:
            text = str(item.get("text", "")).strip()
            if not text:
                return ControlResult(ok=False, reason_code="empty_memory_text")
            entry = write_memory(
                text,
                workspace_root=self.workspace_root,
                scope=str(item.get("scope", "project")),
                store=self.store,
                governance=MemoryGovernance(
                    new_id("evt_"), "", None, "user_import", 1.0, 1.0,
                    str(item.get("retention", "until_forget")), "approved", acting_principal_id or "",
                ),
                owner_principal_id=acting_principal_id,
            )
            update_memory(
                entry.memory_id,
                workspace_root=self.workspace_root,
                search_enabled=bool(item.get("search_enabled", True)),
                expires_at=item.get("expires_at"),
                update_expires_at="expires_at" in item,
                store=self.store,
                owner_principal_id=acting_principal_id,
            )
            self.store.record_memory_lifecycle_event(
                entry.memory_id, "import", acting_principal_id or "", {"source": "user_import"}
            )
        return ControlResult(ok=True, data={"count": len(memories)})

    def reconcile_memory_indexes(self, acting_principal_id: str | None) -> ControlResult:
        """Owner-started repair; never runs as an autonomous background worker."""
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        return ControlResult(ok=True, data=self.store.reconcile_memory_projections(owner_principal_id=acting_principal_id))

    def cleanup_expired_observations(
        self, observation_ids: set[str], now: str, acting_principal_id: str | None
    ) -> ControlResult:
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        from raiker.memory.eidetic import cleanup_expired_observations

        try:
            deleted = cleanup_expired_observations(
                store=self.store, now=now, confirmed_ids=observation_ids
            )
        except PermissionError as error:
            return ControlResult(ok=False, reason_code=str(error))
        return ControlResult(ok=True, data={"deleted_observation_ids": deleted})

    def _is_human(self, acting_principal_id: str | None) -> bool:
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        return principal is not None and principal.principal_type == PrincipalType.HUMAN

    def _update_memory_controlled(
        self,
        memory_id: str,
        *,
        text: str | None,
        search_enabled: bool | None,
        acting_principal_id: str | None,
        expires_at: str | None = None,
        update_expires_at: bool = False,
    ) -> ControlResult:
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        if text is not None and not text.strip():
            return ControlResult(ok=False, reason_code="empty_memory_text")
        from raiker.memory.store import update_memory
        updated = update_memory(
            memory_id,
            workspace_root=self.workspace_root,
            text=text,
            search_enabled=search_enabled,
            expires_at=expires_at,
            update_expires_at=update_expires_at,
            store=self.store,
            owner_principal_id=acting_principal_id,
        )
        if updated is None:
            return ControlResult(ok=False, reason_code=f"unknown_memory:{memory_id}")
        return ControlResult(
            ok=True,
            data={
                "memory_id": memory_id,
                "search_enabled": updated.search_enabled,
                "expires_at": updated.expires_at,
            },
        )

    def get_memory_settings(self, acting_principal_id: str | None = None) -> MemorySettingsView:
        return MemorySettingsView(incognito=self.store.is_memory_incognito(acting_principal_id))

    def set_memory_incognito(
        self, incognito: bool, acting_principal_id: str | None
    ) -> ControlResult:
        """Toggle the incognito opt-out boundary (human-only).

        When on, the context gatherer withholds approved project memory from
        the turn context even if a project opted in. The memory is not
        deleted — only excluded from the model's view.
        """
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        self.store.set_memory_incognito(incognito, principal.principal_id)
        return ControlResult(ok=True, data={"incognito": incognito})

    # ── Events / checkpoints / tasks ────────────────────────────────────
    def list_events(
        self,
        session_id: str | None = None,
        turn_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
        user_id: str | None = None,
    ) -> list[EventView]:
        rows = self.store.list_event_index(
            session_id=session_id, turn_id=turn_id, event_type=event_type, limit=limit
        )
        if user_id is None:
            return [self._event_view(r) for r in rows]
        # Archiving a session never hides its events (archive is not delete), so
        # the visibility set spans the owner's active and archived sessions.
        visible_session_ids = {
            str(session["session_id"])
            for session in self.store.list_sessions(
                limit=10_000, user_id=user_id, include_archived=True
            )
        }
        return [self._event_view(r) for r in rows if str(r.get("session_id")) in visible_session_ids]

    def list_checkpoints(
        self, session_id: str | None = None, limit: int = 50, project_id: str | None = None, user_id: str | None = None
    ) -> list[CheckpointView]:
        return [
            self._checkpoint_view(r)
            for r in self.store.list_checkpoints(session_id, limit=limit, project_id=project_id)
            if (session := self.store.load_session(str(r["session_id"]))) is not None
            and (user_id is None or session.get("user_id") == user_id)
        ]

    def get_checkpoint(self, checkpoint_id: str, user_id: str | None = None) -> CheckpointView | None:
        row = self.store.load_checkpoint_by_id(checkpoint_id)
        if row is None:
            return None
        session = self.store.load_session(str(row["session_id"]))
        if session is None or (user_id is not None and session.get("user_id") != user_id):
            return None
        return self._checkpoint_view(row)

    # ── Projects (web-app task 5) ────────────────────────────────────────
    # A project is a named organizing scope: a workspace-contained subpath plus
    # the sessions (and their checkpoints) created while it is active. It is
    # deliberately governance-neutral — creating or selecting a project grants
    # no capability, and every path stays inside the workspace, fail-closed.

    _PROJECT_NAME_MAX = 100

    def list_projects(self, user_id: str | None = None) -> ProjectsListView:
        active = self.store.get_active_project(user_id)
        return ProjectsListView(
            projects=tuple(self._project_view(row, active) for row in self.store.list_projects(user_id)),
            active_project_id=active,
        )

    def get_project(self, project_id: str, user_id: str | None = None) -> ProjectDetailView | None:
        row = self.store.load_project(project_id, user_id)
        if row is None:
            return None
        active = self.store.get_active_project(user_id)
        sessions = tuple(
            self._session_view(s) for s in self.store.list_sessions(limit=200, project_id=project_id, user_id=user_id)
        )
        checkpoints = tuple(
            self._checkpoint_view(c) for c in self.store.list_checkpoints(project_id=project_id)
        )
        row["session_count"] = len(sessions)
        return ProjectDetailView(
            project=self._project_view(row, active),
            sessions=sessions,
            checkpoints=checkpoints,
            context=self.store.load_project_context(project_id),
        )

    def export_project(
        self, project_id: str, acting_principal_id: str | None
    ) -> ControlResult:
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        if self.store.load_project(project_id, principal.delegated_by_user_id) is None:
            return ControlResult(ok=False, reason_code=f"unknown_project:{project_id}")
        manifest = generate_export(
            self.store,
            project_id=project_id,
            user_id=principal.delegated_by_user_id,
            apply_user_visibility_filter=True,
        )
        return ControlResult(ok=True, data={"export_path": manifest.export_path})

    def create_project(self, name: str, acting_principal_id: str | None, parent_id: str | None = None) -> ControlResult:
        """Create a named project folder (human gate-manager only).

        The root subpath is derived server-side from the name (slug under
        ``projects/``) and verified to stay inside the workspace — a name can
        never place a project root outside it (fail closed). When
        ``parent_id`` is supplied the project is created as a nested child of
        that parent folder.
        """
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        cleaned = (name or "").strip()
        if not cleaned or len(cleaned) > self._PROJECT_NAME_MAX:
            return ControlResult(ok=False, reason_code="invalid_project_name")
        slug = re.sub(r"[^a-z0-9]+", "-", cleaned.lower()).strip("-")
        if not slug:
            return ControlResult(ok=False, reason_code="invalid_project_name")
        if self.store.load_project_by_name(cleaned) is not None:
            return ControlResult(ok=False, reason_code="duplicate_project_name")
        if parent_id is not None and self.store.load_project(parent_id, principal.delegated_by_user_id) is None:
            return ControlResult(ok=False, reason_code=f"unknown_parent:{parent_id}")
        root_subpath = f"projects/{slug}"
        workspace = self.workspace_root.resolve()
        resolved = (workspace / root_subpath).resolve()
        if workspace != resolved and workspace not in resolved.parents:
            return ControlResult(ok=False, reason_code="project_root_escapes_workspace")
        if any(p.get("root_subpath") == root_subpath for p in self.store.list_projects(principal.delegated_by_user_id)):
            return ControlResult(ok=False, reason_code="duplicate_project_root")
        project_id = new_id("proj_")
        resolved.mkdir(parents=True, exist_ok=True)
        self.store.create_project(project_id, cleaned, root_subpath, parent_id=parent_id, owner_user_id=principal.delegated_by_user_id)
        return ControlResult(
            ok=True,
            data={"project_id": project_id, "name": cleaned, "root_subpath": root_subpath, "parent_id": parent_id},
        )

    def select_project(self, project_id: str | None, acting_principal_id: str | None) -> ControlResult:
        """Set (or clear, with null/empty) the active project (human gate-manager only).

        New sessions are stamped with the active project. Selecting grants
        nothing — it is an organizing scope only.
        """
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        cleaned = (project_id or "").strip()
        if not cleaned:
            self.store.save_active_project(None, principal.delegated_by_user_id)
            return ControlResult(ok=True, data={"active_project_id": None})
        if self.store.load_project(cleaned, principal.delegated_by_user_id) is None:
            return ControlResult(ok=False, reason_code=f"unknown_project:{cleaned}")
        self.store.save_active_project(cleaned, principal.delegated_by_user_id)
        return ControlResult(ok=True, data={"active_project_id": cleaned})

    def delete_project(self, project_id: str, acting_principal_id: str | None, confirm: bool = False) -> ControlResult:
        """Human-only hard delete with orphanage cascade. Requires confirmed=True."""
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        if not confirm:
            return ControlResult(ok=False, reason_code="project_delete_confirmation_required")
        project = self.store.load_project(project_id, principal.delegated_by_user_id)
        if project is None:
            return ControlResult(ok=False, reason_code=f"unknown_project:{project_id}")
        root = (self.workspace_root.resolve() / str(project["root_subpath"])).resolve()
        if self.workspace_root.resolve() not in root.parents:
            return ControlResult(ok=False, reason_code="project_root_escapes_workspace")
        if not self.store.delete_project_with_orphanage(project_id):
            return ControlResult(ok=False, reason_code=f"unknown_project:{project_id}")
        try:
            shutil.rmtree(root)
        except FileNotFoundError:
            pass
        except OSError:
            return ControlResult(ok=False, reason_code="project_folder_delete_failed")
        return ControlResult(ok=True, data={"project_id": project_id})

    def save_project_context(
        self,
        project_id: str,
        *,
        instructions: str,
        attachment_ids: list[str],
        memory_enabled: bool | None = None,
        memory_mode: str | None = None,
        acting_principal_id: str | None,
    ) -> ControlResult:
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        if self.store.load_project(project_id, principal.delegated_by_user_id) is None:
            return ControlResult(ok=False, reason_code=f"unknown_project:{project_id}")
        cleaned = instructions.strip()
        if len(cleaned) > 4000:
            return ControlResult(ok=False, reason_code="project_instructions_too_long")
        unique_ids = list(dict.fromkeys(item.strip() for item in attachment_ids if item.strip()))
        if len(unique_ids) > 20:
            return ControlResult(ok=False, reason_code="too_many_project_attachments")
        if any(
            self.store.load_attachment_metadata(
                attachment_id, owner_principal_id=principal.principal_id
            ) is None
            for attachment_id in unique_ids
        ):
            return ControlResult(ok=False, reason_code="unknown_project_attachment")
        self.store.save_project_context(
            project_id,
            instructions=cleaned,
            attachment_ids=unique_ids,
            memory_enabled=memory_enabled,
            memory_mode=memory_mode,
            owner_principal_id=principal.principal_id,
        )
        context = self.store.load_project_context(project_id)
        return ControlResult(
            ok=True, data=context,
        )

    # ── Nested projects/folders (conversation organisation remainder) ─────
    # Organizing scopes only — like all project operations, they grant nothing
    # and change no gate, policy, or authority.

    def list_project_tree(self, user_id: str | None = None) -> list[dict]:
        """Return the full project tree (active, non-archived only)."""
        return self.store.list_project_tree(user_id=user_id)

    def archive_project(self, project_id: str, acting_principal_id: str | None) -> ControlResult:
        """AI-autonomous soft-archive of a project subtree. No confirmation required."""
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if self.store.load_project(project_id, principal.delegated_by_user_id) is None:
            return ControlResult(ok=False, reason_code=f"unknown_project:{project_id}")
        self.store.archive_project(project_id)
        return ControlResult(ok=True, data={"project_id": project_id, "archived": True})

    def move_project(self, project_id: str, new_parent_id: str | None, acting_principal_id: str | None) -> ControlResult:
        """Move a project to a new parent (human-only)."""
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        if self.store.load_project(project_id, principal.delegated_by_user_id) is None:
            return ControlResult(ok=False, reason_code=f"unknown_project:{project_id}")
        if new_parent_id is not None and self.store.load_project(new_parent_id, principal.delegated_by_user_id) is None:
            return ControlResult(ok=False, reason_code=f"unknown_parent:{new_parent_id}")
        ok = self.store.move_project(project_id, new_parent_id)
        if not ok:
            return ControlResult(ok=False, reason_code="move_failed_or_cycle")
        return ControlResult(ok=True, data={"project_id": project_id, "new_parent_id": new_parent_id})

    def get_session_context(self, session_id: str) -> dict:
        """Return the session's effective project context (ancestors merged in).

        This is the same merge the live context gatherer applies, so what the
        dashboard shows is what the model sees.
        """
        session = self.store.load_session(session_id)
        if session is None:
            return {}
        project_id = session.get("project_id")
        if not project_id:
            return {}
        return self.store.load_effective_project_context(str(project_id))

    def _project_view(self, row: dict[str, Any], active_project_id: str | None) -> ProjectView:
        return ProjectView(
            project_id=str(row["project_id"]),
            name=str(row["name"]),
            root_subpath=str(row["root_subpath"]),
            created_at=str(row.get("created_at", "")),
            session_count=int(row.get("session_count", 0) or 0),
            selected=(str(row["project_id"]) == active_project_id),
            parent_id=row.get("parent_id"),
            path=str(row.get("path", "/")),
            is_archived=bool(row.get("is_archived", 0)),
            archived_at=row.get("archived_at"),
        )

    def list_tasks(
        self,
        session_id: str | None = None,
        status: str | None = None,
        user_id: str | None = None,
        project_id: str | None = None,
    ) -> list[TaskView]:
        # The user-facing work queue lists only tasks the user created. Each chat
        # turn also spawns an internal governance task (``parent_turn_id`` set);
        # those are surfaced in Sessions/Audit, not here, so they no longer
        # inflate the open/scheduled/finished counters or appear as selectable
        # "Parent work" (FIX-06). Interrupts operate on the raw store list, so a
        # running chat turn can still be stopped.
        return [
            self._task_view(t)
            for t in self.store.list_tasks(
                session_id=session_id, status=status, user_id=user_id, project_id=project_id
            )
            if not getattr(t, "parent_turn_id", None)
        ]

    def create_task(
        self,
        *,
        title: str,
        objective: str,
        user_id: str | None,
        principal_id: str,
        priority: str | None = None,
        scheduled_at: str | None = None,
        recurrence: str | None = None,
        reminder_at: str | None = None,
        parent_task_id: str | None = None,
        project_id: str | None = None,
    ) -> TaskView:
        """Create a local planning task in the caller's server-owned Inbox session.

        Project-scoped schedules: the task is stamped with ``project_id`` when
        given, else with the active project, so a schedule created inside a
        project stays scoped to it. The stamp is an organizing label — it
        grants nothing.
        """
        if recurrence is not None and recurrence not in TASK_RECURRENCES:
            raise ValueError(f"invalid_recurrence:{recurrence}")
        # An unscheduled task is work requested now; the resident host claims
        # it on its next scheduler tick. Explicit times remain untouched.
        if scheduled_at is None:
            scheduled_at = utc_now()
        if project_id is None:
            project_id = self.store.get_active_project(user_id)
        elif self.store.load_project(project_id, user_id) is None:
            raise ValueError(f"unknown_project:{project_id}")
        if parent_task_id is not None:
            parent = self.store.load_task(parent_task_id)
            parent_session = self.store.load_session(parent.session_id) if parent is not None else None
            if parent is None or parent_session is None or (
                user_id is not None
                and parent_session.get("user_id") not in (None, user_id)
            ):
                raise ValueError(f"unknown_parent_task:{parent_task_id}")
        inbox_session_id = f"sess_inbox_{principal_id}"
        self.store.create_session(
            inbox_session_id,
            str(self.store.paths.workspace_root),
            title="Inbox",
            user_id=user_id,
        )
        task = TaskManager(self.store, EventLogWriter(self.store)).create_task(
            session_id=inbox_session_id,
            title=title,
            objective=objective,
            priority=priority,
            scheduled_at=scheduled_at,
            recurrence=recurrence,
            reminder_at=reminder_at,
            parent_task_id=parent_task_id,
            project_id=project_id,
        )
        return self._task_view(task)

    # ── Approvals (read-only views; resolution lives in ApprovalInbox) ───
    def list_approvals(
        self,
        status: str = "pending",
        *,
        user_id: str | None = None,
        principal_id: str | None = None,
    ) -> list[ApprovalView]:
        return [
            self._approval_view(row)
            for row in self.store.list_approvals(
                status=status, user_id=user_id, principal_id=principal_id
            )
        ]

    def get_approval(
        self,
        approval_id: str,
        *,
        user_id: str | None = None,
        principal_id: str | None = None,
    ) -> ApprovalDetailView | None:
        row = self.store.load_approval(
            approval_id, user_id=user_id, principal_id=principal_id
        )
        if row is None:
            return None
        return self._approval_detail(row)

    # ── Models / diagnostics ────────────────────────────────────────────
    def get_models(self, acting_principal_id: str | None = None) -> ModelsView:
        registry = ModelProfileRegistry.load()
        scoped_principal = (
            acting_principal_id
            if acting_principal_id and self.store.get_account(acting_principal_id) is not None
            else None
        )
        state = (
            self.store.load_principal_model_state(scoped_principal)
            if scoped_principal else self.store.load_model_session_state(TERMINAL_MODEL_SESSION_ID)
        )
        current = state.profile_id if state is not None else None
        # The persisted per-profile model override (e.g. an Ollama/OpenAI model
        # picked at selection time) is what the runtime actually binds, so the
        # selected profile card shows it instead of the profile's placeholder.
        override = state.model if state is not None and state.model else None
        hosted_gate = self.control.get_capability_gate(HOSTED_MODEL_GATE, acting_principal_id)
        private_gate = self.control.get_capability_gate(PRIVATE_NETWORK_MODEL_GATE, acting_principal_id)
        advisor_gate = self.control.get_capability_gate("advisor_model_runtime", acting_principal_id)
        from raiker.models.connections import get_model_connection

        profiles = tuple(
            ModelProfileView(
                profile_id=p.profile_id,
                provider=p.provider,
                model=(override if override and p.profile_id == current else p.model),
                default_state=p.default_state,
                local_only=p.local_only,
                requires_network=p.requires_network,
                endpoint_kind=str(p.raw.get("endpoint_kind", "unknown")),
                requires_egress_policy=bool(p.raw.get("requires_egress_policy", False)),
                requires_budget_policy=bool(p.raw.get("requires_budget_policy", False)),
                runtime_gate=self._runtime_gate_for_profile(str(p.raw.get("endpoint_kind", "unknown"))),
                off_machine=str(p.raw.get("endpoint_kind", "unknown")) in {"remote_hosted", "private_network"},
                selected=(p.profile_id == current),
                connection_configured=bool(
                    acting_principal_id
                    and get_model_connection(self.store, acting_principal_id, p.profile_id)
                ),
                prompt_cache_ttl=(str(p.raw.get("prompt_cache_ttl")) if p.raw.get("prompt_cache_ttl") else None),
                context_window_tokens=(
                    int(p.raw["context_window_tokens"])
                    if isinstance(p.raw.get("context_window_tokens"), int)
                    and not isinstance(p.raw.get("context_window_tokens"), bool)
                    and int(p.raw["context_window_tokens"]) > 0
                    else None
                ),
                configured=(
                    (override if override and p.profile_id == current else p.model) != "<model>"
                ),
            )
            for p in registry.list_profiles()
            # Test-harness profiles (mock/deterministic) are not selectable outside
            # test mode (the provider factory fails closed), so the web surface
            # lists working backends only.
            if not bool(p.raw.get("test_only", False))
            and not bool(p.raw.get("setup_hidden", False))
        )
        return ModelsView(
            profiles=profiles,
            chat_profiles=tuple(profile for profile in profiles if profile.configured),
            current_profile_id=current,
            hosted_model_gate_state=hosted_gate.state if hosted_gate is not None else "unknown",
            private_network_model_gate_state=private_gate.state if private_gate is not None else "unknown",
            model_egress_allowlist_configured=bool(
                os.environ.get(MODEL_EGRESS_ALLOWLIST_ENV, "").strip()
            ),
            remote_profile_count=sum(1 for p in profiles if p.off_machine),
            fallback_sequence=tuple(
                self.store.load_principal_model_fallback_sequence(scoped_principal)
                if scoped_principal else self.store.load_model_fallback_sequence(TERMINAL_MODEL_SESSION_ID)
            ),
            current_model=self._current_model(registry, state),
            advisor_profile_id=(
                self.store.load_principal_model_advisor(scoped_principal)
                if scoped_principal else self.store.load_model_advisor(TERMINAL_MODEL_SESSION_ID)
            ),
            advisor_model_gate_state=advisor_gate.state if advisor_gate is not None else "unknown",
        )

    # ── Connections (governed service connectors — web-app task 4) ───────
    def get_connections(self, acting_principal_id: str | None = None) -> ConnectionsView:
        """Read-only status of every governed service connector.

        Never reaches the network and never exposes a credential value. Each
        connector reports its capability gate state, decision mode, whether the
        owner credential env is set, and whether its host is on the connector
        egress allowlist — so the owner can see exactly what is still
        fail-closed. Enabling a connector is done through the existing capability
        gate + decision-mode control plane (gate-manager only), not here.
        """
        from raiker.runtime.connectors import (
            GCAL_HOST,
            GCAL_TOKEN_ENV,
            GITHUB_HOST,
            GITHUB_TOKEN_ENV,
            GMAIL_HOST,
            GMAIL_TOKEN_ENV,
            SLACK_HOST,
            SLACK_TOKEN_ENV,
        )
        from raiker.runtime.executors.sandbox import connector_egress_allowlist

        allowlist = connector_egress_allowlist()
        connectors: list[ConnectorView] = []
        gh_gate = self.control.get_capability_gate(
            "connector_github_runtime", acting_principal_id
        )
        connectors.append(
            ConnectorView(
                connector_id="github",
                display_name="GitHub (read-only)",
                capability="connector_github_runtime",
                gate_state=gh_gate.state if gh_gate is not None else "unknown",
                capability_enabled=bool(gh_gate.runtime_enabled) if gh_gate is not None else False,
                decision_mode=gh_gate.decision_mode if gh_gate is not None else "ask",
                credential_env=GITHUB_TOKEN_ENV,
                credential_configured=bool(os.environ.get(GITHUB_TOKEN_ENV, "").strip()),
                egress_host=GITHUB_HOST,
                egress_allowed=GITHUB_HOST in allowlist,
                actions=("read_issue", "read_pull_request"),
                kind="read_only",
            )
        )
        gmail_gate = self.control.get_capability_gate(
            "connector_gmail_runtime", acting_principal_id
        )
        connectors.append(
            ConnectorView(
                connector_id="gmail",
                display_name="Gmail (read-only)",
                capability="connector_gmail_runtime",
                gate_state=gmail_gate.state if gmail_gate is not None else "unknown",
                capability_enabled=(
                    bool(gmail_gate.runtime_enabled) if gmail_gate is not None else False
                ),
                decision_mode=gmail_gate.decision_mode if gmail_gate is not None else "ask",
                credential_env=GMAIL_TOKEN_ENV,
                credential_configured=bool(os.environ.get(GMAIL_TOKEN_ENV, "").strip()),
                egress_host=GMAIL_HOST,
                egress_allowed=GMAIL_HOST in allowlist,
                actions=("read_message", "read_thread"),
                kind="read_only",
            )
        )
        gcal_gate = self.control.get_capability_gate(
            "connector_gcal_runtime", acting_principal_id
        )
        connectors.append(
            ConnectorView(
                connector_id="gcal",
                display_name="Google Calendar (read-only)",
                capability="connector_gcal_runtime",
                gate_state=gcal_gate.state if gcal_gate is not None else "unknown",
                capability_enabled=(
                    bool(gcal_gate.runtime_enabled) if gcal_gate is not None else False
                ),
                decision_mode=gcal_gate.decision_mode if gcal_gate is not None else "ask",
                credential_env=GCAL_TOKEN_ENV,
                credential_configured=bool(os.environ.get(GCAL_TOKEN_ENV, "").strip()),
                egress_host=GCAL_HOST,
                egress_allowed=GCAL_HOST in allowlist,
                actions=("read_event", "read_calendar"),
                kind="read_only",
            )
        )
        slack_gate = self.control.get_capability_gate(
            "connector_slack_runtime", acting_principal_id
        )
        connectors.append(
            ConnectorView(
                connector_id="slack",
                display_name="Slack (read-only)",
                capability="connector_slack_runtime",
                gate_state=slack_gate.state if slack_gate is not None else "unknown",
                capability_enabled=(
                    bool(slack_gate.runtime_enabled) if slack_gate is not None else False
                ),
                decision_mode=slack_gate.decision_mode if slack_gate is not None else "ask",
                credential_env=SLACK_TOKEN_ENV,
                credential_configured=bool(os.environ.get(SLACK_TOKEN_ENV, "").strip()),
                egress_host=SLACK_HOST,
                egress_allowed=SLACK_HOST in allowlist,
                actions=("read_channel_info", "read_channel_history"),
                kind="read_only",
            )
        )
        return ConnectionsView(
            connectors=tuple(connectors),
            connector_egress_allowlist_configured=bool(
                os.environ.get("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", "").strip()
            ),
        )

    @staticmethod
    def _current_model(registry: ModelProfileRegistry, state: ModelSessionState | None) -> str | None:
        """The concrete model the current selection binds, or None."""
        if state is None:
            return None
        try:
            profile = registry.resolve_profile_id(state.profile_id)
        except Exception:  # noqa: BLE001 — a stale selection must not break the read
            return None
        effective = state.model or profile.model
        if not effective or "<" in effective:
            return None
        return effective

    def set_model_fallback_sequence(
        self, profile_ids: list[str], acting_principal_id: str | None
    ) -> ControlResult:
        """Persist the user-owned ordered fallback sequence (human gate-manager only).

        Only known, non-test model profile ids are accepted; unknown ids fail
        closed with ``unknown_profile:<id>``. Authorization mirrors the capability
        control plane: the acting principal must be a human ``runtime_gate_manager``.
        Persisting the ordered list does not itself enable any provider — each
        candidate is still gated by provider policy when a turn actually falls back.
        """
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if not self.control._is_gate_manager(principal):  # noqa: SLF001
            return ControlResult(ok=False, reason_code="not_authorized_gate_manager")
        registry = ModelProfileRegistry.load()
        known: dict[str, Any] = {p.profile_id: p for p in registry.list_profiles()}
        cleaned: list[str] = []
        for profile_id in profile_ids:
            profile = known.get(profile_id)
            if profile is None:
                return ControlResult(ok=False, reason_code=f"unknown_profile:{profile_id}")
            if bool(profile.raw.get("test_only", False)):
                return ControlResult(ok=False, reason_code=f"test_profile_not_allowed:{profile_id}")
            if profile_id not in cleaned:
                cleaned.append(profile_id)
        if self.store.get_account(principal.principal_id) is not None:
            self.store.save_principal_model_fallback_sequence(principal.principal_id, cleaned)
        else:
            self.store.save_model_fallback_sequence(TERMINAL_MODEL_SESSION_ID, cleaned)
        return ControlResult(ok=True, data={"fallback_sequence": cleaned})

    def set_model_advisor(
        self, profile_id: str | None, acting_principal_id: str | None
    ) -> ControlResult:
        """Persist the user-owned advisor model profile (human gate-manager only).

        ``None``/empty clears the advisor. Only known, non-test profiles with a
        concrete model are accepted — placeholder-``<model>`` profiles fail
        closed (pick a concrete model for the profile first). Persisting the
        advisor never enables anything: the consult path is gated by
        ``advisor_model_runtime``, its decision mode, and provider policy.
        """
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if not self.control._is_gate_manager(principal):  # noqa: SLF001
            return ControlResult(ok=False, reason_code="not_authorized_gate_manager")
        cleaned = (profile_id or "").strip()
        if not cleaned:
            if self.store.get_account(principal.principal_id) is not None:
                self.store.save_principal_model_advisor(principal.principal_id, None)
            else:
                self.store.save_model_advisor(TERMINAL_MODEL_SESSION_ID, None)
            return ControlResult(ok=True, data={"advisor_profile_id": None})
        registry = ModelProfileRegistry.load()
        try:
            profile = registry.resolve_profile_id(cleaned)
        except Exception:  # noqa: BLE001 — unknown profile fails closed
            return ControlResult(ok=False, reason_code=f"unknown_profile:{cleaned}")
        if bool(profile.raw.get("test_only", False)):
            return ControlResult(ok=False, reason_code=f"test_profile_not_allowed:{cleaned}")
        state = (
            self.store.load_principal_model_state(principal.principal_id)
            if self.store.get_account(principal.principal_id) is not None
            else self.store.load_model_session_state(TERMINAL_MODEL_SESSION_ID)
        )
        effective_model = profile.model
        if state is not None and state.profile_id == profile.profile_id and state.model:
            effective_model = state.model
        if not effective_model or "<" in effective_model:
            return ControlResult(ok=False, reason_code=f"model_required_for_profile:{cleaned}")
        if self.store.get_account(principal.principal_id) is not None:
            self.store.save_principal_model_advisor(principal.principal_id, profile.profile_id)
        else:
            self.store.save_model_advisor(TERMINAL_MODEL_SESSION_ID, profile.profile_id)
        return ControlResult(ok=True, data={"advisor_profile_id": profile.profile_id})

    async def list_provider_models(
        self, profile_id: str, acting_principal_id: str | None = None
    ) -> ProviderModelListView | None:
        """List the models a provider serves, on explicit user demand.

        Returns None for unknown/test-only profiles (the route 404s). This is the
        only web read that touches the network, and only because the user asked
        for this provider's catalogue; provider policy (gates, egress allowlist,
        API key) is enforced by the provider factory exactly as for a chat call,
        so a policy-denied provider is never contacted. On any failure the list
        is empty with an honest status — model names are never fabricated.
        """
        registry = ModelProfileRegistry.load()
        try:
            profile = registry.resolve_profile_id(profile_id)
        except Exception:  # noqa: BLE001 — unknown profile fails closed
            return None
        if bool(profile.raw.get("test_only", False)):
            return None
        from raiker.models.connections import get_model_connection

        router = ModelRouter(
            registry,
            runtime_policy=provider_runtime_policy_from_gates(self.store, acting_principal_id),
            connection_resolver=lambda current_profile_id: get_model_connection(
                self.store, acting_principal_id or "", current_profile_id
            ) if acting_principal_id else None,
        )
        try:
            models = await router.alist_models_for_profile(profile)
        except ProviderPolicyError as exc:
            return ProviderModelListView(
                profile_id=profile.profile_id,
                provider=profile.provider,
                status="policy_denied",
                reason_code=safe_error(str(exc)),
                models=(),
            )
        except ModelProviderError as exc:
            unsupported = "unsupported" in str(exc)
            return ProviderModelListView(
                profile_id=profile.profile_id,
                provider=profile.provider,
                status="unsupported" if unsupported else "unavailable",
                reason_code="model_listing_unsupported" if unsupported else "provider_unreachable",
                models=(),
            )
        except Exception as exc:  # noqa: BLE001 — network/parse failures fail closed
            return ProviderModelListView(
                profile_id=profile.profile_id,
                provider=profile.provider,
                status="unavailable",
                reason_code=safe_error(type(exc).__name__),
                models=(),
            )
        return ProviderModelListView(
            profile_id=profile.profile_id,
            provider=profile.provider,
            status="available",
            reason_code=None,
            models=tuple(m.id for m in models),
        )

    async def set_model_selection(
        self, profile_id: str, model: str | None, acting_principal_id: str | None
    ) -> ControlResult:
        """Persist the operator's model selection (human gate-manager only).

        Mirrors the CLI ``/model use``: the effective profile (concrete model +
        endpoint + provider policy) is validated by the provider factory without
        connecting, so a hosted provider whose gate/egress/key is missing fails
        closed here instead of at turn time. Placeholder profiles require an
        explicit concrete model.
        """
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if not self.control._is_gate_manager(principal):  # noqa: SLF001
            return ControlResult(ok=False, reason_code="not_authorized_gate_manager")
        registry = ModelProfileRegistry.load()
        try:
            profile = registry.resolve_profile_id(profile_id)
        except Exception:  # noqa: BLE001 — unknown profile fails closed
            return ControlResult(ok=False, reason_code=f"unknown_profile:{profile_id}")
        if bool(profile.raw.get("test_only", False)):
            return ControlResult(ok=False, reason_code=f"test_profile_not_allowed:{profile_id}")
        resolved_model = (model or "").strip() or profile.model
        if not resolved_model or "<" in resolved_model:
            return ControlResult(ok=False, reason_code=f"model_required_for_profile:{profile_id}")
        effective = (
            profile
            if resolved_model == profile.model
            else profile_with_model(profile, resolved_model)
        )
        try:
            from raiker.models.connections import get_model_connection

            validator = ModelProviderFactory(
                policy=provider_runtime_policy_from_gates(self.store, principal.principal_id),
                connection=get_model_connection(self.store, principal.principal_id, profile.profile_id),
            ).create(effective)
        except Exception as exc:  # noqa: BLE001 — provider policy failures fail closed
            self._append_model_event(
                "model_provider_rejected_by_policy",
                {
                    "profile_id": profile.profile_id,
                    "provider": profile.provider,
                    "model": resolved_model,
                    "reason": safe_error(str(exc)),
                },
            )
            return ControlResult(ok=False, reason_code=safe_error(str(exc)))
        aclose = getattr(validator, "aclose", None)
        if aclose is not None:
            await aclose()
        state = ModelSessionState(
                session_id=principal.principal_id if self.store.get_account(principal.principal_id) is not None else TERMINAL_MODEL_SESSION_ID,
                profile_id=profile.profile_id,
                model=(None if resolved_model == profile.model else resolved_model),
            )
        if self.store.get_account(principal.principal_id) is not None:
            self.store.save_principal_model_state(principal.principal_id, state)
        else:
            self.store.save_model_session_state(state)
        self._append_model_event(
            "model_profile_selected",
            {
                "profile_id": profile.profile_id,
                "provider": profile.provider,
                "model": profile.model,
                "endpoint_kind": profile.raw.get("endpoint_kind", "unknown"),
                "resolved_model": resolved_model,
            },
        )
        return ControlResult(
            ok=True, data={"profile_id": profile.profile_id, "model": resolved_model}
        )

    def _append_model_event(self, event_type: str, payload: dict[str, Any]) -> None:
        from raiker.contracts.models import ClientMetadata
        from raiker.events.types import make_event
        from raiker.events.writer import EventLogWriter

        EventLogWriter(self.store).append(
            make_event(
                session_id=TERMINAL_MODEL_SESSION_ID,
                turn_id=None,
                event_type=event_type,
                actor="web_ui",
                payload=payload,
                client=ClientMetadata(type="web_ui", name="raiker-web", version="0.0.0"),
            )
        )

    @staticmethod
    def _runtime_gate_for_profile(endpoint_kind: str) -> str | None:
        if endpoint_kind == "remote_hosted":
            return HOSTED_MODEL_GATE
        if endpoint_kind == "private_network":
            return PRIVATE_NETWORK_MODEL_GATE
        return None

    def get_diagnostics(self, acting_principal_id: str | None = None) -> DiagnosticsView:
        readiness = self.control.get_runtime_readiness(acting_principal_id)
        disabled = tuple(
            g.capability for g in readiness.gates if g.state in _DISABLED_STATES
        )
        counts = {
            "sessions": len(self.store.list_sessions(limit=1000)),
            "events": self.store.count_events(),
            "checkpoints": self.store.count_checkpoints(),
            "tasks": self.store.count_tasks(),
        }
        models = self.get_models(acting_principal_id)
        provider_health = self._provider_health(models)
        missing_config = self._missing_config(readiness, models)
        return DiagnosticsView(
            runtime_mode=readiness.mode.mode_name,
            production_ready_local_single_user_runtime=bool(
                readiness.summary.get("production_ready_local_single_user_runtime", False)
            ),
            summary=readiness.summary,
            disabled_capabilities=disabled,
            counts=counts,
            readiness=readiness.summary,
            missing_config=missing_config,
            provider_health=provider_health,
        )

    @staticmethod
    def _provider_health(models: ModelsView) -> tuple[ProviderHealthView, ...]:
        """Configuration-derived provider status. Never probes the network on a read, and never
        fabricates reachability — reachability is checked on demand via the CLI."""
        return tuple(
            ProviderHealthView(
                profile_id=p.profile_id,
                provider=p.provider,
                model=p.model,
                endpoint_kind=p.endpoint_kind,
                local_only=p.local_only,
                requires_network=p.requires_network,
                selected=p.selected,
                status="selected" if p.selected else "configured",
                detail=(
                    "local provider; reachability not probed here"
                    if p.local_only
                    else "remote/networked provider; reachability not probed here"
                ),
            )
            for p in models.profiles
        )

    @staticmethod
    def _missing_config(readiness: Any, models: ModelsView) -> tuple[str, ...]:
        """Human-readable configuration gaps derived from stored readiness — no shell, no probing."""
        s = readiness.summary
        gaps: list[str] = []
        if not s.get("owner_bootstrapped", False):
            gaps.append("No owner principal is bootstrapped (run `raiker` → `/bootstrap-owner`).")
        if not s.get("acting_principal_available", False):
            gaps.append("No acting principal is available.")
        if not s.get("runtime_gate_manager_available", False):
            gaps.append("No runtime_gate_manager principal is available to change gates.")
        if readiness.mode.status != "active":
            gaps.append("No runtime mode is active.")
        if models.current_profile_id is None:
            gaps.append("No model profile is selected.")
        return tuple(gaps)

    # ── Auth (local token mint) ─────────────────────────────────────────
    def mint_owner_session(self, as_principal: str | None = None) -> AuthSessionView | AuthError:
        from raiker.api.sessions import ApiSessionStore
        from raiker.cli.principal_resolver import resolve_local_principal

        principal, error = resolve_local_principal(self.workspace_root, as_principal)
        if principal is None:
            return AuthError(reason_code="no_local_owner", message=error)
        if principal.principal_type != PrincipalType.HUMAN:
            return AuthError(reason_code="ai_principal_not_allowed", message="AI principals cannot mint a session.")
        raw_token, session = ApiSessionStore(self.workspace_root).create_session(principal.principal_id)
        return AuthSessionView(
            token=raw_token,
            session_id=session.session_id,
            principal_id=principal.principal_id,
            expires_at=session.expires_at,
        )

    # ── Mappers ─────────────────────────────────────────────────────────
    def _session_view(self, row: dict[str, Any]) -> SessionView:
        session_id = str(row["session_id"])
        return SessionView(
            session_id=session_id,
            title=row.get("title"),
            status=str(row.get("status", "")),
            created_at=str(row.get("created_at", "")),
            updated_at=str(row.get("updated_at", "")),
            turn_count=len(self.store.list_turns(session_id, limit=1000)),
            pinned=bool(row.get("pinned", 0)),
            tags=tuple(self.store.list_session_tags(session_id)),
            project_id=row.get("project_id"),
            archived=bool(row.get("archived", 0)),
            archived_at=row.get("archived_at"),
        )

    @staticmethod
    def _turn_view(row: dict[str, Any]) -> TurnView:
        return TurnView(
            turn_id=str(row["turn_id"]),
            session_id=str(row["session_id"]),
            turn_type=str(row.get("turn_type", "")),
            status=str(row.get("status", "")),
            prompt_text=row.get("prompt_text"),
            created_at=str(row.get("created_at", "")),
            completed_at=row.get("completed_at"),
            summary=row.get("summary"),
        )

    @staticmethod
    def _event_view(row: dict[str, Any]) -> EventView:
        return EventView(
            event_id=str(row["event_id"]),
            session_id=str(row.get("session_id", "")),
            turn_id=row.get("turn_id"),
            event_type=str(row.get("event_type", "")),
            actor=str(row.get("actor", "")),
            timestamp=str(row.get("timestamp", "")),
            risk_level=row.get("risk_level"),
            summary=row.get("summary"),
        )

    @staticmethod
    def _checkpoint_view(row: dict[str, Any]) -> CheckpointView:
        return CheckpointView(
            checkpoint_id=str(row["checkpoint_id"]),
            session_id=str(row.get("session_id", "")),
            turn_id=row.get("turn_id"),
            task_id=row.get("task_id"),
            checkpoint_type=str(row.get("checkpoint_type", "")),
            created_at=str(row.get("created_at", "")),
            summary=row.get("summary"),
            last_event_id=row.get("last_event_id"),
            can_restore_state=bool(row.get("can_restore_state", 0)),
            can_restore_files=bool(row.get("can_restore_files", 0)),
        )

    @staticmethod
    def _age_seconds(created_at: str) -> int | None:
        try:
            then = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None
        from datetime import UTC

        delta = datetime.now(UTC) - then
        return max(0, int(delta.total_seconds()))

    @classmethod
    def _approval_view(cls, row: dict[str, Any]) -> ApprovalView:
        tool_name = str(row.get("tool_name", ""))
        status = str(row.get("status", ""))
        created_at = str(row.get("created_at", ""))
        expires_at = str(row.get("expires_at", "")) or None
        return ApprovalView(
            approval_id=str(row["approval_id"]),
            action_id=str(row.get("action_id", "")),
            status=status,
            tool_name=tool_name,
            capability=CAPABILITY_GATE_MAP.get(tool_name, tool_name),
            risk_level=str(row.get("risk_level", "")),
            session_id=str(row.get("session_id", "")),
            turn_id=row.get("turn_id"),
            created_at=created_at,
            age_seconds=cls._age_seconds(created_at),
            requires_approval=status == "pending",
            expires_at=expires_at,
            is_expired=status == "pending" and bool(expires_at and utc_now() > expires_at),
            critical=bool(row.get("critical")),
        )

    def _approval_detail(self, row: dict[str, Any]) -> ApprovalDetailView:
        view = self._approval_view(row)
        try:
            raw_args = json.loads(str(row.get("arguments_json", "{}")))
        except (ValueError, TypeError):
            raw_args = {}
        arguments = self._redact_arguments(raw_args)
        diff, diff_path, kind = self._build_preview(view.tool_name, raw_args)
        return ApprovalDetailView(
            approval=view,
            arguments=arguments,
            diff=diff,
            diff_path=diff_path,
            preview_kind=kind,
            metadata_only_notice=(
                "Approving this connector write executes this exact action once."
                if view.tool_name == "connector_write"
                else "Approval resolution is metadata-only. Recording a decision does NOT execute the action."
            ),
        )

    @classmethod
    def _redact_arguments(cls, args: Any) -> dict[str, Any]:
        if not isinstance(args, dict):
            return {}
        return {str(k): cls._redact_value(v) for k, v in args.items()}

    @classmethod
    def _redact_value(cls, value: Any) -> Any:
        if isinstance(value, str):
            return redact_secret_like_text(value)
        if isinstance(value, list):
            return [cls._redact_value(v) for v in value]
        if isinstance(value, dict):
            return {str(k): cls._redact_value(v) for k, v in value.items()}
        return value

    def _build_preview(
        self, tool_name: str, args: dict[str, Any]
    ) -> tuple[str | None, str | None, str]:
        """Return (diff, path, preview_kind). File mutations get a unified diff; never executes."""
        if tool_name in {"write_file", "edit_file"}:
            try:
                snapshot = proposed_write_snapshot(
                    self.workspace_root,
                    str(args.get("path", ".")),
                    str(args.get("text", "")),
                )
            except FilesystemSafetyError:
                return None, str(args.get("path", "")), "arguments"
            before = snapshot.get("before_snapshot") or ""
            after = str(snapshot.get("proposed_text", ""))
            path = str(snapshot.get("path", args.get("path", "")))
            diff = "".join(
                difflib.unified_diff(
                    redact_secret_like_text(before).splitlines(keepends=True),
                    redact_secret_like_text(after).splitlines(keepends=True),
                    fromfile=f"a/{path}",
                    tofile=f"b/{path}",
                )
            )
            return diff, path, "file_diff"
        if tool_name == "apply_patch":
            patch = redact_secret_like_text(str(args.get("patch", "")))
            return patch, str(args.get("path", "")) or None, "patch"
        return None, None, "arguments"

    @staticmethod
    def _task_view(task: Any) -> TaskView:
        d = asdict(task) if not isinstance(task, dict) else task
        return TaskView(
            task_id=str(d["task_id"]),
            session_id=str(d.get("session_id", "")),
            status=str(d.get("status", "")),
            title=str(d.get("title", "")),
            objective=str(d.get("objective", "")),
            current_step=d.get("current_step"),
            progress_percent=d.get("progress_percent"),
            created_at=str(d.get("created_at", "")),
            updated_at=str(d.get("updated_at", "")),
            completed_at=d.get("completed_at"),
            summary=d.get("summary"),
            priority=d.get("priority"),
            scheduled_at=d.get("scheduled_at"),
            recurrence=d.get("recurrence"),
            reminder_at=d.get("reminder_at"),
            parent_task_id=d.get("parent_task_id"),
            project_id=d.get("project_id"),
        )


__all__ = [
    "ApprovalDetailView",
    "ApprovalView",
    "AuthError",
    "AuthSessionView",
    "CheckpointView",
    "DashboardService",
    "DiagnosticsView",
    "EventView",
    "ModelProfileView",
    "ModelsView",
    "ProviderHealthView",
    "SessionDetailView",
    "SessionView",
    "TaskView",
    "TurnDetailView",
    "TurnView",
]
