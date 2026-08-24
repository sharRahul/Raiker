from __future__ import annotations

import base64
import contextlib
import difflib
import json
import os
import re
import shutil
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from raiker.approval_previews import redact_secret_like_text
from raiker.checkpoints.capture import MAX_PRE_IMAGE_BYTES
from raiker.contracts.ids import new_id, utc_now
from raiker.control.dtos import ControlResult
from raiker.control.knowledge_scope import (
    ARTIFACTS_ROOT_ID,
    KNOWLEDGE_SOURCE_EXTENSIONS,
    KNOWLEDGE_UPLOAD_DIR,
    MAX_KNOWLEDGE_UPLOAD_BYTES,
    MAX_SOURCE_PATH_CHARS,
    RUNTIME_DIR_NAME,
    SKIPPED_DIRECTORY_NAMES,
    ScopeError,
    ScopeRoot,
    build_roots,
    grant_root_id,
    parent_scope_path,
    resolve,
    scope_path,
)
from raiker.control.service import RuntimeControlService
from raiker.events.export import generate_export
from raiker.events.writer import EventLogWriter
from raiker.execution.profiles import (
    CONTAINER_PROFILE_TOOLS,
    DEFAULT_EXECUTION_PROFILES,
    ContainerRuntime,
    ExecutionProfile,
    RepositoryAccess,
    probe_execution_profile,
    validate_execution_profile,
)
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
from raiker.runtime.executors.containers import container_image_allowlist
from raiker.runtime.model_facts_store import ModelFactsStore
from raiker.security.credentials import CredentialLifecycle, CredentialLifecycleView
from raiker.security.monitoring import SecurityMonitor
from raiker.storage.internal_paths import display_path, internal_io_path
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager
from raiker.tasks.scheduler import RECURRING_INTERVALS
from raiker.tools.filesystem import (
    FilesystemSafetyError,
    proposed_edit_snapshot,
    proposed_patch_snapshot,
    proposed_write_snapshot,
    resolve_workspace_path,
)
from raiker.tools.git import (
    proposed_branch_snapshot,
    proposed_commit_snapshot,
    proposed_push_snapshot,
    repository_label,
    resolve_repository_root,
    selected_repository_subpath,
)
from raiker.tools.graph_tools import reference_resolution

# Capability states that mean the gate is off / fail-closed.
_DISABLED_STATES = {"disabled", "planned"}

# Cadences a task/schedule may carry. `background` runs one governed cycle now;
# the recurring cadences re-arm after every cycle so a standing agent keeps
# working until the owner stops it. An unknown cadence is refused rather than
# silently stored as a one-shot, which would make a "keep going" schedule stop
# after its first run.
TASK_RECURRENCES = frozenset({"background", *RECURRING_INTERVALS})

# Task states in which the stored summary *is* the outcome — what the run ended
# on, or what it is parked against. In those states `current_step` is the step
# the run last reached, which is not what the owner needs to be told (BUG-09).
TASK_OUTCOME_STATES = frozenset({"completed", "failed", "cancelled", "waiting_for_approval"})

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
    # RAIKER-2020 — when this row came from a search, the exchange that matched
    # and the turn it belongs to. Empty on a plain listing. It is what lets a
    # result say *why* it matched rather than only that it did, which is the
    # difference between finding a chat from years ago and recognising it.
    match_snippet: str = ""
    match_turn_id: str = ""
    # Soft-archive state (Control Deck task 3). Archiving is a reversible
    # organizing action — it moves a chat out of the default active list but
    # never deletes transcripts, events, checkpoints, or permissions.
    archived: bool = False
    archived_at: str | None = None
    # Where the session came from: "chat" for a conversation the owner typed,
    # "task" for the server-owned session a task runs in (BUG-10). Provenance
    # only — it grants nothing and hides nothing; a task session stays fully
    # readable here and from Tasks.
    origin: str = "chat"

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
    # BUG-234 — the Model Context Protocol revision this server actually
    # negotiated, recorded by the last successful handshake. Null until one has
    # happened; nothing in the product said which revision Raiker speaks, which
    # made "why will this server not connect" unanswerable.
    protocol_version: str | None = None

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
    # BUG-215 — how much working this turn produced, and the working itself when
    # the owner has asked for it to be kept. `reasoning_chars > 0` with
    # `reasoning is None` is the honest "it thought, and that was not kept" case
    # a re-opened turn has to be able to state.
    reasoning_chars: int = 0
    reasoning: str | None = None

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
    machine_identity: IdentityView | None = None

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
    relationship_id: str | None = None
    evidence_memory_id: str | None = None
    owner_can_reject: bool = False

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
    updated_at: str | None = None
    last_used_at: str | None = None

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
            "updated_at": self.updated_at,
            "last_used_at": self.last_used_at,
        }


@dataclass(frozen=True)
class ObservationView:
    """MEM-04 — one eidetic observation, as the owner reads it.

    Everything here is metadata *about* material the runtime saw. There is no
    field carrying the material itself, and that is deliberate rather than
    incidental: the point of an observation is that it makes recall possible
    without making a second ungoverned copy of everything the agent has read.
    """

    observation_id: str
    session_id: str
    turn_id: str
    tool_name: str
    source_type: str
    summary: str
    sensitivity: str
    retention: str
    capture_status: str
    skip_reason: str
    promotable_to_memory: bool
    content_sha256: str
    content_bytes: int
    artifact_ref: str | None
    source_event_id: str
    created_at: str
    expires_at: str
    gist_status: str = ""
    gist_summary: str = ""
    gist_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "tool_name": self.tool_name,
            "source_type": self.source_type,
            "summary": self.summary,
            "sensitivity": self.sensitivity,
            "retention": self.retention,
            "capture_status": self.capture_status,
            "skip_reason": self.skip_reason,
            "promotable_to_memory": self.promotable_to_memory,
            "content_sha256": self.content_sha256,
            "content_bytes": self.content_bytes,
            "artifact_ref": self.artifact_ref,
            "source_event_id": self.source_event_id,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "gist_status": self.gist_status,
            "gist_summary": self.gist_summary,
            "gist_id": self.gist_id,
        }


@dataclass(frozen=True)
class MemorySettingsView:
    incognito: bool
    #: MEM-03 — which embedding space recall searches, and what is selectable.
    #: `retrieval` is what is in force *now*, including the reason a weaker
    #: backend is in force; `spaces` is what this workspace actually holds
    #: vectors in, which is the only thing worth offering as a choice.
    embedding_backend: str = "auto"
    retrieval: dict[str, Any] = field(default_factory=dict)
    spaces: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "incognito": self.incognito,
            "embedding_backend": self.embedding_backend,
            "retrieval": dict(self.retrieval),
            "spaces": [dict(space) for space in self.spaces],
        }


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
    model_profile: str | None = None
    model: str | None = None
    attachments: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


#: BUG-218 — how a tool is named on the Knowledge Map. The registry's own
#: labels are written for a transcript line ("Run command"); a graph node has
#: room for a noun. Anything unlisted falls back to its underscored name made
#: readable, so a new tool appears sensibly without being registered twice.
TOOL_LABELS: dict[str, str] = {
    "read_file": "Read file",
    "write_file": "Write file",
    "edit_file": "Edit file",
    "apply_patch": "Apply patch",
    "list_directory": "List folder",
    "grep": "Search text",
    "glob": "Find files",
    "shell": "Run command",
    "run_command": "Run command",
    "background_run": "Background run",
    "web_fetch": "Fetch page",
    "web_search": "Web search",
    "memory_search": "Search memory",
    "memory_write": "Remember",
    "knowledge_graph": "Explore graph",
    "conversation_search": "Search chats",
    "code_map_search": "Search code map",
    "code_map_references": "Find references",
    "create_document": "Create document",
    "spawn_subagent": "Delegate",
    "update_plan": "Update plan",
}

#: What a cited source is drawn *as*. A file the answer quoted should look like
#: a file on the map, not like a generic citation — the whole complaint BUG-218
#: answers is that the map showed runtime bookkeeping where the owner expected
#: their own material.
CONTEXT_NODE_TYPES: dict[str, str] = {
    "file": "file",
    "repository": "file",
    "attachment": "file",
    "document": "file",
    "folder": "folder",
    "memory": "memory",
    "conversation": "conversation",
    "web": "source",
    "url": "source",
    "connector": "source",
}


#: BUG-218 — a Chat and a Build session are different work. `sessions.origin`
#: already distinguished them and the map drew both as one green dot.
SESSION_NODE_TYPES: dict[str, str] = {
    "chat": "conversation",
    "build": "build",
    "task": "task_run",
    "workbench": "conversation",
}

SESSION_LABELS: dict[str, str] = {
    "chat": "chat",
    "build": "build session",
    "task": "task run",
    "workbench": "chat",
}


def _task_detail(task: TaskView) -> str | None:
    """What a live view should say about a task: its outcome, else its step."""
    if task.status in TASK_OUTCOME_STATES:
        return task.summary or task.current_step
    return task.current_step


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
    usage_admin_configured: bool = False
    # Prompt-cache TTL breakpoint the provider uses for this profile ("5m"/"1h"),
    # or None when the provider/profile does not cache. Read-only status.
    prompt_cache_ttl: str | None = None
    # Context capacity and pricing are configuration-owned facts. They stay
    # unset for placeholder or provider-discovered models rather than guessed.
    context_window_tokens: int | None = None
    context_window_source: str | None = None
    configured: bool = False
    readiness_state: str = "not_configured"
    readiness_summary: str = "No readiness check exists for this exact model."
    readiness_reason_code: str = "model_not_checked"
    readiness_checked_at: str | None = None
    readiness_expires_at: str | None = None
    readiness_remediation: str = "Set up or check this model before sending."
    ready: bool = False
    # Only a provider Raiker authenticates with an API key can accrue an API
    # bill, so only those carry cost. A local runtime reports `billable=False`
    # and the UI says "no API cost" rather than an unexplained blank.
    billable: bool = False
    # All-time usage on this provider for the acting owner. `cost` is None when
    # no price is resolvable — never 0, which would read as "free".
    models_used: int = 0
    turns_used: int = 0
    total_tokens: int = 0
    total_cost: str | None = None
    cost_currency: str | None = None
    # Where the active model's price came from: "owner" | "provider" | "config".
    price_source: str | None = None
    price_as_of: str | None = None
    # Provider-declared capability facts. The UI never infers them from a
    # model name or fabricates effort values.
    supports_reasoning: bool = False
    supports_reasoning_effort: bool = False
    reasoning_effort_values: tuple[str, ...] = ()
    # BUG-207 slice B — a provider declares reasoning as an *effort* (OpenAI) or
    # as a *mode* (Anthropic). Sending only the effort values meant the composer
    # could offer a reasoning control for one provider and none for the other,
    # which is why the thinking the product asked for was never asked for.
    reasoning_modes: tuple[str, ...] = ()
    supports_reasoning_summary: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextUsageView:
    """What one conversation has used, and what it has cost.

    Every figure is optional and every one names its source. A missing price, a
    provider that reports no usage, or a model with no published capacity all
    resolve to None here and to an explicit "unavailable" in the UI — this view
    never substitutes a zero or an estimate for a fact it does not have.
    """

    session_id: str
    profile_id: str | None
    provider: str | None
    model: str | None
    # Provider-reported prompt tokens for the newest turn, when one exists.
    used_tokens: int | None
    context_window_tokens: int | None
    context_window_source: str | None
    # "provider" once a turn has run; "unavailable" before that, at which point
    # the browser falls back to its own labelled transcript estimate.
    usage_source: str
    billable: bool
    session_cost: str | None
    provider_total_cost: str | None
    currency: str | None
    price_source: str | None
    price_as_of: str | None
    session_turns: int = 0
    session_input_tokens: int = 0
    session_output_tokens: int = 0
    # BUG-21 — the individual rate components behind `session_cost`, read from
    # the normalised registry. All four are optional and independently sourced:
    # a provider that publishes no cache rate leaves those None rather than
    # having one inferred from the input rate.
    price_input_per_mtok: str | None = None
    price_output_per_mtok: str | None = None
    price_cache_write_per_mtok: str | None = None
    price_cache_read_per_mtok: str | None = None
    price_effective_from: str | None = None
    # True when the conversation runs on a billable provider for which no exact
    # rate exists. The popover states "Unknown" and offers Configure → rather
    # than showing nothing or implying the turn was free.
    price_unknown: bool = False
    # Latest automatic provider-context compaction. This is deliberately
    # metadata-only; the summary remains in the encrypted workspace store and
    # transcript turns are never rewritten.
    latest_compaction: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ModelPricingEntryView:
    """One exact model's pricing row for the Models → Pricing surface (BUG-21)."""

    provider: str
    model: str
    profile_id: str | None
    source: str | None
    currency: str | None
    input_per_mtok: str | None
    output_per_mtok: str | None
    cache_write_per_mtok: str | None
    cache_read_per_mtok: str | None
    effective_from: str | None
    as_of: str | None
    reviewed_at: str | None
    review_due_at: str | None
    review_status: str | None
    recorded_at: str | None
    recorded_by: str | None
    reason: str | None
    has_owner_override: bool
    history: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["history"] = [dict(entry) for entry in self.history]
        return data


@dataclass(frozen=True)
class ModelPricingView:
    """Everything Models → Pricing has to state, in one governed read."""

    entries: tuple[ModelPricingEntryView, ...]
    sync: tuple[dict[str, Any], ...]
    can_override: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "entries": [entry.to_dict() for entry in self.entries],
            "sync": [dict(state) for state in self.sync],
            "can_override": self.can_override,
        }


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
    ready_provider_count: int = 0
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
    # BUG-82 — the advisor is a second model this runtime calls, chosen in the
    # same UI as the chat model and, until now, never readiness-checked: no
    # probe, no state, no chip, and no row in `GET /api/model-readiness`. An
    # owner could pin an advisor whose provider had no credential, no credit or
    # no running runtime and see nothing wrong until a consult failed mid-turn.
    # These four report the exact model a consult would call and what the last
    # check of *that* model found, so the selector can carry the same chip and
    # repair sentence a provider card does.
    advisor_model: str | None = None
    advisor_readiness_state: str = "not_configured"
    advisor_readiness_summary: str | None = None
    advisor_readiness_remediation: str | None = None
    advisor_readiness_checked_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "profiles": [p.to_dict() for p in self.profiles],
            "chat_profiles": [p.to_dict() for p in self.chat_profiles],
            "current_profile_id": self.current_profile_id,
            "current_model": self.current_model,
            "advisor_profile_id": self.advisor_profile_id,
            "advisor_model_gate_state": self.advisor_model_gate_state,
            "advisor_model": self.advisor_model,
            "advisor_readiness_state": self.advisor_readiness_state,
            "advisor_readiness_summary": self.advisor_readiness_summary,
            "advisor_readiness_remediation": self.advisor_readiness_remediation,
            "advisor_readiness_checked_at": self.advisor_readiness_checked_at,
            "hosted_model_gate_state": self.hosted_model_gate_state,
            "private_network_model_gate_state": self.private_network_model_gate_state,
            "model_egress_allowlist_configured": self.model_egress_allowlist_configured,
            "remote_profile_count": self.remote_profile_count,
            "ready_provider_count": self.ready_provider_count,
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
class IdentityView:
    principal_id: str
    principal_type: str
    display_name: str
    subject: str | None = None
    turn_id: str | None = None
    key_id: str | None = None
    issued_at: str | None = None
    expires_at: str | None = None
    state: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
    proposed_by: IdentityView
    approved_by: IdentityView | None
    machine_identity: IdentityView | None
    # Resolving an approval records a decision; it never executes the action.
    executes_action: bool = False
    # Critical approvals use the elevated, human-only RuntimeAuthority lifecycle.
    critical: bool = False
    resolved_by: str | None = None
    # ADD-02 — where this decision sits in the batch of tool calls the turn
    # proposed. 1 of 1 for an ordinary single-call approval; "2 of 3" tells the
    # owner two more decisions are queued behind this one on the same turn.
    queue_position: int = 1
    queue_total: int = 1

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
    # Server-computed: does pressing Approve actually perform this action? True
    # for a connector write intent and — once the relay and the target capability
    # are both enabled — for a file mutation. The owner is told which of the two
    # kinds of decision they are making before they make it.
    executes_on_approval: bool = False
    execution_evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "approval": self.approval.to_dict(),
            "arguments": dict(self.arguments),
            "diff": self.diff,
            "diff_path": self.diff_path,
            "preview_kind": self.preview_kind,
            "metadata_only_notice": self.metadata_only_notice,
            "executes_on_approval": self.executes_on_approval,
            "execution_evidence": dict(self.execution_evidence),
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
        """Resolve one workspace-contained path, for the Build repository refs.

        The Knowledge Map no longer uses this — it has its own, narrower
        boundary in :mod:`raiker.control.knowledge_scope`. Referencing a
        repository is a different act: the owner names a folder they already
        keep in this workspace, and the containment check is against the
        workspace itself.
        """
        candidate = raw_path.strip()
        if not candidate or len(candidate) > MAX_SOURCE_PATH_CHARS:
            raise ValueError("invalid_brain_source_path")
        root = self.workspace_root.resolve()
        path = (root / candidate).resolve()
        if path != root and root not in path.parents:
            raise ValueError("brain_source_outside_workspace")
        relative = path.relative_to(root)
        if any(part in {".git", RUNTIME_DIR_NAME, "node_modules"} for part in relative.parts):
            raise ValueError("brain_source_protected_path")
        if not path.exists():
            raise ValueError("brain_source_not_found")
        return relative.as_posix(), path

    def _scope_roots(self, owner_principal_id: str | None) -> list[ScopeRoot]:
        """The places the Knowledge Map may look for this owner.

        Raiker's own document areas plus the folders this owner granted — never
        the workspace root, which is what made the picker list Raiker's whole
        installation and offer to index it.
        """
        # Scoped to this owner's projects, exactly as the Projects page is: a
        # root list built from every project in the workspace would offer
        # another account's folder as somewhere to browse.
        user_id = (
            self.store.principal_user_id(owner_principal_id) if owner_principal_id else None
        )
        projects = self.store.list_projects(user_id)
        grants = (
            self.store.list_brain_source_grants(owner_principal_id)
            if owner_principal_id
            else []
        )
        return build_roots(self.workspace_root.resolve(), projects, grants)

    def _scoped_source(
        self, raw_path: str, *, owner_principal_id: str | None
    ) -> tuple[ScopeRoot, str, Path]:
        try:
            return resolve(self._scope_roots(owner_principal_id), raw_path)
        except ScopeError as exc:
            raise ValueError(exc.reason) from exc

    def brain_source_roots(self, *, owner_principal_id: str) -> dict[str, Any]:
        """What the picker opens on: the boundary itself, named."""
        return {"roots": [root.to_dict() for root in self._scope_roots(owner_principal_id)]}

    def add_brain_source(self, raw_path: str, *, owner_principal_id: str) -> dict[str, Any]:
        root, relative, _path = self._scoped_source(
            raw_path, owner_principal_id=owner_principal_id
        )
        stored = scope_path(root, relative)
        self.store.add_brain_source(owner_principal_id, stored)
        return {"ok": True, "path": stored}

    def remove_brain_source(self, raw_path: str, *, owner_principal_id: str) -> dict[str, Any]:
        try:
            root, relative, _path = self._scoped_source(
                raw_path, owner_principal_id=owner_principal_id
            )
            stored = scope_path(root, relative)
        except ValueError:
            # A source recorded before this boundary existed, or one whose
            # folder has since gone: removing it must still work, or the owner
            # cannot clear a source they can see.
            stored = raw_path.strip()
        self.store.remove_brain_source(owner_principal_id, stored)
        return {"ok": True, "path": stored}

    def grant_brain_source_folder(
        self, raw_path: str, *, owner_principal_id: str
    ) -> dict[str, Any]:
        """Record the owner granting one folder on this machine.

        The folder is read where it is. Nothing is copied into the workspace by
        granting it, which is the difference between this and an upload.
        """
        candidate = (raw_path or "").strip()
        if not candidate or len(candidate) > MAX_SOURCE_PATH_CHARS:
            raise ValueError("invalid_brain_source_path")
        path = Path(candidate).expanduser()
        if not path.is_absolute():
            raise ValueError("brain_grant_requires_absolute_path")
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise ValueError("brain_grant_not_found") from exc
        if not resolved.is_dir():
            raise ValueError("brain_grant_not_a_directory")
        runtime_dir = (self.workspace_root / RUNTIME_DIR_NAME).resolve()
        if resolved == runtime_dir or runtime_dir in resolved.parents:
            # The runtime directory is Raiker's own machinery, and its documents
            # are already offered as their own roots.
            raise ValueError("brain_grant_is_runtime_directory")
        root_id = grant_root_id(resolved)
        self.store.add_brain_source_grant(
            owner_principal_id, root_id, str(resolved), resolved.name or str(resolved)
        )
        self._record_brain_grant_event("brain_source_folder_granted", root_id, str(resolved))
        return {"ok": True, "root_id": root_id, "path": str(resolved)}

    def _record_brain_grant_event(self, event_type: str, root_id: str, path: str) -> None:
        """Granting Raiker access to a folder is a governed step, so it is one
        the audit log carries — with the path, because the owner needs to see
        exactly what they opened and when."""
        from raiker.events.types import make_event

        EventLogWriter(self.store).append(
            make_event(
                session_id="authz",
                turn_id=None,
                event_type=event_type,
                actor="dashboard_service",
                payload={"root_id": root_id, "path": path},
            )
        )

    # A file picked from the owner's computer arrives as bytes, so adding it is
    # necessarily a copy. That makes consent the whole design: `store_copy` has
    # to be explicitly true, the copy lands in one named place the owner can
    # find and delete, and the alternative — granting the folder and reading it
    # where it is — is offered beside it in the dialog.
    def upload_brain_source_file(
        self, filename: str, content_base64: str, store_copy: bool, *, owner_principal_id: str
    ) -> dict[str, Any]:
        if not store_copy:
            raise ValueError("brain_upload_copy_not_authorised")
        name = Path((filename or "").strip()).name
        if not name or name.startswith(".") or len(name) > 200:
            raise ValueError("brain_upload_invalid_filename")
        if Path(name).suffix.casefold() not in KNOWLEDGE_SOURCE_EXTENSIONS:
            raise ValueError("brain_upload_unsupported_file_type")
        try:
            content = base64.b64decode(content_base64.encode("ascii"), validate=True)
        except (ValueError, UnicodeEncodeError) as exc:
            raise ValueError("brain_upload_invalid_content") from exc
        if not content:
            raise ValueError("brain_upload_empty")
        if len(content) > MAX_KNOWLEDGE_UPLOAD_BYTES:
            raise ValueError("brain_upload_too_large")
        destination_dir = internal_io_path(
            self.workspace_root / RUNTIME_DIR_NAME / "artifacts" / KNOWLEDGE_UPLOAD_DIR
        )
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / name
        if destination.exists():
            stem, suffix = Path(name).stem, Path(name).suffix
            destination = destination_dir / f"{stem}-{uuid4().hex[:6]}{suffix}"
        destination.write_bytes(content)
        stored = f"{ARTIFACTS_ROOT_ID}/{KNOWLEDGE_UPLOAD_DIR}/{destination.name}"
        self.store.add_brain_source(owner_principal_id, stored)
        return {
            "ok": True,
            "path": stored,
            "stored_copy": True,
            "byte_size": len(content),
        }

    def revoke_brain_source_folder(
        self, root_id: str, *, owner_principal_id: str
    ) -> dict[str, Any]:
        cleaned = (root_id or "").strip()
        if not cleaned:
            raise ValueError("invalid_brain_source_path")
        revoked = next(
            (
                grant
                for grant in self.store.list_brain_source_grants(owner_principal_id)
                if str(grant.get("root_id")) == cleaned
            ),
            None,
        )
        self.store.remove_brain_source_grant(owner_principal_id, cleaned)
        self._record_brain_grant_event(
            "brain_source_folder_revoked", cleaned, str((revoked or {}).get("path", ""))
        )
        return {"ok": True, "root_id": cleaned}

    def browse_brain_sources(
        self, raw_path: str = "", *, owner_principal_id: str | None = None
    ) -> dict[str, Any]:
        """Browse one contained directory inside one root, and nothing above it."""
        roots = self._scope_roots(owner_principal_id)
        if not (raw_path or "").strip() or raw_path.strip() in {".", "/"}:
            # There is no path meaning "the workspace", so the empty request
            # answers with the boundary rather than with a listing.
            return {
                "path": "",
                "parent": None,
                "roots": [root.to_dict() for root in roots],
                "children": [],
                "truncated": False,
            }
        try:
            root, relative, path = resolve(roots, raw_path)
        except ScopeError as exc:
            raise ValueError(exc.reason) from exc
        if not path.is_dir():
            raise ValueError("brain_source_not_a_directory")
        try:
            values = sorted(
                path.iterdir(), key=lambda item: (not item.is_dir(), item.name.casefold())
            )
        except OSError as exc:
            raise ValueError("brain_source_unreadable") from exc
        base = root.path.resolve() if root.path is not None else path
        children: list[dict[str, Any]] = []
        for child in values[:200]:
            try:
                if child.name in SKIPPED_DIRECTORY_NAMES or child.name.startswith("."):
                    continue
                resolved_child = child.resolve()
                # Re-checked after resolution: a symlink inside a granted folder
                # must not become a way out of it.
                if base not in resolved_child.parents:
                    continue
                children.append(
                    {
                        "name": child.name,
                        "path": scope_path(root, resolved_child.relative_to(base).as_posix()),
                        "kind": "folder" if child.is_dir() else "file",
                        "size_bytes": child.stat().st_size if child.is_file() else None,
                    }
                )
            except OSError:
                continue
        return {
            "path": scope_path(root, relative),
            "parent": parent_scope_path(root, relative),
            "roots": [item.to_dict() for item in roots],
            "children": children,
            "truncated": len(values) > 200,
        }

    def review_brain_source(
        self, raw_path: str, *, owner_principal_id: str | None = None
    ) -> dict[str, Any]:
        """Build a bounded, read-only indexing plan before a source is selected."""
        root, relative, path = self._scoped_source(
            raw_path, owner_principal_id=owner_principal_id
        )
        relative_path = scope_path(root, relative)
        candidates = [path] if path.is_file() else path.rglob("*")
        supported = 0
        unsupported = 0
        total_bytes = 0
        scanned = 0
        examples: list[str] = []
        warnings: list[str] = []
        # Containment is judged against the root that was selected, not against
        # the workspace: a granted folder lives outside the workspace entirely,
        # and everything under it — and nothing above it — is in scope.
        base = root.path.resolve() if root.path is not None else path
        for candidate in candidates:
            if scanned >= 5000:
                warnings.append("More than 5,000 entries were found; review is capped and indexing will remain incremental.")
                break
            try:
                resolved = candidate.resolve()
                if resolved != base and base not in resolved.parents:
                    continue
                if not candidate.is_file() or any(
                    part in SKIPPED_DIRECTORY_NAMES or part.startswith(".")
                    for part in candidate.relative_to(base).parts
                ):
                    continue
                size = candidate.stat().st_size
            except (OSError, ValueError):
                continue
            scanned += 1
            if candidate.suffix.casefold() in KNOWLEDGE_SOURCE_EXTENSIONS and size <= 5 * 1024 * 1024:
                supported += 1
                total_bytes += size
                if len(examples) < 8:
                    examples.append(scope_path(root, resolved.relative_to(base).as_posix()))
            else:
                unsupported += 1
        if total_bytes > 100 * 1024 * 1024:
            warnings.append("The selected source exceeds 100 MB; content will be loaded incrementally as it is needed.")
        if unsupported:
            warnings.append(f"{unsupported} unsupported or oversized file(s) will be skipped.")
        return {
            "path": relative_path,
            "kind": "folder" if path.is_dir() else "file",
            "supported_files": supported,
            "unsupported_files": unsupported,
            "total_bytes": total_bytes,
            "examples": examples,
            "warnings": warnings,
            "review_cap": 5000,
        }

    def get_brain_preferences(self, owner_principal_id: str) -> dict[str, Any]:
        return {"settings": self.store.load_brain_preferences(owner_principal_id)}

    def save_brain_preferences(
        self, settings: dict[str, Any], *, owner_principal_id: str
    ) -> dict[str, Any]:
        allowed = {"transform", "display", "forces", "groups", "positions", "filters", "motion"}
        clean = {key: value for key, value in settings.items() if key in allowed}
        serialized = json.dumps(clean, sort_keys=True)
        if len(serialized) > 100_000:
            raise ValueError("brain_preferences_too_large")
        if not all(isinstance(value, (dict, list, str, int, float, bool, type(None))) for value in clean.values()):
            raise ValueError("invalid_brain_preferences")
        updated_at = self.store.save_brain_preferences(owner_principal_id, clean)
        return {"ok": True, "settings": clean, "updated_at": updated_at}

    def execution_environments(self, owner_principal_id: str) -> dict[str, Any]:
        """List selectable execution targets without exposing credential values."""
        selected = self.store.selected_execution_environment(owner_principal_id)
        allowed_images = sorted(container_image_allowlist())
        gate = self.control.get_capability_gate(
            "container_execution_cap", owner_principal_id
        )
        gate_enabled = gate is not None and gate.state not in _DISABLED_STATES
        default_image = allowed_images[0] if allowed_images else None
        default_profile = ExecutionProfile(
            "container_default",
            "container",
            name="Local container",
            runtime="docker",
            image=default_image,
            tools=("shell",),
            repository_access="read_only",
            writable_output=True,
        )
        default_probe = probe_execution_profile(default_profile)
        default_reason = (
            "container_gate_disabled"
            if not gate_enabled
            else (
                "container_image_required:container_default"
                if default_image is None
                else default_probe.reason_code
            )
        )
        local_profile = ExecutionProfile("local_native", "local")
        # The native boundary is measured, not declared: this probe runs the
        # real sandbox over the real workspace before the card can say anything
        # about it.
        native_profile = next(
            profile
            for profile in DEFAULT_EXECUTION_PROFILES
            if profile.profile_id == "native_sandbox"
        )
        native_probe = probe_execution_profile(
            native_profile, workspace_root=self.store.paths.workspace_root
        )
        environments: list[dict[str, Any]] = [
            {
                "profile_id": "local_native", "kind": "local", "name": "Local strict",
                "enabled": True, "configured": True, "available": True,
                "status": "ready", "selected": selected == "local_native",
                "credential_configured": True, "budget": None, "cost": None,
                "selected_for_commands": selected == "local_native",
                "assigned_tools": ["run_command"],
                "features": asdict(local_profile.features),
                "probe_checked_at": utc_now(),
                "availability_reason": None,
                "boundary": "host_reduced_isolation",
                "probe_observations": {},
            },
            {
                "profile_id": "native_sandbox", "kind": "native", "name": "Native OS sandbox",
                "enabled": True, "configured": True,
                "available": native_probe.available,
                "status": "ready" if native_probe.available else "unavailable",
                "selected": selected == "native_sandbox",
                "credential_configured": True, "budget": None, "cost": None,
                "selected_for_commands": selected == "native_sandbox",
                "assigned_tools": ["shell", "run_command"],
                "features": asdict(native_probe.features or native_profile.features),
                "probe_checked_at": native_probe.checked_at,
                "availability_reason": native_probe.reason_code,
                "boundary": native_probe.boundary,
                "probe_observations": dict(native_probe.observations),
                "runner_trust": native_probe.runner_trust,
            },
            {
                "profile_id": "container_default", "kind": "container", "name": "Local container",
                "enabled": True, "configured": default_image is not None,
                "available": default_reason is None,
                "status": "ready" if default_reason is None else "unavailable",
                "selected": selected == "container_default", "credential_configured": True, "budget": None,
                "cost": None, "runtime": "docker", "image": default_image,
                "repository_access": "read_only", "writable_output": True,
                "assigned_tool_count": 1, "availability_reason": default_reason,
                "selected_for_commands": selected == "container_default",
                "assigned_tools": ["shell"],
                "features": asdict(default_profile.features),
                "probe_checked_at": default_probe.checked_at,
            },
        ]
        for row in self.store.list_remote_execution_profiles(owner_principal_id=owner_principal_id):
            try:
                config = json.loads(row["config_json"])
            except (TypeError, ValueError):
                config = {}
            kind = "daytona" if row["profile_type"] == "cloud" else str(row["profile_type"])
            if kind == "container":
                raw_tools = config.get("tools", [])
                tools = (
                    tuple(str(tool) for tool in raw_tools if isinstance(tool, str))
                    if isinstance(raw_tools, list)
                    else ()
                )
                profile = ExecutionProfile(
                    str(row["profile_id"]),
                    "container",
                    name=str(row["name"]),
                    enabled=bool(row["enabled"]),
                    runtime=cast(ContainerRuntime | None, config.get("runtime")),
                    image=str(config.get("image") or "") or None,
                    tools=tools,
                    repository_access=cast(
                        RepositoryAccess, config.get("repository_access", "none")
                    ),
                    writable_output=bool(config.get("writable_output", False)),
                    config={**config, "owner_principal_id": owner_principal_id},
                )
                reason = validate_execution_profile(profile)
                if reason is None and profile.image not in container_image_allowlist():
                    reason = f"container_image_not_allowed:{profile.profile_id}"
                if reason is None and not gate_enabled:
                    reason = "container_gate_disabled"
                proof = probe_execution_profile(profile)
                if reason is None:
                    reason = proof.reason_code
                available = bool(profile.enabled and reason is None)
                environments.append(
                    {
                        "profile_id": profile.profile_id,
                        "kind": "container",
                        "name": profile.name,
                        "enabled": profile.enabled,
                        "configured": validate_execution_profile(profile) is None,
                        "available": available,
                        "status": "ready" if available else "unavailable",
                        "selected": selected == profile.profile_id,
                        "credential_configured": True,
                        "budget": None,
                        "cost": None,
                        "runtime": profile.runtime,
                        "image": profile.image,
                        "repository_access": profile.repository_access,
                        "writable_output": profile.writable_output,
                        "assigned_tool_count": len(profile.tools),
                        "selected_for_commands": selected == profile.profile_id,
                        "assigned_tools": list(profile.tools),
                        "features": asdict(profile.features),
                        "probe_checked_at": proof.checked_at,
                        "availability_reason": reason,
                        "config": {
                            "runtime": profile.runtime,
                            "image": profile.image,
                            "tools": list(profile.tools),
                            "repository_access": profile.repository_access,
                            "writable_output": profile.writable_output,
                            "egress_domains": list(config.get("egress_domains", [])),
                            "egress_ports": list(config.get("egress_ports", [])),
                            # Configuration is a request, not enforcement. This
                            # remains false until the real container bypass
                            # probe records a passing measurement.
                            "egress_enforcement": "not_proven",
                        },
                    }
                )
                continue
            credential_env = str(config.get("credential_env") or config.get("api_key_env") or "")
            credential_configured = bool(credential_env and os.environ.get(credential_env, "").strip())
            configured = (
                bool(
                    config.get("host")
                    and config.get("user")
                    and config.get("host_public_key")
                    and config.get("host_key_sha256")
                    and credential_env
                )
                if kind == "ssh"
                else bool(config.get("sandbox_id") and credential_env)
            )
            remote_profile = ExecutionProfile(
                str(row["profile_id"]),
                cast(Any, kind),
                name=str(row["name"]),
                enabled=bool(row["enabled"]),
                tools=("shell",),
                config={**config, "owner_principal_id": owner_principal_id},
            )
            remote_proof = (
                probe_execution_profile(
                    remote_profile, workspace_root=self.store.paths.workspace_root
                )
                if configured and credential_configured
                else None
            )
            available = bool(
                row["enabled"]
                and configured
                and credential_configured
                and remote_proof is not None
                and remote_proof.available
            )
            budget = config.get("max_cost") if kind == "daytona" else None
            cost = self.store.cloud_execution_cost_summary(
                owner_principal_id, str(row["profile_id"]), max_cost=float(budget or 0)
            ) if kind == "daytona" else None
            environments.append(
                {
                    "profile_id": str(row["profile_id"]), "kind": kind, "name": str(row["name"]),
                    "enabled": bool(row["enabled"]), "configured": configured, "available": available,
                    "status": "ready" if available else ("credential_required" if configured and not credential_configured else "unavailable" if remote_proof is not None else "configuration_required"),
                    "selected": selected == row["profile_id"], "credential_configured": credential_configured,
                    "budget": budget,
                    "cost": cost,
                    "selected_for_commands": selected == row["profile_id"],
                    "assigned_tools": ["shell"],
                    "features": asdict(remote_profile.features),
                    "probe_checked_at": remote_proof.checked_at if remote_proof is not None else utc_now(),
                    "boundary": remote_proof.boundary if remote_proof is not None else "remote_recipient_tcb",
                    "probe_observations": dict(remote_proof.observations) if remote_proof is not None else {},
                    "availability_reason": None if available else (remote_proof.reason_code if remote_proof is not None else (
                        "execution_environment_credential_required"
                        if configured and not credential_configured
                        else "execution_environment_configuration_required"
                    )),
                    "config": {key: value for key, value in config.items() if key not in {"password", "token", "api_key", "secret"}},
                }
            )
        if not any(item["selected"] for item in environments):
            environments[0]["selected"] = True
            selected = "local_native"
        return {
            "selected_profile_id": selected,
            "environments": environments,
            "container_options": {
                "runtimes": ["docker", "podman"],
                "images": allowed_images,
                "supported_tools": sorted(CONTAINER_PROFILE_TOOLS),
            },
        }

    def configure_execution_environment(
        self,
        *,
        profile_id: str | None,
        kind: str,
        name: str,
        config: dict[str, Any],
        enabled: bool,
        owner_principal_id: str,
    ) -> ControlResult:
        if kind not in {"ssh", "daytona", "container"}:
            return ControlResult(ok=False, reason_code="unsupported_execution_environment")
        forbidden = {"password", "token", "api_key", "secret", "private_key"}
        if any(key.casefold() in forbidden for key in config):
            return ControlResult(ok=False, reason_code="execution_credentials_must_use_environment_reference")
        if kind == "container":
            raw_tools = config.get("tools")
            tools = (
                tuple(str(tool) for tool in raw_tools if isinstance(tool, str))
                if isinstance(raw_tools, list)
                else ()
            )
            profile = ExecutionProfile(
                profile_id or "container_pending",
                "container",
                name=name.strip() or "Local container",
                enabled=enabled,
                runtime=cast(ContainerRuntime | None, config.get("runtime")),
                image=str(config.get("image") or "") or None,
                tools=tools,
                repository_access=cast(
                    RepositoryAccess, config.get("repository_access", "none")
                ),
                writable_output=bool(config.get("writable_output", False)),
            )
            reason = validate_execution_profile(profile)
            if reason:
                return ControlResult(ok=False, reason_code=reason)
            if profile.image not in container_image_allowlist():
                return ControlResult(ok=False, reason_code="container_image_not_allowed")
            raw_domains = config.get("egress_domains", [])
            raw_ports = config.get("egress_ports", [])
            if raw_domains or raw_ports:
                try:
                    from raiker.execution.commands.egress_policy import EgressPolicy

                    policy = EgressPolicy(
                        tuple(str(value) for value in raw_domains),
                        tuple(int(value) for value in raw_ports),
                    )
                except (TypeError, ValueError):
                    return ControlResult(ok=False, reason_code="container_egress_policy_invalid")
                config = {
                    **config,
                    "egress_domains": list(policy.domains),
                    "egress_ports": list(policy.ports),
                }
        env_key = "credential_env" if kind == "ssh" else "api_key_env"
        credential_env = str(config.get(env_key, "")).strip()
        if kind != "container" and credential_env and not re.fullmatch(r"[A-Z][A-Z0-9_]{2,127}", credential_env):
            return ControlResult(ok=False, reason_code="invalid_execution_credential_reference")
        if kind == "ssh":
            host = str(config.get("host", "")).strip()
            user = str(config.get("user", "")).strip()
            if not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", host) or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", user):
                return ControlResult(ok=False, reason_code="invalid_ssh_profile")
            try:
                from raiker.execution.commands.known_hosts import host_key_fingerprint

                if host_key_fingerprint(str(config.get("host_public_key", ""))) != str(
                    config.get("host_key_sha256", "")
                ).strip():
                    return ControlResult(
                        ok=False, reason_code="ssh_host_key_fingerprint_mismatch"
                    )
            except ValueError:
                return ControlResult(ok=False, reason_code="ssh_host_key_invalid")
        elif kind == "daytona" and not str(config.get("sandbox_id", "")).strip():
            return ControlResult(ok=False, reason_code="daytona_sandbox_required")
        elif kind == "daytona":
            try:
                if float(config.get("max_cost", 0) or 0) <= 0:
                    return ControlResult(ok=False, reason_code="daytona_budget_required")
            except (TypeError, ValueError):
                return ControlResult(ok=False, reason_code="daytona_budget_required")
        now = utc_now()
        existing = self.store.load_remote_execution_profile(
            profile_id or "", owner_principal_id=owner_principal_id
        )
        actual_id = str(existing["profile_id"]) if existing else new_id("rex_")
        from raiker.contracts.models import RemoteExecutionProfile

        self.store.insert_remote_execution_profile(
            RemoteExecutionProfile(
                actual_id,
                "ssh" if kind == "ssh" else ("cloud" if kind == "daytona" else "container"),
                name.strip() or (
                    "SSH host" if kind == "ssh" else (
                        "Daytona sandbox" if kind == "daytona" else "Local container"
                    )
                ),
                json.dumps(config, sort_keys=True),
                enabled,
                owner_principal_id,
                str(existing["created_at"]) if existing else now,
                now,
            )
        )
        return ControlResult(ok=True, data={"profile_id": actual_id})

    def select_execution_environment(
        self, profile_id: str, owner_principal_id: str
    ) -> ControlResult:
        view = self.execution_environments(owner_principal_id)
        environment = next((item for item in view["environments"] if item["profile_id"] == profile_id), None)
        if environment is None:
            return ControlResult(ok=False, reason_code="unknown_execution_environment")
        if not environment["available"]:
            return ControlResult(ok=False, reason_code="execution_environment_unavailable")
        self.store.select_execution_environment(owner_principal_id, profile_id)
        return ControlResult(ok=True, data={"selected_profile_id": profile_id})

    def reset_execution_environment(
        self, profile_id: str, session_id: str, *, recreate: bool, owner_principal_id: str
    ) -> ControlResult:
        """Take a session's persistent boundary away, on the owner's word (BUG-194).

        Only a boundary that *is* persistent can be reset, and the refusal says
        which it is: offering the control on a profile that rebuilds itself
        around every command would be offering an action with no effect.
        """
        view = self.execution_environments(owner_principal_id)
        environment = next(
            (item for item in view["environments"] if item["profile_id"] == profile_id), None
        )
        if environment is None:
            return ControlResult(ok=False, reason_code="unknown_execution_environment")
        if not environment.get("features", {}).get("persistent_environment"):
            return ControlResult(
                ok=False, reason_code="execution_environment_not_persistent"
            )
        if not session_id.strip():
            return ControlResult(ok=False, reason_code="execution_environment_session_required")
        from raiker.execution.commands.service import CommandService

        service = CommandService.for_workspace(self.workspace_root)
        reset = service.reset_environment(
            owner_principal_id, session_id, profile_id, recreate=recreate
        )
        if not reset:
            return ControlResult(ok=False, reason_code="execution_environment_reset_unavailable")
        return ControlResult(
            ok=True,
            data={"profile_id": profile_id, "session_id": session_id, "recreated": recreate},
        )

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
        indexed = self._index_code_map(
            relative_path, repo_id, owner_principal_id, user_id
        )
        return ControlResult(
            ok=True,
            data={
                "repo_id": repo_id,
                "kind": "local",
                "local_subpath": relative_path,
                "code_map": indexed,
            },
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
        row = None
        if repo_id is not None:
            row = self.store.load_code_repo(owner_principal_id, repo_id)
            if row is None:
                return ControlResult(ok=False, reason_code="unknown_repo")
        self.store.select_code_repo(owner_principal_id, repo_id)
        # B9 — selecting a repository that was connected before the code map
        # existed (or before the owner turned it on) is the other moment the map
        # should be built. Already-indexed repositories are left alone: selecting
        # is not a request to re-scan.
        indexed = None
        if row is not None and str(row.get("kind", "")) == "local":
            from raiker.graph.codemap_service import CodeMapService

            subpath = str(row.get("local_subpath") or "")
            service = CodeMapService(
                self.workspace_root, self.store, principal_id=owner_principal_id
            )
            if subpath and service.index_row(subpath) is None:
                indexed = self._index_code_map(subpath, repo_id or "", owner_principal_id, None)
        return ControlResult(
            ok=True, data={"selected_repo_id": repo_id, "code_map": indexed}
        )

    # ── B9: the repository code map ──────────────────────────────────────────

    def code_map_status(self, *, owner_principal_id: str) -> dict[str, Any]:
        """What Build shows about the index: the gate, the repository, the counts."""
        from raiker.graph.codemap_service import CodeMapService

        return CodeMapService(
            self.workspace_root, self.store, principal_id=owner_principal_id
        ).status()

    def code_map_paths(
        self, *, owner_principal_id: str, fragment: str, limit: int = 12
    ) -> dict[str, Any]:
        """Paths matching an `@`-mention fragment, from the index the owner built."""
        from raiker.graph.codemap_service import CodeMapService

        return CodeMapService(
            self.workspace_root, self.store, principal_id=owner_principal_id
        ).complete_paths(fragment, limit=limit)

    def rebuild_code_map(
        self, *, owner_principal_id: str, user_id: str | None = None
    ) -> ControlResult:
        """Re-scan the selected repository on the owner's explicit request."""
        from raiker.graph.codemap_service import CodeMapService

        service = CodeMapService(
            self.workspace_root, self.store, principal_id=owner_principal_id
        )
        result = service.build()
        if str(result.get("status", "")) not in ("indexed", "partial"):
            error = result.get("error", {}) if isinstance(result.get("error"), dict) else {}
            return ControlResult(
                ok=False, reason_code=str(error.get("type", "code_map_failed"))
            )
        self._record_repo_event(
            "code_map_indexed", owner_principal_id, user_id,
            {k: v for k, v in result.items() if k not in ("languages", "skipped")},
        )
        return ControlResult(ok=True, data=result)

    def _index_code_map(
        self,
        relative_path: str,
        repo_id: str,
        owner_principal_id: str,
        user_id: str | None,
    ) -> dict[str, Any] | None:
        """Index a just-connected folder, and say so in the audit trail.

        Best-effort by design: connecting a repository is bookkeeping that must
        succeed whether or not a scan can. A gate that is off, a folder that
        cannot be read, or a scan that raises leaves the reference connected and
        the map simply not built — which is what the Build panel then reports.
        """
        from raiker.graph.codemap_service import CodeMapService, CodeMapTarget
        from raiker.tools.git import resolve_repository_root

        try:
            service = CodeMapService(
                self.workspace_root, self.store, principal_id=owner_principal_id
            )
            if service.governance_refusal("Code map indexing") is not None:
                return None
            root = resolve_repository_root(self.workspace_root, relative_path)
            # `resolve_repository_root` falls back to the workspace root for a
            # sub-path it cannot contain. Indexing the whole workspace under the
            # folder's name would be a quietly wrong answer, so refuse instead.
            if root == self.workspace_root.resolve() and relative_path not in ("", "."):
                return None
            result = service.build(
                target=CodeMapTarget(
                    repo_path=relative_path, root=root, repo_id=repo_id, label=relative_path
                )
            )
        except Exception:  # noqa: BLE001 — a derived index never blocks the reference
            return None
        if str(result.get("status", "")) not in ("indexed", "partial"):
            return None
        self._record_repo_event(
            "code_map_indexed", owner_principal_id, user_id,
            {k: v for k, v in result.items() if k not in ("languages", "skipped")},
        )
        return result

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
        origin: str | None = None,
    ) -> list[SessionView]:
        """List the caller's sessions, newest first.

        ``origin`` filters by provenance (BUG-10): ``"chat"`` is the owner's own
        conversations, which is what a "recent chats" list means. Omitting it
        lists every session, so Sessions still shows task runs.
        """
        return [
            self._session_view(row)
            for row in self.store.list_sessions(
                limit=limit,
                project_id=project_id,
                user_id=user_id,
                include_archived=include_archived,
                origin=origin,
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
        approval_rows = [
            row
            for row in self.store.list_approvals()
            if str(row.get("session_id", "")) in session_ids
        ]
        approval_queue = self.store.suspended_turn_queue_positions(
            [str(row.get("approval_id", "")) for row in approval_rows]
        )
        approvals = [
            self._approval_view(row, queue=approval_queue) for row in approval_rows
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
        # BUG-218 — projects, which the map never drew even though the colour
        # for them was already defined. A session belongs to one, and "which
        # work belongs together" is the first question a map of your work is
        # asked.
        projects_by_id = {
            str(row["project_id"]): row
            for row in self.store.list_projects(user_id=user_id)
            if not row.get("is_archived")
        }
        used_projects: set[str] = set()

        for session in sessions:
            node_id = f"session:{session.session_id}"
            # BUG-218 — a Chat and a Build session were the same green dot. They
            # are different work and the store already knows which is which;
            # `origin` was simply never read here.
            origin = (getattr(session, "origin", "") or "chat").lower()
            node_type = SESSION_NODE_TYPES.get(origin, "session")
            nodes.append(
                BrainNodeView(
                    node_id,
                    node_type,
                    session.title or f"Untitled {SESSION_LABELS.get(origin, 'session')}",
                    session.status,
                    SESSION_LABELS.get(origin, origin),
                )
            )
            project_id = str(getattr(session, "project_id", "") or "")
            if project_id and project_id in projects_by_id:
                used_projects.add(project_id)
                edges.append(BrainEdgeView(f"project:{project_id}", node_id, "contains"))
            else:
                edges.append(BrainEdgeView(f"principal:{principal_id}", node_id, "owns"))
        for project_id in sorted(used_projects):
            row = projects_by_id[project_id]
            nodes.append(
                BrainNodeView(
                    f"project:{project_id}",
                    "project",
                    str(row.get("name") or "Untitled project"),
                    "active",
                    str(row.get("path") or ""),
                )
            )
            edges.append(
                BrainEdgeView(f"principal:{principal_id}", f"project:{project_id}", "owns")
            )
        for task in tasks:
            node_id = f"task:{task.task_id}"
            nodes.append(BrainNodeView(node_id, "task", task.title or "Untitled task", task.status, _task_detail(task), task.progress_percent))
            edges.append(BrainEdgeView(f"session:{task.session_id}", node_id, "tracks", task.status == "running"))
            # Only work that is actually waiting for its slot is scheduled work.
            # A task that has already run keeps its `scheduled_at`, so listing it
            # here showed a finished or blocked run as "Waiting" indefinitely.
            if task.scheduled_at and task.status == "queued":
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
        # BUG-218 — one node per *tool*, not one per event.
        #
        # This used to emit a node per row of `list_event_index(limit=250)`,
        # typed `tool`. Measured on a workspace after one live round: 20 of 22
        # nodes were that type, and not one was a tool — they were "turn
        # started", "model request completed" and their kin. The map read as a
        # map of the runtime's own bookkeeping, which is why chats, context and
        # files were invisible underneath it.
        #
        # `tool_actions` is where tools actually are, aggregated per session, so
        # a session that ran `read_file` forty times is one node saying forty
        # rather than forty nodes saying nothing.
        for use in self.store.summarize_session_tool_use(
            sorted(session_ids), owner_principal_id=principal_id
        ):
            session_key = str(use["session_id"])
            tool_name = str(use["tool_name"])
            node_id = f"tool:{session_key}:{tool_name}"
            uses = int(use["uses"] or 0)
            failures = int(use["failures"] or 0)
            nodes.append(
                BrainNodeView(
                    node_id,
                    "tool",
                    TOOL_LABELS.get(tool_name, tool_name.replace("_", " ")),
                    "failed" if failures and failures == uses else "used",
                    f"{uses} use{'' if uses == 1 else 's'}"
                    + (f", {failures} failed" if failures else ""),
                )
            )
            edges.append(BrainEdgeView(f"session:{session_key}", node_id, "used"))

        # BUG-218 — what the answers actually came from. `turn_sources` is the
        # citation record and the map never read it, so a map of the owner's
        # work showed no context at all. A source is drawn as the thing it is:
        # a cited file is a file node, a fetched page is a source node.
        context_nodes: set[str] = set()
        for cited in self.store.list_session_context_sources(
            sorted(session_ids), principal_id=principal_id
        ):
            locator = str(cited["locator"] or "")
            title = str(cited["title"] or "") or locator or str(cited["kind"])
            kind = str(cited["kind"] or "")
            # Identity is the thing cited, not the citation: the same file read
            # in three sessions is one node with three edges, which is the
            # relationship the map exists to show.
            node_id = f"context:{kind}:{locator or title}"
            # Emitted once even when several sessions cite it — the shared node
            # with an edge per session *is* the relationship this map exists to
            # show, and two nodes carrying one id would leave the force layout
            # drawing the same file twice.
            if node_id not in context_nodes:
                context_nodes.add(node_id)
                # MEM-14 — a citation whose file has since been deleted is drawn
                # as `missing` rather than omitted. Obsidian keeps its
                # unresolved links for the same reason: "this answer rested on
                # something that is gone" is more useful than a tidier map, and
                # dropping the node would leave the work looking ungrounded
                # instead of grounded in something that has moved.
                status = reference_resolution(
                    self.workspace_root,
                    kind=kind,
                    locator=locator,
                    attachment_id=str(cited["attachment_id"] or ""),
                    tool_name=str(cited["tool_name"] or ""),
                )
                nodes.append(
                    BrainNodeView(
                        node_id,
                        CONTEXT_NODE_TYPES.get(kind, "source"),
                        title[:80],
                        "missing" if status == "unresolved" else "cited",
                        f"{kind}" + (f" · via {cited['tool_name']}" if cited["tool_name"] else ""),
                    )
                )
            edges.append(
                BrainEdgeView(f"session:{cited['session_id']}", node_id, "grounded_in")
            )

        # BUG-218 — files the owner attached to a conversation. Metadata only;
        # the stored bytes are never read to draw a node.
        for attached in self.store.list_session_attached_files(
            sorted(session_ids), owner_principal_id=principal_id
        ):
            node_id = f"attachment:{attached['attachment_id']}"
            nodes.append(
                BrainNodeView(
                    node_id,
                    "file",
                    str(attached["filename"]),
                    "attached",
                    str(attached["media_type"]),
                )
            )
            edges.append(
                BrainEdgeView(f"session:{attached['session_id']}", node_id, "attached")
            )

        event_ids = {event.event_id for event in events}
        # One lookup for every memory whose source event is outside the window,
        # rather than one per memory.
        distant = self.store.sessions_for_events(
            [m.source_event_id for m in memories if m.source_event_id not in event_ids]
        )
        for memory in memories:
            node_id = f"memory:{memory.memory_id}"
            nodes.append(BrainNodeView(node_id, "memory", f"Memory · {memory.scope}", "available", memory.sensitivity))
            # BUG-218 — a memory whose source event fell outside the event
            # window used to be drawn with no edge at all: a fact floating free
            # of the work that produced it. The session is the durable anchor,
            # so it is the fallback rather than leaving the node orphaned.
            if memory.source_event_id in event_ids:
                edges.append(BrainEdgeView(f"event:{memory.source_event_id}", node_id, "remembered"))
            elif distant.get(memory.source_event_id, "") in session_ids:
                edges.append(
                    BrainEdgeView(
                        f"session:{distant[memory.source_event_id]}", node_id, "remembered"
                    )
                )
            else:
                # Neither reachable: the owner still owns it, and an anchored
                # node is more honest than a floating one.
                edges.append(BrainEdgeView(f"principal:{principal_id}", node_id, "remembers"))
        # MEM-06 — reviewed entity facts are first-class graph records. Every
        # relation remains connected to the approved memory that evidenced it;
        # an edge can therefore be inspected instead of trusted as inference.
        entity_nodes: set[str] = set()
        memory_node_ids = {f"memory:{memory.memory_id}" for memory in memories}
        for relationship in self.store.list_memory_relationships(principal_id):
            subject = f"entity:{relationship['subject_entity_id']}"
            object_id = f"entity:{relationship['object_entity_id']}"
            if subject not in entity_nodes:
                entity_nodes.add(subject)
                nodes.append(
                    BrainNodeView(
                        subject,
                        "entity",
                        str(relationship["subject_name"]),
                        "reviewed",
                        str(relationship["subject_type"]),
                    )
                )
            if object_id not in entity_nodes:
                entity_nodes.add(object_id)
                nodes.append(
                    BrainNodeView(
                        object_id,
                        "entity",
                        str(relationship["object_name"]),
                        "reviewed",
                        str(relationship["object_type"]),
                    )
                )
            edges.append(
                BrainEdgeView(
                    subject,
                    object_id,
                    str(relationship["predicate"]),
                    False,
                    str(relationship["relationship_id"]),
                    str(relationship["evidence_memory_id"]),
                    True,
                )
            )
            evidence = f"memory:{relationship['evidence_memory_id']}"
            if evidence in memory_node_ids:
                edges.append(BrainEdgeView(evidence, subject, "evidence_for"))

        for approval in approvals:
            node_id = f"approval:{approval.approval_id}"
            nodes.append(BrainNodeView(node_id, "approval", approval.tool_name, approval.status, approval.capability))
            edges.append(BrainEdgeView(f"session:{approval.session_id}", node_id, "requires"))
        for backup in backups:
            node_id = f"backup:{backup['manifest_id']}"
            nodes.append(BrainNodeView(node_id, "backup", "Backup", "verified" if backup.get("restore_verified_at") else "catalogued"))
            edges.append(BrainEdgeView(f"principal:{principal_id}", node_id, "backs_up"))
        # Sources are addressed within the Knowledge Map's boundary, so a stored
        # source that no longer resolves — its grant revoked, its folder gone —
        # simply drops out of the graph rather than being drawn from a stale path.
        roots = self._scope_roots(principal_id)
        for source in self.store.list_brain_sources(principal_id):
            try:
                source_root, relative, path = resolve(roots, source)
            except ScopeError:
                continue
            relative_path = scope_path(source_root, relative)
            base = source_root.path.resolve() if source_root.path is not None else path
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
                    child_path = scope_path(
                        source_root, child.resolve().relative_to(base).as_posix()
                    )
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

    # ── BUG-22: conversation transcript export ───────────────────────────

    def build_session_transcript(
        self,
        session_id: str,
        *,
        user_id: str | None,
        principal_id: str | None,
    ) -> Any | None:
        """A redacted, scoped transcript ready to render, or None if not visible.

        Visibility is the existing session boundary — this reads through
        ``get_session``, so an export can never reach a conversation the caller
        could not already open. Attachment metadata is folded in so the review
        step can name every file the transcript will list.
        """
        from raiker.sessions.transcript import build_transcript

        detail = self.get_session(session_id, user_id=user_id)
        if detail is None:
            return None
        files: list[Any] = []
        if principal_id:
            with contextlib.suppress(Exception):
                from raiker.runtime.attachment_preview import AttachmentPreviewService

                files = list(
                    AttachmentPreviewService(self.store).list_session_files(
                        session_id, principal_id
                    )
                )
        sources_by_turn: dict[str, list[dict[str, Any]]] = {}
        if principal_id:
            with contextlib.suppress(Exception):
                for source in self.store.load_turn_sources(session_id, principal_id):
                    sources_by_turn.setdefault(str(source.get("turn_id", "")), []).append(source)
        return build_transcript(
            session_id=session_id,
            title=detail.session.title or "Untitled conversation",
            created_at=detail.session.created_at,
            turns=detail.turns,
            files=files,
            sources_by_turn=sources_by_turn,
        )

    def record_transcript_export(
        self,
        session_id: str,
        *,
        acting_principal_id: str,
        export_format: str,
        message_count: int,
        file_count: int,
        byte_size: int,
    ) -> None:
        """Audit that a transcript left the runtime. Metadata only, never text."""
        from raiker.contracts.models import AgentEvent
        from raiker.sessions.transcript import REDACTION_POLICY

        with contextlib.suppress(Exception):
            EventLogWriter(self.store).append(
                AgentEvent(
                    event_id=new_id("evt_"),
                    timestamp=utc_now(),
                    session_id=session_id,
                    turn_id=None,
                    event_type="session_transcript_exported",
                    actor=acting_principal_id,
                    payload={
                        "format": export_format,
                        "message_count": message_count,
                        "file_count": file_count,
                        "byte_size": byte_size,
                        "redaction_policy": REDACTION_POLICY,
                    },
                )
            )

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

    def _dispatch_session_end_hook(self, session_id: str, reason: str) -> None:
        """`SessionEnd` for the one thing that really ends a web conversation.

        The event was in the config schema from the start and had no call site,
        because "what ends a session" has no obvious answer on the web: a browser
        tab closing is not a decision, and a conversation left idle is not over.
        Archiving or deleting it is a decision the owner made, and it is the only
        point at which the conversation stops being somewhere work continues —
        so that is the boundary (BUG-223).

        Dispatched *before* a delete and *after* an archive, for the same reason
        in both cases: a handler should be able to read the transcript it is
        being told about. Observation only — a handler cannot refuse either.
        """
        from raiker.hooks.contracts import HookInput
        from raiker.hooks.factory import dispatcher_for_workspace

        try:
            dispatcher = dispatcher_for_workspace(self.store)
            if not dispatcher.is_active():
                return
            dispatcher.dispatch(
                HookInput(
                    event_name="SessionEnd",
                    tool_name=None,
                    tool_input={},
                    context={"session_id": session_id, "reason": reason},
                    session_id=session_id,
                ),
                session_id=session_id,
                turn_id=None,
            )
        except Exception:  # noqa: BLE001 — a hook never blocks archiving or deleting
            return

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
        if archived:
            self._dispatch_session_end_hook(session_id, "archived")
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
                protocol_version=row.get("protocol_version"),
            )
            for row in self.store.list_mcp_servers(principal_id)
        ]

    def list_mcp_offers(self, principal_id: str) -> list[dict[str, Any]]:
        """MCP servers installed plugins *offer*, and whether each is already added.

        An offer is inert (BUG-221). It is a description of a server, read from
        the file the plugin wrote, and nothing about it is connected, stored as a
        server profile, or reachable. Adding one is the owner's action and runs
        the same governed create path as typing it in — which is the whole reason
        a plugin may offer one at all: it goes *through* the trust gate rather
        than around it.

        ``already_added`` is resolved against the owner's own servers by name, so
        an offer the owner has taken up reads as taken up rather than as a button
        that would fail with ``mcp_name_taken``.
        """
        from raiker.plugins.contributions import contributed_mcp_servers

        taken = {str(row.get("name")) for row in self.store.list_mcp_servers(principal_id)}
        return [
            {**offer, "plugin_id": plugin_id, "already_added": offer["name"] in taken}
            for plugin_id, offer in contributed_mcp_servers(self.workspace_root)
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

    def list_capability_containment(self, principal_id: str) -> dict[str, Any]:
        """Every monitored capability's containment state, in one owner-facing shape.

        BUG-77 — the security surface used to list containment for exactly one
        capability family. Monitored MCP connections keep their richer per-session
        view; this is the same three facts (state, reason, the control that clears
        it) for connectors, plugins, subagents, providers, tools and local
        execution, so nothing is contained without being visible.
        """
        from raiker.security.containment import (
            CAPABILITY_LABELS,
            CapabilityContainment,
        )

        views = CapabilityContainment(self.store).list(principal_id)
        return {
            "subjects": [view.to_dict() for view in views],
            "contained": sum(1 for view in views if view.contained),
            "capabilities": [
                {"id": capability, "label": label}
                for capability, label in sorted(CAPABILITY_LABELS.items())
            ],
        }

    def set_capability_containment(
        self, principal_id: str, capability: str, subject_id: str, action: str
    ) -> dict[str, Any]:
        """Pause, stop or resume one monitored subject. Every state is revocable."""
        from raiker.security.containment import CAPABILITY_LABELS, CapabilityContainment

        if capability not in CAPABILITY_LABELS:
            raise ValueError(f"unknown_capability:{capability}")
        containment = CapabilityContainment(self.store)
        if action == "pause":
            view = containment.pause(
                principal_id, capability, subject_id,
                reason="Paused by you. It will not run until you resume it.",
            )
        elif action == "kill":
            view = containment.kill(principal_id, capability, subject_id)
        elif action == "resume":
            view = containment.resume(principal_id, capability, subject_id)
        else:
            raise ValueError(f"unknown_containment_action:{action}")
        return view.to_dict()

    #: Event types the dispatcher writes, newest-first, for the hooks surface.
    _HOOK_EVENT_TYPES = (
        "hook_matched",
        "hook_executed",
        "hook_decision",
        "hook_timeout",
        "hook_failed",
    )

    def list_hooks(self, principal_id: str | None = None) -> dict[str, Any]:
        """What hooks are configured, whether they can fire, and what they did.

        Hooks were the one extension surface with a real, enforcing backend and no
        way to see it: they were configured by editing JSON on disk and observed
        only by reading the audit log by hand. Three things have to be true of
        this view for it to be worth more than that file:

        1. **A file Raiker could not read is visible.** A malformed hooks config
           contributes no rules by design; saying nothing about it would leave the
           owner believing a guard is in place that is not.
        2. **A rule that can never fire says so.** `HOOK_EVENTS` is what the schema
           accepts; `DISPATCHED_HOOK_EVENTS` is what this build emits, and a rule
           on the difference is configured but dead.
        3. **A rule that cannot change an outcome says so.** Only `PreToolUse` and
           `PreCompact` decisions are honoured, and only from a handler holding
           decision authority. Everything else observes.

        Read-only. Nothing here edits a hook: the config files are the owner's own
        text, and a surface that rewrote them would need its own authority story.
        """
        from raiker.hooks.contracts import (
            DECIDING_HOOK_EVENTS,
            DISPATCHED_HOOK_EVENTS,
            HOOK_EVENT_SUMMARIES,
            HOOK_EVENTS,
            HOOK_SCOPES,
            HookHandler,
        )
        from raiker.hooks.handlers.builtin import BUILTIN_HANDLERS
        from raiker.hooks.owner_switch import hooks_disabled
        from raiker.hooks.registry import HooksRegistry

        registry = HooksRegistry.load(self.workspace_root)
        rules: list[dict[str, Any]] = []
        for index, rule in enumerate(
            sorted(registry.rules, key=lambda r: (HOOK_SCOPES.index(r.scope), r.event, r.matcher))
        ):
            source = rule.source
            dispatched = rule.event in DISPATCHED_HOOK_EVENTS
            deciding = rule.event in DECIDING_HOOK_EVENTS
            # A builtin naming a handler this build does not have raises at
            # dispatch time and is recorded as `hook_failed`. The config parses,
            # the rule matches, and nothing happens — so it is the same class of
            # dead rule as an event that is never emitted, and is reported the
            # same way rather than being left to look enforcing.
            def _available(handler: HookHandler) -> bool:
                return handler.type != "builtin" or (handler.builtin or "") in BUILTIN_HANDLERS

            authoritative = any(
                (handler.decision_authority or handler.type == "builtin")
                and _available(handler)
                for handler in rule.handlers
            )
            rules.append(
                {
                    # Stable within one read, which is all a list key needs; hook
                    # rules have no identity of their own in the config format.
                    "rule_id": f"{rule.scope}:{rule.event}:{index}",
                    "event": rule.event,
                    "event_summary": HOOK_EVENT_SUMMARIES.get(rule.event, ""),
                    "matcher": rule.matcher,
                    "if_guard": rule.if_guard,
                    "scope": rule.scope,
                    "source": source,
                    "dispatched": dispatched,
                    # A rule can only change an outcome when the event is one the
                    # runtime asks about *and* a handler on it holds authority.
                    "can_decide": dispatched and deciding and authoritative,
                    "handlers": [
                        {
                            "id": handler.id,
                            "type": handler.type,
                            "target": (
                                " ".join(handler.command)
                                if handler.type == "command" and handler.command
                                else (handler.builtin or "")
                            ),
                            "timeout_ms": handler.timeout_ms,
                            # A builtin is Raiker's own code and always carries
                            # authority; a command carries it only when the owner
                            # said so in the config.
                            "decision_authority": (
                                handler.decision_authority or handler.type == "builtin"
                            )
                            and _available(handler),
                            # False only for a builtin this build does not ship.
                            # A command's program is resolved at dispatch time
                            # inside the workspace, so it is not checked here.
                            "available": _available(handler),
                        }
                        for handler in rule.handlers
                    ],
                }
            )

        activity: list[dict[str, Any]] = []
        counts: dict[str, int] = {}
        for event_type in self._HOOK_EVENT_TYPES:
            rows = self.store.list_event_index(event_type=event_type, limit=50)
            counts[event_type] = len(rows)
            for row in rows:
                activity.append(
                    {
                        "event_id": str(row["event_id"]),
                        "event_type": event_type,
                        "session_id": str(row.get("session_id", "")),
                        "timestamp": str(row.get("timestamp", "")),
                        "summary": row.get("summary"),
                    }
                )
        activity.sort(key=lambda entry: entry["timestamp"], reverse=True)

        # BUG-222 — off is a state to display, not a reason to hide what would
        # otherwise run: the rules stay listed and the page says they are off.
        disabled = (
            hooks_disabled(self.workspace_root, principal_id)
            if principal_id is not None
            else False
        )
        return {
            "active": not disabled and not registry.is_empty(),
            "disabled": disabled,
            "rule_count": len(rules),
            "rules": rules,
            "sources": [entry.to_dict() for entry in registry.sources],
            "failed_sources": [entry.to_dict() for entry in registry.failed_sources()],
            "events": [
                {
                    "event": event,
                    "summary": HOOK_EVENT_SUMMARIES.get(event, ""),
                    "dispatched": event in DISPATCHED_HOOK_EVENTS,
                    "can_decide": event in DECIDING_HOOK_EVENTS,
                }
                for event in sorted(HOOK_EVENTS)
            ],
            "builtins": sorted(BUILTIN_HANDLERS),
            "activity": activity[:40],
            "activity_counts": counts,
        }

    def list_plugins(self) -> dict[str, Any]:
        """Installed plugin records, what each one provides, and the signing posture.

        A plugin's signature is reported at the level it actually earned —
        ``verified``, ``present_only`` or ``unsigned`` — rather than as a boolean
        that reads the same whether an author was checked or not (BUG-79).

        Each record also carries what the plugin *provides*, read from the
        contribution files on disk rather than from the manifest that described
        them (BUG-221). The files are what the runtime loads, so this cannot
        report a contribution the runtime does not have — or miss one it does,
        which is the failure that would matter.
        """
        from raiker.plugins.contributions import installed_contributions
        from raiker.plugins.verify import (
            LEVEL_PRESENT_ONLY,
            LEVEL_UNSIGNED,
            LEVEL_VERIFIED,
            signature_verification,
            signing_posture,
        )

        posture = signing_posture()
        contributions = installed_contributions(self.workspace_root)
        plugins: list[dict[str, Any]] = []
        for row in self.store.list_plugin_install_records():
            signature = str(row.get("signature") or "")
            manifest = {
                "id": row.get("plugin_id"),
                "version": row.get("version"),
                "supply_chain": {
                    "checksum": row.get("checksum"),
                    "signature": signature or None,
                },
            }
            verification = signature_verification(manifest)
            # The stored record cannot be re-signed after the fact, so an install
            # made while a key was configured is reported at the level it earned
            # then; without a key today the honest answer is the weaker one.
            level = (
                LEVEL_VERIFIED
                if verification.level == LEVEL_VERIFIED
                else (LEVEL_PRESENT_ONLY if signature else LEVEL_UNSIGNED)
            )
            plugins.append(
                {
                    "record_id": row.get("record_id"),
                    "plugin_id": row.get("plugin_id"),
                    "version": row.get("version"),
                    "trust_level": row.get("trust_level"),
                    "status": row.get("status"),
                    "source_url": row.get("source_url"),
                    "installed_at": row.get("installed_at"),
                    "installed_by": row.get("installed_by"),
                    "checksum_present": bool(row.get("checksum")),
                    "signature": {**verification.to_dict(), "level": level},
                    # A revoked plugin's files are deleted with the revocation, so
                    # an empty contribution here is the same answer the runtime
                    # would give: it provides nothing.
                    "contributions": contributions.get(
                        str(row.get("plugin_id") or ""),
                        {
                            "hooks": 0,
                            "events": [],
                            "skills": 0,
                            "skill_names": [],
                            "mcp_servers": 0,
                            "mcp_server_names": [],
                            "error": None,
                        },
                    ),
                }
            )
        return {
            "plugins": plugins,
            "signing": posture,
            # What a plugin is allowed to contribute on this build, so the tab can
            # say what the surface *is* rather than only what is installed.
            "contribution_kinds": [
                {
                    "kind": "hooks",
                    "available": True,
                    "summary": (
                        "Hook rules at plugin scope — below managed, user, project "
                        "and local, so they can make an action stricter and never "
                        "override a deny you set."
                    ),
                },
                {
                    "kind": "skills",
                    "available": True,
                    "summary": (
                        "Instruction text validated by the same reader an upload "
                        "goes through. It arrives switched off and credited to the "
                        "plugin, so offering a skill and running with one stay two "
                        "separate decisions."
                    ),
                },
                {
                    "kind": "mcp_servers",
                    "available": True,
                    "summary": (
                        "A plugin may offer a server; it cannot add one. Nothing "
                        "is connected or stored until you add it, and adding it "
                        "runs the same governed create path as typing it in "
                        "yourself."
                    ),
                },
                {
                    "kind": "panels",
                    "available": False,
                    "summary": "Needs a route, permission and accessibility contract that does not exist.",
                },
            ],
        }

    # ── Channels (BUG-225) ──────────────────────────────────────────────────
    def list_channels(self, principal_id: str) -> dict[str, Any]:
        """Every connector profile, what it needs, and what is actually true today.

        The Channels tab said channels did not exist. The outbound executor, the
        inbound receiver, the capability gate and the egress boundary were all
        built; what was missing was any way for the owner to pair a connector, so
        `list_channel_pairings` stayed empty and both executors refused. The
        transport was unreachable because there was no surface, not because there
        was no transport — and the tab could not tell the difference.

        This reports each of the separate facts rather than collapsing them into
        one "ready" flag, because they have different remedies:

        * **Linked** — is there a pairing at all.
        * **Enabled** — is that pairing switched on. Linked is not enabled.
        * **Senders** — how many are allowlisted, for a profile that requires it.
          Enabled is not trusted.
        * **The capability gate** — `external_channel_runtime`, which the owner
          sets in Permissions and which no channel control here can widen.
        * **Egress** — whether `RAIKER_CHANNEL_EGRESS_ALLOWLIST` names any host.
          It defaults to empty and is fail-closed, so a channel that is linked,
          enabled and trusted still delivers nothing until the owner allowlists
          the destination.
        * **Inbound** — whether `RAIKER_CHANNEL_INBOUND_SECRET` is set. Without
          it the receiver refuses every message, which is the right default and a
          confusing one to meet without being told.

        Never returns a secret, a host, or a sender identifier — a count and a
        boolean answer every question this page asks.
        """
        import json as _json
        import os

        from raiker.api.routes_channels import channel_inbound_limit
        from raiker.channels.registry import ConnectorRegistry
        from raiker.runtime.executors.sandbox import channel_egress_allowlist

        try:
            profiles = ConnectorRegistry.load().profiles
        except Exception:  # noqa: BLE001 - an unreadable registry is a reported state
            return {
                "profiles": [],
                "error": "connector_registry_unavailable",
                "outbound": {},
                "inbound": {},
            }
        pairings = {
            str(row.get("connector_id")): row for row in self.store.list_channel_pairings()
        }
        gate = self.control.get_capability_gate("external_channel_runtime", principal_id)
        allowlist = channel_egress_allowlist()
        rows: list[dict[str, Any]] = []
        for profile in profiles:
            pairing = pairings.get(profile.connector_id)
            senders: list[str] = []
            if pairing is not None:
                try:
                    senders = list(_json.loads(pairing.get("sender_allowlist_json") or "[]"))
                except (ValueError, TypeError):
                    senders = []
            rows.append(
                {
                    "connector_id": profile.connector_id,
                    "channel_type": profile.channel_type,
                    "display_name": profile.display_name,
                    "transport": profile.transport,
                    "auth_method": profile.auth_method,
                    "default_state": profile.default_state,
                    "requires_pairing": profile.requires_pairing,
                    "requires_sender_allowlist": profile.requires_sender_allowlist,
                    "requires_network": profile.requires_network,
                    "linked": pairing is not None,
                    "enabled": bool(pairing.get("enabled")) if pairing else False,
                    "pairing_id": pairing.get("pairing_id") if pairing else None,
                    "display_label": pairing.get("display_name") if pairing else None,
                    "sender_count": len(senders),
                    # The identifiers themselves are the owner's contact list and
                    # never leave the store; the count answers the page's question.
                    "senders": senders,
                }
            )
        return {
            "profiles": rows,
            "error": None,
            "outbound": {
                "capability": "external_channel_runtime",
                "gate_state": gate.state if gate is not None else "unknown",
                "runtime_enabled": bool(gate.runtime_enabled) if gate is not None else False,
                "egress_configured": bool(allowlist),
                "egress_host_count": len(allowlist),
                # The webhook profile declares `signed_http_callback`. Without a
                # secret the executor still delivers — the owner controls both
                # ends of a webhook they configured — but the receiver cannot
                # tell a Raiker delivery from anything else that reaches the URL,
                # so the state is reported rather than assumed.
                "signing_configured": bool(
                    os.environ.get("RAIKER_CHANNEL_OUTBOUND_SECRET", "").strip()
                ),
            },
            "inbound": {
                "secret_configured": bool(
                    os.environ.get("RAIKER_CHANNEL_INBOUND_SECRET", "").strip()
                ),
                # Allowlisting says *who* may speak; the budget says how often.
                # They are different questions, and an allowlisted sender was
                # unbounded until one had an answer.
                "rate_limit_per_minute": channel_inbound_limit(),
                # Stated rather than implied: an inbound message is untrusted
                # content from a sender who is not the owner, it is quarantined,
                # and its instructions are inert. That is the accepted contract,
                # and the receiver enforces it on every message.
                "quarantined": True,
                "instructions_inert": True,
            },
        }

    def pair_channel(
        self,
        acting_principal_id: str | None,
        connector_id: str,
        display_name: str,
        sender_allowlist: list[str] | None = None,
    ) -> ControlResult:
        return self.control.pair_channel(
            acting_principal_id, connector_id, display_name, sender_allowlist
        )

    def set_channel_enabled(
        self, acting_principal_id: str | None, pairing_id: str, enabled: bool
    ) -> ControlResult:
        return self.control.set_channel_enabled(acting_principal_id, pairing_id, enabled)

    def set_channel_senders(
        self, acting_principal_id: str | None, pairing_id: str, senders: list[str]
    ) -> ControlResult:
        return self.control.set_channel_senders(acting_principal_id, pairing_id, senders)

    def unpair_channel(self, acting_principal_id: str | None, pairing_id: str) -> ControlResult:
        return self.control.unpair_channel(acting_principal_id, pairing_id)

    def deliver_channel_test(
        self, acting_principal_id: str | None, connector_id: str, url: str, text: str
    ) -> ControlResult:
        return self.control.deliver_channel_test(acting_principal_id, connector_id, url, text)

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
        # Before the row goes, so a handler can still read what it is told about.
        self._dispatch_session_end_hook(session_id, "deleted")
        if not self.store.delete_session(session_id, user_id=user_id):
            return ControlResult(ok=False, reason_code=f"unknown_session:{session_id}")
        return ControlResult(ok=True, data={"session_id": session_id})

    def delete_sessions(self, session_ids: list[str], acting_principal_id: str | None) -> ControlResult:
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        for session_id in session_ids:
            self._dispatch_session_end_hook(session_id, "deleted")
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
        histories = {
            e.memory_id: self.store.list_memory_lifecycle_events(
                e.memory_id, owner_principal_id=e.owner_principal_id
            )
            for e in entries
        }
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
                updated_at=e.updated_at,
                last_used_at=next(
                    (
                        event["created_at"]
                        for event in histories[e.memory_id]
                        if event["action"] == "recall"
                    ),
                    None,
                ),
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
        self.store.record_memory_lifecycle_event(
            memory_id, "pin" if pinned else "unpin", principal.principal_id
        )
        return ControlResult(ok=True, data={"memory_id": memory_id, "pinned": pinned})

    def list_memory_proposals(self, acting_principal_id: str | None) -> list[dict[str, Any]]:
        if not self._is_human(acting_principal_id):
            return []
        return self.store.list_memory_candidates(
            decision="deferred", owner_principal_id=acting_principal_id
        )

    def list_memory_relationship_proposals(
        self, acting_principal_id: str | None
    ) -> list[dict[str, Any]]:
        if not self._is_human(acting_principal_id):
            return []
        return self.store.list_memory_relationship_candidates(
            acting_principal_id or ""
        )

    def scan_memory_relationships(
        self, acting_principal_id: str | None
    ) -> ControlResult:
        """Owner-started, idempotent backfill over currently approved memory."""
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        from raiker.memory.entity_extraction import propose_memory_relationships

        scanned = proposed = skipped = already_present = 0
        for memory in self.store.list_approved_memory(
            limit=10_000,
            include_search_disabled=False,
            owner_principal_id=acting_principal_id,
        ):
            summary = propose_memory_relationships(
                self.store, str(memory["memory_id"]), acting_principal_id or ""
            )
            scanned += summary.scanned
            proposed += summary.proposed
            skipped += summary.skipped
            already_present += summary.already_present
        return ControlResult(
            ok=True,
            data={
                "scanned": scanned,
                "proposed": proposed,
                "skipped": skipped,
                "already_present": already_present,
            },
        )

    def decide_memory_relationship_proposal(
        self,
        candidate_id: str,
        *,
        decision: str,
        expected_decision: str,
        acting_principal_id: str | None,
    ) -> ControlResult:
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        if decision not in {"approved", "denied"}:
            return ControlResult(
                ok=False, reason_code="invalid_memory_relationship_decision"
            )
        try:
            relationship_id = self.store.resolve_memory_relationship_candidate_atomic(
                candidate_id,
                owner_principal_id=acting_principal_id or "",
                decision=decision,
                reviewer_id=acting_principal_id or "",
                expected_decision=expected_decision,
            )
        except ValueError as exc:
            if str(exc) == "stale_memory_relationship_candidate":
                return ControlResult(
                    ok=False, reason_code="stale_memory_relationship_proposal"
                )
            raise
        return ControlResult(
            ok=True,
            data={
                "candidate_id": candidate_id,
                "decision": decision,
                "relationship_id": relationship_id or None,
            },
        )

    def reject_memory_relationship(
        self,
        relationship_id: str,
        *,
        reason: str,
        expected_active: bool,
        acting_principal_id: str | None,
    ) -> ControlResult:
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        if not reason.strip():
            return ControlResult(
                ok=False, reason_code="memory_relationship_rejection_reason_required"
            )
        if not self.store.reject_memory_relationship(
            relationship_id,
            owner_principal_id=acting_principal_id or "",
            expected_active=expected_active,
        ):
            return ControlResult(ok=False, reason_code="stale_memory_relationship")
        self.store.record_memory_lifecycle_event(
            relationship_id,
            "reject",
            acting_principal_id or "",
            {"kind": "entity_relationship", "reason": reason.strip()},
        )
        return ControlResult(
            ok=True,
            data={"relationship_id": relationship_id, "active": False},
        )

    def decide_memory_proposal(
        self,
        candidate_id: str,
        *,
        decision: str,
        edited_text: str | None,
        reason: str | None,
        expected_decision: str,
        acting_principal_id: str | None,
    ) -> ControlResult:
        """Human-only, stale-safe approval/rejection for durable memory proposals."""
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        if decision not in {"approved", "rejected"}:
            return ControlResult(ok=False, reason_code="invalid_memory_proposal_decision")
        candidate = self.store.get_memory_candidate(
            candidate_id, owner_principal_id=acting_principal_id or ""
        )
        if candidate is None:
            return ControlResult(ok=False, reason_code=f"unknown_memory_proposal:{candidate_id}")
        if candidate["decision"] != expected_decision:
            return ControlResult(ok=False, reason_code="stale_memory_proposal")
        text = (edited_text if edited_text is not None else str(candidate["text"])).strip()
        if decision == "approved" and not text:
            return ControlResult(ok=False, reason_code="empty_memory_text")
        from raiker.memory.policy import MemorySensitivity, classify_memory_sensitivity

        sensitivity = classify_memory_sensitivity(text)
        if decision == "approved" and sensitivity in {
            MemorySensitivity.SECRET_LIKE,
            MemorySensitivity.CREDENTIAL_LIKE,
        }:
            return ControlResult(ok=False, reason_code="secret_like_memory_blocked")
        if not self.store.resolve_memory_candidate(
            candidate_id,
            owner_principal_id=acting_principal_id or "",
            expected_decision=expected_decision,
            decision=decision,
            reason=reason,
            resolved_at=utc_now(),
        ):
            return ControlResult(ok=False, reason_code="stale_memory_proposal")
        if decision == "rejected":
            self.store.record_memory_lifecycle_event(
                candidate_id,
                "reject",
                acting_principal_id or "",
                {"reason": reason or "", "source_event_id": candidate["source_event_id"]},
            )
            return ControlResult(ok=True, data={"candidate_id": candidate_id, "decision": decision})

        from raiker.memory.entity_extraction import propose_memory_relationships
        from raiker.memory.store import MemoryGovernance, write_memory

        entry = write_memory(
            text,
            workspace_root=self.workspace_root,
            scope=str(candidate["scope"]),
            memory_type=str(candidate["memory_type"]),
            source="human_approved_proposal",
            store=self.store,
            owner_principal_id=acting_principal_id,
            governance=MemoryGovernance(
                source_event_id=str(candidate["source_event_id"]),
                source_session_id="",
                source_turn_id=None,
                source_type="memory_proposal",
                confidence=float(candidate["confidence"]),
                trust_score=1.0,
                retention="until_forget",
                approval_state="approved",
                created_by=acting_principal_id or "",
            ),
        )
        self.store.record_memory_lifecycle_event(
            entry.memory_id,
            "approve",
            acting_principal_id or "",
            {
                "candidate_id": candidate_id,
                "edited": edited_text is not None and edited_text != candidate["text"],
                "reason": reason or "",
            },
        )
        extraction = propose_memory_relationships(
            self.store, entry.memory_id, acting_principal_id or ""
        )
        return ControlResult(
            ok=True,
            data={
                "candidate_id": candidate_id,
                "decision": decision,
                "memory_id": entry.memory_id,
                "relationship_proposals": extraction.proposed,
            },
        )

    def memory_history(
        self, memory_id: str, acting_principal_id: str | None
    ) -> ControlResult:
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        events = self.store.list_memory_lifecycle_events(
            memory_id, owner_principal_id=acting_principal_id or ""
        )
        if not events:
            memory = get_memory(
                memory_id,
                workspace_root=self.workspace_root,
                include_expired=True,
                include_archived=True,
                owner_principal_id=acting_principal_id,
            )
            if memory is None:
                return ControlResult(ok=False, reason_code=f"unknown_memory:{memory_id}")
        return ControlResult(ok=True, data={"memory_id": memory_id, "events": events})

    def change_memory_scope(
        self,
        memory_id: str,
        scope: str,
        expected_updated_at: str | None,
        reason: str,
        acting_principal_id: str | None,
    ) -> ControlResult:
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        normalized = scope.strip()
        if not normalized or not (
            normalized in {"account", "project", "session"}
            or normalized.startswith(("project:", "session:"))
        ):
            return ControlResult(ok=False, reason_code="invalid_memory_scope")
        current = get_memory(
            memory_id,
            workspace_root=self.workspace_root,
            include_expired=True,
            include_archived=True,
            owner_principal_id=acting_principal_id,
        )
        if current is None:
            return ControlResult(ok=False, reason_code=f"unknown_memory:{memory_id}")
        if current.updated_at != expected_updated_at:
            return ControlResult(ok=False, reason_code="stale_memory_scope_change")
        from raiker.memory.store import update_memory

        updated = update_memory(
            memory_id,
            workspace_root=self.workspace_root,
            scope=normalized,
            store=self.store,
            owner_principal_id=acting_principal_id,
        )
        if updated is None:
            return ControlResult(ok=False, reason_code=f"unknown_memory:{memory_id}")
        self.store.record_memory_lifecycle_event(
            memory_id,
            "scope_change",
            acting_principal_id or "",
            {"from": current.scope, "to": normalized, "reason": reason.strip()},
        )
        return ControlResult(
            ok=True,
            data={"memory_id": memory_id, "scope": normalized, "updated_at": updated.updated_at},
        )

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
        memory_path = internal_io_path(
            self.workspace_root / ".raiker" / "memory" / f"{memory_id}.md"
        )
        return ControlResult(ok=True, data={"memory_id": memory_id, "artifacts": [display_path(memory_path)], "backup_disposition": "retained backups are not immediately erased", "requires_confirmation": memory_id})

    def purge_memory(self, memory_id: str, confirmation: str | None, acting_principal_id: str | None) -> ControlResult:
        preview = self.preview_memory_purge(memory_id, acting_principal_id)
        if not preview.ok:
            return preview
        if confirmation != memory_id:
            return ControlResult(ok=False, reason_code="memory_purge_confirmation_required")
        from raiker.contracts.ids import utc_now
        path = internal_io_path(
            self.workspace_root / ".raiker" / "memory" / f"{memory_id}.md"
        )
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
        from raiker.memory.entity_extraction import propose_memory_relationships
        from raiker.memory.store import MemoryGovernance, update_memory, write_memory
        relationship_proposals = 0
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
            relationship_proposals += propose_memory_relationships(
                self.store, entry.memory_id, acting_principal_id or ""
            ).proposed
        return ControlResult(
            ok=True,
            data={
                "count": len(memories),
                "relationship_proposals": relationship_proposals,
            },
        )

    def reconcile_memory_indexes(self, acting_principal_id: str | None) -> ControlResult:
        """Owner-started repair; never runs as an autonomous background worker."""
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        return ControlResult(ok=True, data=self.store.reconcile_memory_projections(owner_principal_id=acting_principal_id))

    def list_observations(self, acting_principal_id: str | None) -> ControlResult:
        """MEM-04 — what the runtime captured, and what it refused to.

        The counters are part of the answer, not a convenience: an owner looking
        at an empty list needs to know whether nothing was produced or
        everything was refused, and a page that can only count what it received
        cannot tell them.
        """
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        from raiker.memory.eidetic import list_observations

        owner = self.store.account_scope(acting_principal_id) or (acting_principal_id or "")
        observations = list_observations(store=self.store, owner_principal_id=owner)
        with self.store.connect() as connection:
            gists = {
                str(row["observation_id"]): (
                    str(row["gist_id"]), str(row["status"]), str(row["summary"])
                )
                for row in connection.execute(
                    "SELECT gist_id, observation_id, status, summary FROM gist_memories"
                ).fetchall()
            }
        views = []
        for item in observations:
            gist = gists.get(item.observation_id)
            views.append(
                ObservationView(
                    observation_id=item.observation_id,
                    session_id=item.session_id,
                    turn_id=item.turn_id,
                    tool_name=item.tool_name,
                    source_type=item.source_type,
                    summary=item.summary,
                    sensitivity=item.sensitivity,
                    retention=item.retention,
                    capture_status=item.capture_status,
                    skip_reason=item.skip_reason,
                    promotable_to_memory=item.promotable_to_memory,
                    content_sha256=item.content_sha256,
                    content_bytes=item.content_bytes,
                    artifact_ref=item.artifact_ref,
                    source_event_id=item.source_event_id,
                    created_at=item.created_at,
                    expires_at=item.expires_at,
                    gist_id=gist[0] if gist else "",
                    gist_status=gist[1] if gist else "",
                    gist_summary=gist[2] if gist else "",
                )
            )
        return ControlResult(
            ok=True,
            data={
                "observations": [view.to_dict() for view in views],
                "captured": sum(1 for view in views if view.capture_status == "captured"),
                "skipped": sum(1 for view in views if view.capture_status == "skipped"),
                "gists_pending": sum(1 for view in views if view.gist_status == "pending_review"),
            },
        )

    def delete_observations(
        self, observation_ids: set[str], acting_principal_id: str | None
    ) -> ControlResult:
        """The same delete control the rest of memory has, for observations."""
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        from raiker.memory.eidetic import delete_observations

        owner = self.store.account_scope(acting_principal_id) or (acting_principal_id or "")
        try:
            deleted = delete_observations(
                store=self.store, owner_principal_id=owner, observation_ids=observation_ids
            )
        except ValueError as error:
            return ControlResult(ok=False, reason_code=str(error))
        if not deleted:
            return ControlResult(ok=False, reason_code="unknown_observation")
        return ControlResult(ok=True, data={"deleted_observation_ids": deleted})

    def discard_gist(self, gist_id: str, acting_principal_id: str | None) -> ControlResult:
        """Reject a proposed gist without touching the observation it came from.

        A gist is a candidate; discarding one is a review decision, and the
        observation it summarised remains its own record with its own retention.
        """
        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        owner = self.store.account_scope(acting_principal_id) or (acting_principal_id or "")
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT observation_id FROM gist_memories WHERE gist_id = ?", (gist_id,)
            ).fetchone()
            if row is None:
                return ControlResult(ok=False, reason_code="unknown_gist")
            owned = connection.execute(
                "SELECT 1 FROM eidetic_observations"
                " WHERE observation_id = ? AND owner_principal_id = ?",
                (str(row["observation_id"]), owner),
            ).fetchone()
            if owned is None:
                return ControlResult(ok=False, reason_code="unknown_gist")
            connection.execute("DELETE FROM gist_memories WHERE gist_id = ?", (gist_id,))
        return ControlResult(ok=True, data={"gist_id": gist_id, "discarded": True})

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
        if text is not None:
            self.store.record_memory_lifecycle_event(
                memory_id, "edit", acting_principal_id or "", {"text_changed": True}
            )
        if update_expires_at:
            self.store.record_memory_lifecycle_event(
                memory_id,
                "expiry_change",
                acting_principal_id or "",
                {"expires_at": updated.expires_at},
            )
        return ControlResult(
            ok=True,
            data={
                "memory_id": memory_id,
                "search_enabled": updated.search_enabled,
                "expires_at": updated.expires_at,
            },
        )

    def get_memory_settings(self, acting_principal_id: str | None = None) -> MemorySettingsView:
        from raiker.vector.backends import list_embedding_spaces, resolve_embedding_backend

        owner = self.store.account_scope(acting_principal_id) if acting_principal_id else None
        active = resolve_embedding_backend(self.store, owner_principal_id=owner)
        return MemorySettingsView(
            incognito=self.store.is_memory_incognito(acting_principal_id),
            embedding_backend=self.store.get_memory_embedding_backend(owner),
            retrieval=active.describe(),
            # `auto` is always offered and always resolvable; the rest are the
            # spaces that really hold vectors, so a selection can never name a
            # corpus that would answer with nothing.
            spaces=tuple(
                space.describe()
                for space in list_embedding_spaces(self.store, owner_principal_id=owner)
            ),
        )

    def set_memory_embedding_backend(
        self, backend: str, acting_principal_id: str | None
    ) -> ControlResult:
        """Choose the embedding space recall searches (MEM-03, human-only).

        Refused rather than coerced when the named space holds no vectors: a
        selection silently downgraded to the fallback is exactly the kind of
        quiet substitution this change exists to remove.
        """
        from raiker.vector.backends import DEFAULT_SELECTION, list_embedding_spaces

        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        owner = self.store.account_scope(principal.principal_id)
        if backend != DEFAULT_SELECTION:
            known = {
                space.model_label
                for space in list_embedding_spaces(self.store, owner_principal_id=owner)
            }
            if backend not in known:
                return ControlResult(ok=False, reason_code="embedding_backend_unknown")
        self.store.set_memory_embedding_backend(backend, owner)
        return ControlResult(ok=True, data={"embedding_backend": backend})

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
        # BUG-87 — the audit log is account-scoped, not conversation-scoped.
        # Governed steps taken outside any conversation — connecting a
        # credential, pinning a model, resolving a principal — are recorded on
        # runtime channels (`terminal-local`, `authz`) that are not sessions at
        # all. Filtering on the owner's session set alone dropped every one of
        # them, so the page an owner opens to confirm those exact steps showed
        # "No events match" with no filters set.
        #
        # A row is visible when it belongs to one of the owner's own sessions,
        # or to no session record at all. The second clause cannot leak another
        # user's conversation: their sessions are session records, so they fail
        # it and stay filtered.
        conversation_ids = self.store.all_session_ids()
        return [
            self._event_view(row)
            for row in rows
            if str(row.get("session_id")) in visible_session_ids
            or str(row.get("session_id")) not in conversation_ids
        ]

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
        model_profile: str | None = None,
        model: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
        start_immediately: bool = True,
    ) -> TaskView:
        """Create a local planning task in the caller's server-owned Inbox session.

        Project-scoped schedules: the task is stamped with ``project_id`` when
        given, else with the active project, so a schedule created inside a
        project stays scoped to it. The stamp is an organizing label — it
        grants nothing.
        """
        if recurrence is not None and recurrence not in TASK_RECURRENCES:
            raise ValueError(f"invalid_recurrence:{recurrence}")
        if bool(model_profile) != bool(model):
            raise ValueError("task_model_pair_required")
        if model_profile and model:
            try:
                profile = ModelProfileRegistry.load().resolve_profile_id(model_profile)
            except Exception as exc:  # noqa: BLE001 - unknown choices fail closed
                raise ValueError(f"unknown_profile:{model_profile}") from exc
            if bool(profile.raw.get("test_only", False)):
                raise ValueError(f"test_profile_not_allowed:{model_profile}")
            if not self.store.is_configured_model(principal_id, model_profile, model):
                raise ValueError("model_not_configured_for_task")
        clean_attachments: list[dict[str, Any]] = []
        if len(attachments or []) > 8:
            raise ValueError("too_many_attachments")
        for entry in attachments or []:
            if not isinstance(entry, dict):
                raise ValueError("invalid_attachment")
            kind = entry.get("type")
            if kind == "path" and isinstance(entry.get("path"), str) and entry["path"].strip():
                clean_attachments.append({"type": "path", "path": entry["path"].strip()})
                continue
            attachment_id = entry.get("attachment_id")
            if kind in {"image", "document"} and isinstance(attachment_id, str) and attachment_id.strip():
                if self.store.load_attachment_metadata(
                    attachment_id.strip(), owner_principal_id=principal_id
                ) is None:
                    raise ValueError("attachment_not_found")
                clean_attachments.append({"type": kind, "attachment_id": attachment_id.strip()})
                continue
            raise ValueError("invalid_attachment")
        # BUG-64 — creation and execution are separate decisions for a model-
        # proposed task. Human use of Tasks keeps the established start-now
        # default; approval execution passes false and parks the new row until
        # the owner explicitly runs it. A model-supplied date does not smuggle
        # scheduling authority through a creation approval.
        if not start_immediately:
            scheduled_at = None
        elif scheduled_at is None:
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
        # Task origin (BUG-10): the Inbox is a server-owned session that task
        # runs execute in, not a conversation the owner had. Tagging it keeps it
        # out of RECENT CHATS while leaving it fully readable in Sessions.
        self.store.create_session(
            inbox_session_id,
            str(self.store.paths.workspace_root),
            title="Inbox",
            user_id=user_id,
            origin="task",
        )
        self.store.set_session_origin(inbox_session_id, "task")
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
            model_profile=model_profile,
            model=model,
            attachments=clean_attachments,
        )
        return self._task_view(task)

    def run_task_now(self, task_id: str, *, user_id: str | None) -> TaskView:
        """Schedule one visible, queued, unscheduled task for immediate claim."""
        from raiker.events.types import make_event

        task, reason = self.store.schedule_task_now(task_id, user_id=user_id)
        if task is None:
            raise ValueError(reason or "task_not_runnable")
        EventLogWriter(self.store).append(
            make_event(
                session_id=task.session_id,
                turn_id=task.parent_turn_id,
                event_type="task_run_requested",
                actor="dashboard",
                payload={"task_id": task.task_id, "scheduled_at": task.scheduled_at},
            )
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
        rows = self.store.list_approvals(
            status=status, user_id=user_id, principal_id=principal_id
        )
        # ADD-02 — one join for the whole page rather than a query per row, so a
        # batched turn's approvals can each say which decision they are.
        positions = self.store.suspended_turn_queue_positions(
            [str(row.get("approval_id", "")) for row in rows]
        )
        return [self._approval_view(row, queue=positions) for row in rows]

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
        return self._approval_detail(row, principal_id=principal_id)

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
        native_default = next(
            (profile for profile in registry.list_profiles() if profile.raw.get("is_native_default")),
            None,
        )
        current = state.profile_id if state is not None else (
            native_default.profile_id if native_default is not None else None
        )
        # The persisted per-profile model override (e.g. an Ollama/OpenAI model
        # picked at selection time) is what the runtime actually binds, so the
        # selected profile card shows it instead of the profile's placeholder.
        override = state.model if state is not None and state.model else None
        hosted_gate = self.control.get_capability_gate(HOSTED_MODEL_GATE, acting_principal_id)
        private_gate = self.control.get_capability_gate(PRIVATE_NETWORK_MODEL_GATE, acting_principal_id)
        advisor_gate = self.control.get_capability_gate("advisor_model_runtime", acting_principal_id)
        from raiker.models.connections import get_model_connection
        from raiker.models.readiness import ModelReadinessService, ProviderCatalogueProbe
        from raiker.runtime.model_usage import ModelUsageLedger, sum_totals

        # One ledger read for the whole page, grouped by provider, so each card
        # can show its own spend without a query per card.
        usage_by_provider: dict[str, list[Any]] = {}
        if acting_principal_id:
            for row in ModelUsageLedger(self.store).provider_usage(acting_principal_id):
                usage_by_provider.setdefault(row.provider, []).append(row)
        readiness_service = ModelReadinessService(
            self.store,
            probe=ProviderCatalogueProbe(self.store),
        )

        def _usage_fields(profile: Any) -> dict[str, Any]:
            rows = usage_by_provider.get(profile.provider, [])
            totals = sum_totals(rows)
            billable = self._profile_is_billable(profile)
            cost = None
            currency = None
            price_source = None
            price_as_of = None
            if billable and rows:
                # Price each model at its own rate and add them up: a provider's
                # cheap and expensive models differ by an order of magnitude, so
                # one blended rate across the provider would be meaningless.
                total = Decimal(0)
                priced_any = False
                for row in rows:
                    facts = self._resolve_facts(profile, row.model, acting_principal_id)
                    row_cost = row.totals.cost(facts)
                    if row_cost is None:
                        continue
                    priced_any = True
                    total += row_cost
                    if facts.price is not None and price_source is None:
                        currency = facts.price.currency
                        price_source = facts.price.source
                        price_as_of = facts.price.as_of
                if priced_any:
                    cost = str(total)
            return {
                "billable": billable,
                "models_used": len({row.model for row in rows}),
                "turns_used": totals.turns,
                "total_tokens": totals.total_tokens,
                "total_cost": cost,
                "cost_currency": currency,
                "price_source": price_source,
                "price_as_of": price_as_of,
            }

        registry_profiles = tuple(
            p
            for p in registry.list_profiles()
            if not bool(p.raw.get("test_only", False))
            and not bool(p.raw.get("setup_hidden", False))
        )

        def _profile_view(
            profile: Any, effective_model: str, *, selected: bool
        ) -> ModelProfileView:
            facts = self._resolve_facts(profile, effective_model, acting_principal_id)
            saved_connection = (
                get_model_connection(self.store, acting_principal_id, profile.profile_id)
                if acting_principal_id
                else None
            )
            readiness = (
                readiness_service.current_selected(
                    acting_principal_id,
                    profile.profile_id,
                    effective_model,
                )
                if acting_principal_id and effective_model and "<" not in effective_model
                else None
            )
            return ModelProfileView(
                profile_id=profile.profile_id,
                provider=profile.provider,
                model=effective_model,
                default_state=profile.default_state,
                local_only=profile.local_only,
                requires_network=profile.requires_network,
                endpoint_kind=str(profile.raw.get("endpoint_kind", "unknown")),
                requires_egress_policy=bool(profile.raw.get("requires_egress_policy", False)),
                requires_budget_policy=bool(profile.raw.get("requires_budget_policy", False)),
                runtime_gate=self._runtime_gate_for_profile(
                    str(profile.raw.get("endpoint_kind", "unknown"))
                ),
                off_machine=str(profile.raw.get("endpoint_kind", "unknown"))
                in {"remote_hosted", "private_network"},
                selected=selected,
                connection_configured=bool(saved_connection),
                usage_admin_configured=bool(
                    saved_connection and saved_connection.get("admin_api_key")
                ),
                prompt_cache_ttl=(
                    str(profile.raw.get("prompt_cache_ttl"))
                    if profile.raw.get("prompt_cache_ttl")
                    else None
                ),
                context_window_tokens=facts.context_window_tokens,
                context_window_source=facts.context_window_source,
                configured=effective_model != "<model>",
                readiness_state=(readiness.state.value if readiness else "not_configured"),
                readiness_summary=(
                    readiness.summary
                    if readiness
                    else "Choose a concrete model before checking readiness."
                ),
                readiness_reason_code=(
                    readiness.reason_code if readiness else "model_not_configured"
                ),
                readiness_checked_at=(readiness.checked_at if readiness else None),
                readiness_expires_at=(readiness.expires_at if readiness else None),
                readiness_remediation=(
                    readiness.remediation
                    if readiness
                    else "Choose a model, then check the connection."
                ),
                ready=bool(readiness and readiness.ready),
                supports_reasoning=bool(profile.raw.get("supports_reasoning", False)),
                supports_reasoning_effort=bool(
                    profile.raw.get("supports_reasoning_effort", False)
                ),
                reasoning_effort_values=tuple(
                    str(value)
                    for value in profile.raw.get("reasoning_effort_values", [])
                ),
                reasoning_modes=tuple(
                    str(value) for value in profile.raw.get("reasoning_modes", [])
                ),
                supports_reasoning_summary=bool(
                    profile.raw.get("supports_reasoning_summary", False)
                ),
                **_usage_fields(profile),
            )

        configured_pairs = (
            self.store.list_configured_models(acting_principal_id)
            if acting_principal_id
            else []
        )
        configured_by_profile: dict[str, list[str]] = {}
        for profile_id, configured_model in configured_pairs:
            configured_by_profile.setdefault(profile_id, []).append(configured_model)

        def _card_model(profile: Any) -> str:
            if override and profile.profile_id == current:
                return override
            choices = configured_by_profile.get(profile.profile_id, [])
            if profile.model == "<model>" and choices:
                return choices[-1]
            return profile.model

        profiles = tuple(
            _profile_view(
                profile,
                _card_model(profile),
                selected=profile.profile_id == current,
            )
            for profile in registry_profiles
        )

        chat_profiles: list[ModelProfileView] = []
        seen_choices: set[tuple[str, str]] = set()
        for profile in registry_profiles:
            choices = ([] if profile.model == "<model>" else [profile.model]) + configured_by_profile.get(
                profile.profile_id, []
            )
            for configured_model in choices:
                key = (profile.profile_id, configured_model)
                if key in seen_choices:
                    continue
                seen_choices.add(key)
                chat_profiles.append(
                    _profile_view(
                        profile,
                        configured_model,
                        selected=(
                            profile.profile_id == current
                            and configured_model
                            == (override or profile.model)
                        ),
                    )
                )
        return ModelsView(
            profiles=profiles,
            chat_profiles=tuple(chat_profiles),
            current_profile_id=current,
            hosted_model_gate_state=hosted_gate.state if hosted_gate is not None else "unknown",
            private_network_model_gate_state=private_gate.state if private_gate is not None else "unknown",
            model_egress_allowlist_configured=bool(
                os.environ.get(MODEL_EGRESS_ALLOWLIST_ENV, "").strip()
            ),
            remote_profile_count=sum(1 for p in profiles if p.off_machine),
            ready_provider_count=sum(1 for p in profiles if p.ready),
            fallback_sequence=tuple(
                self.store.load_principal_model_fallback_sequence(scoped_principal)
                if scoped_principal else self.store.load_model_fallback_sequence(TERMINAL_MODEL_SESSION_ID)
            ),
            current_model=(
                self._current_model(registry, state)
                if state is not None
                else (native_default.model if native_default is not None else None)
            ),
            advisor_profile_id=(
                self.store.load_principal_model_advisor(scoped_principal)
                if scoped_principal else self.store.load_model_advisor(TERMINAL_MODEL_SESSION_ID)
            ),
            advisor_model_gate_state=advisor_gate.state if advisor_gate is not None else "unknown",
            **self._advisor_readiness_fields(readiness_service, acting_principal_id),
        )

    def _advisor_readiness_fields(
        self, readiness_service: Any, acting_principal_id: str | None
    ) -> dict[str, Any]:
        """Readiness for the exact model a consult would call (BUG-82).

        Resolved through the same per-profile pin the chat chain uses, so a
        hosted advisor chosen in Models → Routing is the model reported on —
        rather than the profile's `<model>` placeholder, which is what made the
        consult refuse `advisor_model_unresolved` for owners who had pinned one.
        """
        from raiker.runtime.advisor import AdvisorService

        blank = {
            "advisor_model": None,
            "advisor_readiness_state": "not_configured",
            "advisor_readiness_summary": None,
            "advisor_readiness_remediation": None,
            "advisor_readiness_checked_at": None,
        }
        if not acting_principal_id:
            return blank
        try:
            resolved = AdvisorService(
                self.workspace_root, self.store, principal_id=acting_principal_id
            ).resolved_advisor()
        except Exception:  # noqa: BLE001 — an unreadable advisor reports "none chosen"
            return blank
        if resolved is None:
            return blank
        profile_id, model = resolved
        try:
            readiness = readiness_service.current_selected(
                acting_principal_id, profile_id, model
            )
        except Exception:  # noqa: BLE001 — an unresolvable endpoint is "not checked"
            return {**blank, "advisor_model": model}
        return {
            "advisor_model": model,
            "advisor_readiness_state": readiness.state.value,
            "advisor_readiness_summary": readiness.summary,
            "advisor_readiness_remediation": readiness.remediation,
            "advisor_readiness_checked_at": readiness.checked_at,
        }

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

    # ── Model cost and usage accounting ─────────────────────────────────

    @staticmethod
    def _profile_is_billable(profile: Any) -> bool:
        """True only for off-machine providers Raiker authenticates with a key.

        A local runtime costs nothing per token however many tokens it burns, so
        attaching money to it would be a lie. An API key alone is not enough to
        decide: LM Studio reads `LM_API_TOKEN` yet runs on `127.0.0.1` and bills
        nothing. Both conditions must hold — the endpoint leaves this machine
        **and** a credential authenticates it.
        """
        raw = getattr(profile, "raw", {}) or {}
        endpoint_kind = str(raw.get("endpoint_kind", ""))
        off_machine = endpoint_kind in {"remote_hosted", "private_network"}
        # The shipped profiles do not persist this runtime classification. Their
        # policy metadata is still authoritative: a non-local provider that
        # requires network access is off-machine even before its first request.
        if not off_machine:
            off_machine = bool(getattr(profile, "requires_network", raw.get("requires_network", False))) and not bool(
                getattr(profile, "local_only", raw.get("local_only", False))
            )
        if not off_machine:
            return False
        keyed = bool(raw.get("requires_api_key")) or bool(raw.get("api_key_env"))
        return keyed

    def _resolve_facts(self, profile: Any, model: str, principal_id: str | None) -> Any:
        """Merge owner override, cached provider report, and shipped config.

        BUG-21 — the normalised price registry is consulted first, because it is
        the only source that carries effective dating and the cache-write and
        cache-read components. Its answer is exact-model-id only, so a model the
        registry has never seen falls through to the pre-registry resolution
        below rather than borrowing a sibling's rate.
        """
        from raiker.models.price_registry import PriceRegistry
        from raiker.models.pricing import resolve_model_facts
        facts_store = ModelFactsStore(self.store)
        registered = (
            PriceRegistry(self.store).resolve(principal_id, profile.provider, model)
            if principal_id and model
            else None
        )
        owner_price = (
            facts_store.owner_price(principal_id, profile.provider, model)
            if principal_id and model else None
        )
        provider_facts = (
            facts_store.provider_facts(principal_id, profile.provider, model)
            if principal_id and model else None
        )
        raw = getattr(profile, "raw", {}) or {}
        configured_window = raw.get("context_window_tokens")
        if registered is not None:
            # A registered rate outranks all three legacy sources: it *is* one
            # of them, resolved by the same precedence, but dated and complete.
            owner_price = registered.rates.to_price(registered.source, registered.as_of)
        resolved = resolve_model_facts(
            provider=profile.provider,
            model=model,
            owner_price=owner_price,
            provider_facts=provider_facts,
            config_pricing=raw.get("pricing"),
            config_context_window=(
                configured_window
                if isinstance(configured_window, int) and not isinstance(configured_window, bool)
                else None
            ),
        )
        owner_capacity = (
            facts_store.owner_context_capacity(principal_id, profile.provider, model)
            if principal_id and model else None
        )
        if owner_capacity is not None:
            resolved = replace(
                resolved,
                context_window_tokens=owner_capacity[0],
                context_window_source="owner",
            )
        return resolved

    def get_context_usage(
        self, session_id: str, acting_principal_id: str | None = None
    ) -> ContextUsageView:
        """Usage and cost for one conversation, plus the provider's all-time total.

        Reads only what the ledger recorded. A session with no completed turn
        reports `usage_source="unavailable"`, which is the browser's signal to
        show its own clearly-labelled transcript estimate instead of pretending
        this is provider-reported.
        """
        from raiker.runtime.model_usage import ModelUsageLedger, sum_totals

        registry = ModelProfileRegistry.load()
        state = (
            self.store.load_principal_model_state(acting_principal_id)
            if acting_principal_id and self.store.get_account(acting_principal_id) is not None
            else self.store.load_model_session_state(TERMINAL_MODEL_SESSION_ID)
        )
        profile_id = state.profile_id if state is not None else None
        profile = None
        if profile_id:
            try:
                profile = registry.resolve_profile_id(profile_id)
            except Exception:  # noqa: BLE001 — an unknown selection is simply unpriced
                profile = None

        ledger = ModelUsageLedger(self.store)
        principal = acting_principal_id or ""
        session_rows = ledger.session_usage(principal, session_id) if principal else []
        session_totals = sum_totals(session_rows)

        # The model that actually served this conversation beats the currently
        # selected one: re-pricing history at a newly picked model's rate would
        # misreport what the user already spent.
        model = session_rows[-1].model if session_rows else (
            (state.model if state is not None and state.model else None)
            or (profile.model if profile is not None else None)
        )
        if model in (None, "", "<model>"):
            model = None

        billable = bool(profile is not None and self._profile_is_billable(profile))
        facts = (
            self._resolve_facts(profile, model, acting_principal_id)
            if profile is not None and model else None
        )

        def _priced_total(rows: list[Any]) -> Decimal | None:
            """Sum cost by pricing each model at its own rate.

            Summing tokens first and applying one model's rate would charge a
            cheap model's tokens at an expensive model's price — Claude models
            differ by roughly 15x, so a mixed history would be badly wrong.
            Returns None when no row could be priced at all.
            """
            total = Decimal(0)
            priced_any = False
            for row in rows:
                row_facts = self._resolve_facts(profile, row.model, acting_principal_id)
                row_cost = row.totals.cost(row_facts)
                if row_cost is None:
                    continue
                priced_any = True
                total += row_cost
            return total if priced_any else None

        session_cost = _priced_total(session_rows) if billable and profile is not None else None
        provider_total: Decimal | None = None
        if billable and profile is not None and principal:
            matching = [
                row for row in ledger.provider_usage(principal)
                if row.provider == profile.provider
            ]
            provider_total = _priced_total(matching) if matching else None

        price = facts.price if facts is not None else None
        # BUG-21 — a billable conversation with no exact rate says so. Silence
        # here reads as "free", which is the one thing it certainly is not.
        price_unknown = bool(billable and price is None)
        registered = None
        if profile is not None and model and acting_principal_id:
            from raiker.models.price_registry import PriceRegistry

            registered = PriceRegistry(self.store).resolve(
                acting_principal_id, profile.provider, model
            )
        latest_compaction = None
        if acting_principal_id:
            from raiker.runtime.conversation_compaction import ContextCompactionStore

            compacted = ContextCompactionStore(self.store).latest(
                acting_principal_id, session_id
            )
            if compacted is not None:
                latest_compaction = {
                    "status": compacted.status,
                    "created_at": compacted.created_at,
                    "source_turn_count": compacted.source_turn_count,
                    "estimated_input_tokens_before": (
                        compacted.estimated_input_tokens_before
                    ),
                    "estimated_summary_tokens": compacted.estimated_summary_tokens,
                    "reason_code": compacted.reason_code,
                }
        return ContextUsageView(
            session_id=session_id,
            profile_id=profile.profile_id if profile is not None else None,
            provider=profile.provider if profile is not None else None,
            model=model,
            used_tokens=session_rows[-1].totals.input_tokens if session_rows else None,
            context_window_tokens=facts.context_window_tokens if facts is not None else None,
            context_window_source=facts.context_window_source if facts is not None else None,
            usage_source="provider" if session_rows else "unavailable",
            billable=billable,
            session_cost=str(session_cost) if session_cost is not None else None,
            provider_total_cost=str(provider_total) if provider_total is not None else None,
            currency=price.currency if price is not None else None,
            price_source=price.source if price is not None else None,
            price_as_of=price.as_of if price is not None else None,
            session_turns=session_totals.turns,
            session_input_tokens=session_totals.input_tokens,
            session_output_tokens=session_totals.output_tokens,
            price_input_per_mtok=str(price.input_per_mtok) if price is not None else None,
            price_output_per_mtok=str(price.output_per_mtok) if price is not None else None,
            price_cache_write_per_mtok=(
                str(price.cache_write_per_mtok)
                if price is not None and price.cache_write_per_mtok is not None
                else None
            ),
            price_cache_read_per_mtok=(
                str(price.cache_read_per_mtok)
                if price is not None and price.cache_read_per_mtok is not None
                else None
            ),
            price_effective_from=registered.effective_from if registered is not None else None,
            price_unknown=price_unknown,
            latest_compaction=latest_compaction,
        )

    # ── BUG-21: the pricing registry surface ─────────────────────────────

    def list_model_pricing(
        self, acting_principal_id: str | None, *, history_limit: int = 10
    ) -> ModelPricingView:
        """Every priced model this owner has, with source, dates, and history.

        The list is the union of what the registry holds and what the shipped
        profiles document, so a model whose price has never been synchronised
        still appears — with its documented rate and its ``as_of`` date — rather
        than being invisible until a network call succeeds.
        """
        from raiker.models.price_registry import PriceRegistry
        from raiker.models.price_sync import PriceSynchroniser

        owner = acting_principal_id or ""
        registry = PriceRegistry(self.store)
        synchroniser = PriceSynchroniser(self.store, registry)
        if not owner:
            return ModelPricingView(entries=(), sync=(), can_override=False)

        # Seed the reviewed-documentation adapter for anything not yet recorded,
        # so first open is populated without pretending a provider was called.
        self._sync_documented_prices(owner, force=False)

        profile_registry = ModelProfileRegistry.load()
        profile_by_model: dict[tuple[str, str], str] = {}
        review_by_model: dict[tuple[str, str], tuple[str, str, str]] = {}
        for profile in profile_registry.list_profiles():
            if bool(profile.raw.get("test_only", False)):
                continue
            pricing_block = profile.raw.get("pricing")
            models = (
                pricing_block.get("models") if isinstance(pricing_block, dict) else None
            )
            if isinstance(models, dict) and isinstance(pricing_block, dict):
                for model_id in models:
                    if isinstance(model_id, str):
                        profile_by_model.setdefault(
                            (profile.provider, model_id), profile.profile_id
                        )
                        reviewed_at = pricing_block.get("reviewed_at")
                        interval = pricing_block.get("review_interval_days", 92)
                        if isinstance(reviewed_at, str) and reviewed_at:
                            try:
                                reviewed = datetime.fromisoformat(reviewed_at).replace(tzinfo=UTC)
                                due = reviewed + timedelta(days=max(int(interval), 1))
                                review_by_model[(profile.provider, model_id)] = (
                                    reviewed_at,
                                    due.date().isoformat(),
                                    "overdue" if datetime.now(UTC) > due else "current",
                                )
                            except (TypeError, ValueError):
                                review_by_model[(profile.provider, model_id)] = (
                                    reviewed_at, "", "invalid",
                                )
            if isinstance(profile.model, str) and profile.model not in ("", "<model>"):
                profile_by_model.setdefault(
                    (profile.provider, profile.model), profile.profile_id
                )

        entries: list[ModelPricingEntryView] = []
        for provider, model in registry.models(owner):
            current = registry.resolve(owner, provider, model)
            if current is None:
                continue
            history = registry.history(owner, provider, model, limit=history_limit)
            entries.append(
                # A documented rate's human review is a different clock from
                # provider synchronisation. Overrides and provider catalogue
                # rows have no shipped-document review to claim.
                ModelPricingEntryView(
                    provider=provider,
                    model=model,
                    profile_id=profile_by_model.get((provider, model)),
                    source=current.source,
                    currency=current.rates.currency,
                    input_per_mtok=str(current.rates.input_per_mtok),
                    output_per_mtok=str(current.rates.output_per_mtok),
                    cache_write_per_mtok=(
                        None
                        if current.rates.cache_write_per_mtok is None
                        else str(current.rates.cache_write_per_mtok)
                    ),
                    cache_read_per_mtok=(
                        None
                        if current.rates.cache_read_per_mtok is None
                        else str(current.rates.cache_read_per_mtok)
                    ),
                    effective_from=current.effective_from,
                    as_of=current.as_of,
                    reviewed_at=(review_by_model.get((provider, model)) or (None, None, None))[0]
                    if current.source == "config" else None,
                    review_due_at=(review_by_model.get((provider, model)) or (None, None, None))[1]
                    if current.source == "config" else None,
                    review_status=(review_by_model.get((provider, model)) or (None, None, None))[2]
                    if current.source == "config" else None,
                    recorded_at=current.recorded_at,
                    recorded_by=current.recorded_by,
                    reason=current.reason,
                    has_owner_override=any(row.source == "owner" for row in history),
                    history=tuple(row.to_dict() for row in history),
                )
            )

        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        can_override = principal is not None and self.control._is_gate_manager(principal)  # noqa: SLF001
        return ModelPricingView(
            entries=tuple(entries),
            sync=tuple(state.to_dict() for state in synchroniser.states(owner)),
            can_override=bool(can_override),
        )

    def _sync_documented_prices(self, owner_principal_id: str, *, force: bool) -> list[Any]:
        """Run the reviewed-documentation adapter for every shipped profile.

        ``force`` bypasses the 6–24 hour cadence for an explicit refresh. Without
        it a provider that is not yet due is skipped, which is what keeps opening
        the Models page from re-recording prices on every visit.
        """
        from raiker.models.price_sync import PriceSynchroniser

        synchroniser = PriceSynchroniser(self.store)
        blocks: dict[str, dict[str, Any]] = {}
        for profile in ModelProfileRegistry.load().list_profiles():
            if bool(profile.raw.get("test_only", False)):
                continue
            pricing_block = profile.raw.get("pricing")
            if not isinstance(pricing_block, dict):
                continue
            merged = blocks.setdefault(
                profile.provider,
                {
                    "currency": pricing_block.get("currency", "USD"),
                    "as_of": pricing_block.get("as_of"),
                    "models": {},
                },
            )
            models = pricing_block.get("models")
            if isinstance(models, dict):
                merged["models"].update(models)

        results = []
        for provider, block in sorted(blocks.items()):
            if not force and not synchroniser.due(owner_principal_id, provider):
                continue
            results.append(
                synchroniser.sync_from_documentation(owner_principal_id, provider, block)
            )
        return results

    def refresh_model_pricing(self, acting_principal_id: str | None) -> ControlResult:
        """Run the synchronisation now, on explicit demand.

        Only the reviewed adapters run here. A provider catalogue is contacted
        exclusively by the user-initiated model listing, which feeds the registry
        on its way past — this route never opens a connection of its own.
        """
        if not acting_principal_id:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        results = self._sync_documented_prices(acting_principal_id, force=True)
        return ControlResult(
            ok=True,
            data={
                "providers": [result.to_dict() for result in results],
                "changes_written": sum(result.changes_written for result in results),
            },
        )

    def model_capacity_status(self, acting_principal_id: str | None) -> ControlResult:
        if not acting_principal_id:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        models = self.get_models(acting_principal_id)
        facts_store = ModelFactsStore(self.store)
        entries: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for profile in (*models.profiles, *models.chat_profiles):
            key = (profile.profile_id, profile.provider, profile.model)
            if profile.model == "<model>" or key in seen:
                continue
            seen.add(key)
            entries.append(
                {
                    "profile_id": profile.profile_id,
                    "provider": profile.provider,
                    "model": profile.model,
                    "endpoint_identity": f"{profile.profile_id}:{profile.endpoint_kind}",
                    "context_window_tokens": profile.context_window_tokens,
                    "source": profile.context_window_source,
                    "history": facts_store.capacity_history(
                        acting_principal_id, profile.provider, profile.model
                    ),
                }
            )
        sync = facts_store.capacity_refresh_state(acting_principal_id)
        registry = ModelProfileRegistry.load()
        local_ids = [
            profile.profile_id
            for profile in registry.list_profiles()
            if profile.local_only and not bool(profile.raw.get("test_only", False))
        ]
        due = any(facts_store.capacity_refresh_due(acting_principal_id, profile_id) for profile_id in local_ids)
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        return ControlResult(
            ok=True,
            data={
                "entries": entries,
                "sync": sync,
                "refresh_due": due,
                "cadence_hours": 24,
                "can_override": bool(principal and self.control._is_gate_manager(principal)),  # noqa: SLF001
            },
        )

    async def refresh_local_model_capacities(
        self, acting_principal_id: str | None, *, force: bool = False
    ) -> ControlResult:
        if not acting_principal_id:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        registry = ModelProfileRegistry.load()
        facts_store = ModelFactsStore(self.store)
        refreshed: list[dict[str, Any]] = []
        for profile in registry.list_profiles():
            if not profile.local_only or bool(profile.raw.get("test_only", False)):
                continue
            if not force and not facts_store.capacity_refresh_due(acting_principal_id, profile.profile_id):
                continue
            view = await self.list_provider_models(profile.profile_id, acting_principal_id)
            status_value = view.status if view is not None else "unavailable"
            reason_code = view.reason_code if view is not None else "unknown_model_profile"
            facts_store.record_capacity_refresh(
                acting_principal_id, profile.profile_id, status_value, reason_code
            )
            refreshed.append(
                {"profile_id": profile.profile_id, "status": status_value, "reason_code": reason_code}
            )
        return ControlResult(ok=True, data={"profiles": refreshed})

    def set_model_context_capacity(
        self,
        profile_id: str,
        model: str,
        tokens: int | None,
        reason: str,
        acting_principal_id: str | None,
    ) -> ControlResult:
        if not acting_principal_id:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None or not self.control._is_gate_manager(principal):  # noqa: SLF001
            return ControlResult(ok=False, reason_code="not_authorized_gate_manager")
        if not model or model == "<model>":
            return ControlResult(ok=False, reason_code="model_not_specified")
        try:
            profile = ModelProfileRegistry.load().resolve_profile_id(profile_id)
        except Exception:
            return ControlResult(ok=False, reason_code="unknown_model_profile")
        try:
            ModelFactsStore(self.store).set_owner_context_capacity(
                acting_principal_id,
                profile.provider,
                model,
                tokens=tokens,
                endpoint_identity=f"{profile.profile_id}:{profile.raw.get('endpoint_kind', 'unknown')}",
                reason=redact_secret_like_text(reason.strip()),
                recorded_by=acting_principal_id,
            )
        except ValueError as exc:
            return ControlResult(ok=False, reason_code=str(exc))
        return ControlResult(ok=True, data={"profile_id": profile_id, "model": model, "tokens": tokens})

    def set_model_price(
        self,
        profile_id: str,
        model: str,
        *,
        input_per_mtok: str | None,
        output_per_mtok: str | None,
        currency: str = "USD",
        acting_principal_id: str | None,
        cache_write_per_mtok: str | None = None,
        cache_read_per_mtok: str | None = None,
        effective_from: str | None = None,
        reason: str | None = None,
    ) -> ControlResult:
        """Set or clear one model's administrator price override (BUG-21).

        Both input and output absent clears the override, returning the model to
        its provider-published or documented rate. An override is administrator
        work rather than a personal preference — it changes what every figure in
        the product claims a turn cost — so it requires the gate-manager role and
        is recorded in the registry with who set it and why. It is still scoped
        to the acting principal, so it can never change another account's costs.
        """
        if not acting_principal_id:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if not self.control._is_gate_manager(principal):  # noqa: SLF001
            return ControlResult(ok=False, reason_code="not_authorized_gate_manager")
        if not model or model == "<model>":
            return ControlResult(ok=False, reason_code="model_not_specified")
        registry = ModelProfileRegistry.load()
        try:
            profile = registry.resolve_profile_id(profile_id)
        except Exception:  # noqa: BLE001 — unknown profile fails closed
            return ControlResult(ok=False, reason_code="unknown_model_profile")

        from raiker.models.price_registry import PriceRates, PriceRegistry, PriceRegistryError

        price_registry = PriceRegistry(self.store)
        facts_store = ModelFactsStore(self.store)
        if input_per_mtok is None and output_per_mtok is None:
            facts_store.clear_owner_price(acting_principal_id, profile.provider, model)
            price_registry.clear_source(
                acting_principal_id, profile.provider, model, "owner"
            )
            self._record_price_audit(
                acting_principal_id, profile.provider, model, "cleared", reason
            )
            return ControlResult(ok=True, data={"model": model, "cleared": True})

        def _rate(value: str | None) -> Decimal | None:
            if value is None or str(value).strip() == "":
                return None
            parsed = Decimal(str(value))
            if not parsed.is_finite() or parsed < 0:
                raise ValueError("model_price_invalid")
            return parsed

        try:
            price_in = _rate(input_per_mtok)
            price_out = _rate(output_per_mtok)
            cache_write = _rate(cache_write_per_mtok)
            cache_read = _rate(cache_read_per_mtok)
        except Exception:  # noqa: BLE001 — a malformed price is rejected, not guessed
            return ControlResult(ok=False, reason_code="model_price_invalid")
        if price_in is None or price_out is None:
            return ControlResult(ok=False, reason_code="model_price_invalid")

        facts_store.set_owner_price(
            acting_principal_id,
            profile.provider,
            model,
            input_per_mtok=price_in,
            output_per_mtok=price_out,
            currency=currency or "USD",
        )
        try:
            price_registry.record(
                acting_principal_id,
                profile.provider,
                model,
                PriceRates(
                    input_per_mtok=price_in,
                    output_per_mtok=price_out,
                    cache_write_per_mtok=cache_write,
                    cache_read_per_mtok=cache_read,
                    currency=currency or "USD",
                ),
                source="owner",
                effective_from=effective_from,
                as_of=effective_from,
                recorded_by=acting_principal_id,
                reason=reason or "Administrator price override",
            )
        except PriceRegistryError as exc:
            return ControlResult(ok=False, reason_code=str(exc))
        self._record_price_audit(
            acting_principal_id, profile.provider, model, "set", reason
        )
        return ControlResult(
            ok=True,
            data={
                "model": model,
                "input_per_mtok": str(price_in),
                "output_per_mtok": str(price_out),
                "cache_write_per_mtok": None if cache_write is None else str(cache_write),
                "cache_read_per_mtok": None if cache_read is None else str(cache_read),
                "currency": currency or "USD",
            },
        )

    def _record_price_audit(
        self,
        acting_principal_id: str,
        provider: str,
        model: str,
        action: str,
        reason: str | None,
    ) -> None:
        """Write the override to the governed event log. Never fails the write."""
        from raiker.contracts.models import AgentEvent

        with contextlib.suppress(Exception):
            EventLogWriter(self.store).append(
                AgentEvent(
                    event_id=new_id("evt_"),
                    timestamp=utc_now(),
                    session_id=TERMINAL_MODEL_SESSION_ID,
                    turn_id=None,
                    event_type=(
                        "model_price_override_cleared"
                        if action == "cleared"
                        else "model_price_override_recorded"
                    ),
                    actor=acting_principal_id,
                    payload={
                        "provider": provider,
                        "model": model,
                        "reason": redact_secret_like_text(reason or ""),
                    },
                )
            )

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
        # A successful listing is the one moment Raiker legitimately hears from
        # the provider, so whatever it published about its models (Anthropic's
        # context window, OpenRouter's prices) is cached here for the meter and
        # the cost rows to read without a second round trip.
        if acting_principal_id:
            with contextlib.suppress(Exception):  # caching never fails a listing
                ModelFactsStore(self.store).save_provider_facts(
                    acting_principal_id, profile.provider, list(models)
                )
            # BUG-21 — the same listing is the provider's own price feed, so it
            # also lands in the effective-dated registry. Recording is idempotent:
            # a catalogue whose rates have not moved writes no history row.
            with contextlib.suppress(Exception):
                from raiker.models.price_sync import PriceSynchroniser

                PriceSynchroniser(self.store).sync_from_catalogue(
                    acting_principal_id, profile.provider, list(models)
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
        self.store.save_configured_model(
            principal.principal_id, profile.profile_id, resolved_model
        )
        if self.store.get_account(principal.principal_id) is not None:
            self.store.save_principal_model_state(principal.principal_id, state)
        else:
            self.store.save_model_session_state(state)
        self.store.invalidate_model_readiness(
            principal.principal_id,
            profile.profile_id,
            reason_code="model_selection_changed",
        )
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
        readiness_summary = dict(readiness.summary)
        checkpoint_health = self.store.get_checkpoint_capture_health()
        if checkpoint_health is not None:
            checkpoint_health["ok"] = bool(checkpoint_health["ok"])
            readiness_summary["checkpoint_capture"] = checkpoint_health
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
            summary=readiness_summary,
            disabled_capabilities=disabled,
            counts=counts,
            readiness=readiness_summary,
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
            origin=str(row.get("origin") or "chat"),
            match_snippet=str(row.get("match_snippet") or ""),
            match_turn_id=str(row.get("match_turn_id") or ""),
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
            reasoning_chars=int(row.get("reasoning_chars") or 0),
            reasoning=row.get("reasoning_text"),
        )

    @staticmethod
    def _event_view(row: dict[str, Any]) -> EventView:
        machine_identity = (
            DashboardService._proposal_identity(row)
            if row.get("proposed_by")
            else None
        )
        return EventView(
            event_id=str(row["event_id"]),
            session_id=str(row.get("session_id", "")),
            turn_id=row.get("turn_id"),
            event_type=str(row.get("event_type", "")),
            actor=str(row.get("actor", "")),
            timestamp=str(row.get("timestamp", "")),
            risk_level=row.get("risk_level"),
            summary=row.get("summary"),
            machine_identity=machine_identity,
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

    @staticmethod
    def _proposal_identity(row: dict[str, Any]) -> IdentityView:
        principal_id = str(row.get("proposed_by") or "agent_runtime")
        principal_type = str(row.get("proposer_principal_type") or "unknown")
        turn_id = str(row.get("turn_id") or "") or None
        expires_at = str(row.get("machine_expires_at") or "") or None
        if row.get("machine_is_active") is not None and not bool(
            row.get("machine_is_active")
        ):
            state = "inactive"
        elif expires_at and expires_at < utc_now():
            state = "expired"
        elif principal_type == "ai_agent":
            state = "active"
        else:
            state = "unknown"
        display_name = str(row.get("proposer_display_name") or "")
        if not display_name and principal_type == "ai_agent":
            display_name = f"Raiker agent · {turn_id or 'turn'}"
        return IdentityView(
            principal_id=principal_id,
            principal_type=principal_type,
            display_name=display_name or principal_id,
            subject=str(row.get("machine_subject") or "") or None,
            turn_id=turn_id,
            key_id=str(row.get("machine_key_id") or "") or None,
            issued_at=str(row.get("machine_issued_at") or "") or None,
            expires_at=expires_at,
            state=state,
        )

    @staticmethod
    def _authorizer_identity(row: dict[str, Any]) -> IdentityView | None:
        principal_id = str(row.get("approved_by") or "")
        if not principal_id:
            return None
        return IdentityView(
            principal_id=principal_id,
            principal_type=str(row.get("authorizer_principal_type") or "human"),
            display_name=str(row.get("authorizer_display_name") or principal_id),
            state="active",
        )

    @classmethod
    def _approval_view(
        cls, row: dict[str, Any], *, queue: dict[str, tuple[int, int]] | None = None
    ) -> ApprovalView:
        tool_name = str(row.get("tool_name", ""))
        status = str(row.get("status", ""))
        created_at = str(row.get("created_at", ""))
        expires_at = str(row.get("expires_at", "")) or None
        # An approval with no parked turn behind it is a batch of one, which is
        # what the defaults say.
        queue_position, queue_total = (queue or {}).get(str(row["approval_id"]), (1, 1))
        proposed_by = cls._proposal_identity(row)
        approved_by = cls._authorizer_identity(row)
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
            proposed_by=proposed_by,
            approved_by=approved_by,
            machine_identity=(
                proposed_by if proposed_by.principal_type == "ai_agent" else None
            ),
            critical=bool(row.get("critical")),
            resolved_by=(str(row["approved_by"]) if row.get("approved_by") else None),
            queue_position=queue_position,
            queue_total=queue_total,
        )

    def _approval_detail(
        self, row: dict[str, Any], *, principal_id: str | None = None
    ) -> ApprovalDetailView:
        from raiker.approvals.execution import ApprovalExecutionBridge

        approval_id = str(row["approval_id"])
        view = self._approval_view(
            row, queue=self.store.suspended_turn_queue_positions([approval_id])
        )
        try:
            raw_args = json.loads(str(row.get("arguments_json", "{}")))
        except (ValueError, TypeError):
            raw_args = {}
        arguments = self._redact_arguments(raw_args)
        diff, diff_path, kind = self._build_preview(
            view.tool_name, raw_args, principal_id=principal_id
        )
        connector_write = view.tool_name == "connector_write"
        # BUG-06 — the notice is derived from what the server will actually do,
        # not from a constant. A file mutation executes only when the relay and
        # the target capability are both enabled; either gate being off returns
        # this approval to metadata-only, and the notice says so.
        relays = ApprovalExecutionBridge(self.store).executes_on_resolution(
            view.tool_name, principal_id, critical=view.critical
        )
        if connector_write:
            notice = "Approving this connector write executes this exact action once."
        elif relays and view.tool_name == "create_task":
            # BUG-62 — the file wording below promises a checkpointed diff, which
            # a task row does not have. Saying where it lands is the useful part.
            notice = (
                "Approving this creates the task above in Tasks, once, under a fresh "
                "capability, policy and posture check. It is a local row you can stop "
                "and delete there; nothing else runs until the task itself does."
            )
        elif relays and view.tool_name == "assign_session_project":
            notice = (
                "Approving this moves the proposing conversation into the project above, "
                "once. A project is an organizing scope: the move grants nothing, changes "
                "no gate, and is reversed in Projects."
            )
        elif relays and view.tool_name == "git_commit":
            # B11 — the file wording below promises a checkpointed rewind, and a
            # commit is not a file the checkpoint store holds a pre-image of.
            notice = (
                "Approving this records the change set above as one commit, once, "
                "under a fresh capability, policy and posture check. Repository "
                "hooks do not run. It is git history rather than a checkpointed "
                "file write, so undo it in git."
            )
        elif relays and view.tool_name == "git_branch":
            notice = (
                "Approving this creates the branch above and checks it out, once, "
                "under a fresh capability, policy and posture check. No commit is "
                "made and no file is changed; delete the branch in git to undo it."
            )
        elif relays and view.tool_name == "git_push":
            # BUG-67 — the branch and the commit above are local and the owner
            # can undo them in git. This one leaves the machine, so it is worded
            # like the GitHub write below rather than like its own siblings.
            notice = (
                "Approving this sends the commits above to the remote shown, once, "
                "with your own credential. It never forces and never deletes a "
                "branch, but it leaves this machine and git cannot take it back — "
                "undo it on the remote."
            )
        elif relays and view.tool_name == "github_write":
            notice = (
                "Approving this sends the request above to GitHub with your own "
                "token, once. It leaves this machine and cannot be unsent — close "
                "or delete it on GitHub to undo it."
            )
        elif relays and view.tool_name == "checkpoint_restore":
            # BUG-230 — the rewind. The wording below promises a checkpoint of
            # the previous contents, which is exactly what this action consumes
            # rather than produces; and the one fact an owner needs here is that
            # the restore is itself captured, so approving is not a one-way door.
            notice = (
                "Approving this rewinds the files listed above to their state at "
                "the checkpoint, once, under a fresh capability, policy and posture "
                "check. The restore captures its own pre-image first, so it appears "
                "as a new checkpoint and can be rewound the same way. Files marked "
                "skipped are left exactly as they are."
            )
        elif relays:
            # BUG-233 — the rewind sentence was a constant for the whole
            # file-mutation class, and for a file over the pre-image cap it was
            # false: the write still happens, its pre-image is recorded
            # `oversize`, and nothing can put it back. The owner read the promise
            # *before* deciding, so the check has to happen here, before the
            # decision, rather than at capture time after it.
            oversize = self._oversize_target(view.tool_name, raw_args)
            if oversize is not None:
                path, size_bytes = oversize
                notice = (
                    "Approving this performs the change shown above, once, in your "
                    "workspace — under a fresh capability, policy and posture check. "
                    f"**This change cannot be rewound.** `{path}` is "
                    f"{size_bytes // (1024 * 1024)} MiB, over the "
                    f"{MAX_PRE_IMAGE_BYTES // (1024 * 1024)} MiB checkpoint pre-image "
                    "cap, so no copy of the previous contents is kept."
                )
            else:
                notice = (
                    "Approving this performs the change shown above, once, in your "
                    "workspace — under a fresh capability, policy and posture check. "
                    "The previous file contents are checkpointed first, so it can be "
                    "rewound."
                )
        else:
            notice = (
                "Approval resolution is metadata-only. Recording a decision does "
                "NOT execute the action."
            )
        # BUG-218 — when Auto withheld this action rather than granting it, the
        # owner is looking at an approval they did not expect to see. Saying why,
        # first, is what makes it a question they can answer.
        withheld = self._alignment_withheld(view.approval_id, turn_id=view.turn_id)
        if withheld:
            notice = f"{withheld}\n\n{notice}"
        return ApprovalDetailView(
            approval=view,
            arguments=arguments,
            diff=diff,
            diff_path=diff_path,
            preview_kind=kind,
            metadata_only_notice=notice,
            executes_on_approval=connector_write or relays,
            execution_evidence=self._approval_execution_evidence(
                view.approval_id, turn_id=view.turn_id
            ),
        )

    def _alignment_withheld(self, approval_id: str, *, turn_id: str | None) -> str:
        """The sentence Auto's alignment check left behind, or ``""``.

        BUG-218 — read from the durable ``approval_requested`` event rather than
        recomputed here. The check is deterministic and would give the same
        answer, but recomputing it would also attach the sentence to approvals
        raised in **manual** mode, where the check never ran and Auto promised
        nothing. What the owner is told has to match what actually happened.
        """
        from raiker.events.query import EventViewer

        if not turn_id:
            return ""
        viewer = EventViewer(self.store)
        for row in viewer.list_events(
            turn_id=turn_id, event_type="approval_requested", limit=50
        ):
            event = viewer.read_event_payload(str(row.get("event_id", "")))
            payload = event.get("payload") if isinstance(event, dict) else None
            if not isinstance(payload, dict) or payload.get("approval_id") != approval_id:
                continue
            alignment = payload.get("alignment")
            if isinstance(alignment, dict) and not alignment.get("aligned", True):
                return str(alignment.get("message") or "")
            return ""
        return ""

    def _approval_execution_evidence(
        self, approval_id: str, *, turn_id: str | None
    ) -> dict[str, Any]:
        """Return the durable relay evidence for one resolved approval."""
        from raiker.events.query import EventViewer

        viewer = EventViewer(self.store)
        # Relay audit events use the resolving API session id, not the original
        # chat session id. A turn id remains stable across both boundaries and
        # narrows the durable lookup to the approval's own execution history.
        event_rows = viewer.list_events(
            turn_id=turn_id, event_type="approval_executed", limit=50
        ) if turn_id else viewer.list_events(event_type="approval_executed", limit=500)
        for row in event_rows:
            event = viewer.read_event_payload(str(row.get("event_id", "")))
            payload = event.get("payload") if isinstance(event, dict) else None
            if not isinstance(payload, dict) or payload.get("approval_id") != approval_id:
                continue
            result = payload.get("result")
            return {
                "principal_id": payload.get("principal_id"),
                **(result if isinstance(result, dict) else {}),
            }
        return {}

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

    def _git_root(self, principal_id: str | None) -> Path:
        """The repository a git approval was computed against (BUG-66).

        The same resolution the broker and the executor use, so the diff the
        owner reviews, the sentence they are shown, and the repository the change
        lands in are one answer rather than three.
        """
        scope: str | None = None
        if principal_id:
            try:
                scope = self.store.account_scope(principal_id) or principal_id
            except Exception:  # noqa: BLE001 — a storage failure falls back to the workspace
                scope = None
        return resolve_repository_root(
            self.workspace_root, selected_repository_subpath(self.store, scope)
        )

    #: Tools whose approval promises a checkpointed rewind, keyed by the argument
    #: naming the file the promise is about.
    _REWIND_PROMISE_TOOLS: dict[str, str] = {
        "write_file": "path",
        "edit_file": "path",
        "create_document": "path",
        "apply_patch": "path",
    }

    def _oversize_target(
        self, tool_name: str, args: dict[str, Any]
    ) -> tuple[str, int] | None:
        """``(path, size)`` when the target is too large to checkpoint, else None.

        BUG-233. Only an *existing* file has a pre-image to lose, so a new file is
        not oversize however large the proposed content is: there is nothing to
        rewind to either way. A path that does not resolve inside the workspace is
        not this function's problem — the executor refuses it — so it reports no
        promise rather than guessing.
        """
        argument = self._REWIND_PROMISE_TOOLS.get(tool_name)
        if argument is None:
            return None
        raw_path = str(args.get(argument, "")).strip()
        if not raw_path:
            return None
        try:
            resolved = resolve_workspace_path(self.workspace_root, raw_path)
        except FilesystemSafetyError:
            return None
        try:
            if not resolved.is_file():
                return None
            size = resolved.stat().st_size
        except OSError:
            return None
        return (raw_path, size) if size > MAX_PRE_IMAGE_BYTES else None

    def _build_preview(
        self, tool_name: str, args: dict[str, Any], *, principal_id: str | None = None
    ) -> tuple[str | None, str | None, str]:
        """Return (diff, path, preview_kind). File mutations get a unified diff; never executes."""
        if tool_name == "checkpoint_restore":
            # BUG-230 — the approval carries the same preflight the Checkpoints
            # panel shows, recomputed here from the capture manifest rather than
            # taken from the caller, so the owner decides on what will actually
            # run. Metadata only: paths, operations and sizes, never content.
            from raiker.checkpoints.service import CheckpointService

            checkpoint_id = str(args.get("checkpoint_id", "")).strip()
            try:
                plan = CheckpointService(self.store).compute_restore_plan(
                    checkpoint_id, restoring_principal_id=principal_id
                )
            except (ValueError, OSError):
                return None, checkpoint_id or None, "arguments"
            files: list[dict[str, Any]] = plan.get("files", [])  # type: ignore[assignment]
            lines = [
                f"Checkpoint {checkpoint_id}",
                f"{plan['restore_content_count']} to rewrite, "
                f"{plan['delete_count']} to delete, {plan['skip_count']} skipped "
                f"(too large to have been captured).",
                "",
            ]
            for entry in files:
                marks: list[str] = []
                if entry.get("changed_by_other_principal"):
                    marks.append("last changed by a different principal")
                if entry.get("op") == "skip_oversize":
                    marks.append("not restorable — over the pre-image cap")
                suffix = f"  [{'; '.join(marks)}]" if marks else ""
                lines.append(f"{entry['op']:>16}  {entry['workspace_path']}{suffix}")
            return "\n".join(lines), checkpoint_id or None, "checkpoint_restore"
        if tool_name == "write_file":
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
        if tool_name == "edit_file":
            try:
                snapshot = proposed_edit_snapshot(
                    self.workspace_root,
                    str(args.get("path", ".")),
                    str(args.get("old_text", "")),
                    str(args.get("new_text", "")),
                )
            except FilesystemSafetyError:
                return None, str(args.get("path", "")), "arguments"
            if snapshot["status"] == "failed":
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
            try:
                snapshot = proposed_patch_snapshot(
                    self.workspace_root,
                    str(args["path"]) if args.get("path") else None,
                    str(args.get("patch", "")),
                )
            except FilesystemSafetyError:
                return None, str(args.get("path", "")), "arguments"
            if snapshot["status"] == "failed":
                return None, str(args.get("path", "")), "arguments"
            changes = snapshot.get("changes") or [snapshot]
            diffs: list[str] = []
            for change in changes:
                path = str(change.get("path", ""))
                diffs.append("".join(difflib.unified_diff(
                    redact_secret_like_text(change.get("before_snapshot") or "").splitlines(keepends=True),
                    redact_secret_like_text(str(change.get("proposed_text", ""))).splitlines(keepends=True),
                    fromfile=f"a/{path}", tofile=f"b/{path}",
                )))
            paths = [str(item.get("path", "")) for item in changes]
            return "".join(diffs), ", ".join(paths), "file_diff"
        if tool_name == "connector_write":
            connector = str(args.get("connector_id", "connector"))
            operation = str(args.get("operation_id", "operation"))
            request_arguments = self._redact_value(args.get("arguments", {}))
            return json.dumps(request_arguments, indent=2, sort_keys=True), f"{connector} / {operation}", "connector_request"
        # B11 — the git write path. A commit is reviewed the way a file change
        # is, as a diff; a branch is reviewed as the two refs it moves between,
        # because there is no diff to show and pretending otherwise would be
        # worse than saying so.
        repo_root = self._git_root(principal_id)
        repository = repository_label(self.workspace_root, repo_root)
        if tool_name == "git_commit":
            snapshot = proposed_commit_snapshot(
                repo_root, str(args.get("message", "")), args.get("paths")
            )
            if snapshot["status"] != "success":
                return None, None, "arguments"
            header = "\n".join(
                f"{entry['state']:>10}  "
                + (
                    f"{entry['previous_path']} → {entry['path']}"
                    if entry.get("previous_path")
                    else entry["path"]
                )
                for entry in snapshot["files"]
            )
            body = redact_secret_like_text(str(snapshot["diff"]))
            truncated = "\n\n(diff truncated)" if snapshot["truncated"] else ""
            return (
                f"{snapshot['file_count']} file(s) on {snapshot['branch']} "
                f"in repository {repository}\n{header}\n\n{body}{truncated}",
                str(snapshot["branch"]),
                "git_change",
            )
        if tool_name == "git_branch":
            snapshot = proposed_branch_snapshot(
                repo_root,
                str(args.get("name", "")),
                str(args["base"]) if args.get("base") else None,
            )
            if snapshot["status"] != "success":
                return None, None, "arguments"
            lines = [
                f"repository    {repository}",
                f"new branch    {snapshot['name']}",
                f"branch from   {snapshot['base'] or snapshot['current_branch'] or snapshot['head']}",
                f"checked out   {snapshot['current_branch'] or '(detached HEAD)'} → {snapshot['name']}",
            ]
            if snapshot["uncommitted_files"]:
                lines.append(
                    f"carried over  {snapshot['uncommitted_files']} uncommitted file(s)"
                )
            return "\n".join(lines), str(snapshot["name"]), "git_change"
        # BUG-67 — a push has no diff either. What the owner needs before
        # deciding is where it goes and what it carries, so that is what is
        # shown: the remote and its host, the branch, and the commits that are
        # not there yet.
        if tool_name == "git_push":
            snapshot = proposed_push_snapshot(
                repo_root,
                str(args["remote"]) if args.get("remote") else None,
                str(args["branch"]) if args.get("branch") else None,
            )
            if snapshot["status"] != "success":
                return None, None, "arguments"
            lines = [
                f"repository    {repository}",
                f"remote        {snapshot['remote']} ({snapshot['host']})",
                f"branch        {snapshot['branch']}"
                + ("  — new on the remote" if snapshot["creates_remote_branch"] else ""),
                f"sending       {snapshot['commit_count']} commit(s)",
            ]
            if snapshot["behind"]:
                lines.append(
                    f"remote ahead  {snapshot['behind']} commit(s) this branch does not have"
                )
            lines.append("")
            lines.extend(f"  {line}" for line in snapshot["commits"])
            if snapshot["truncated"]:
                lines.append("  …")
            return (
                "\n".join(lines),
                f"{snapshot['remote']}/{snapshot['branch']}",
                "git_change",
            )
        if tool_name == "github_write":
            request_arguments = self._redact_value(
                {k: v for k, v in args.items() if k not in ("operation", "repo")}
            )
            return (
                json.dumps(request_arguments, indent=2, sort_keys=True),
                f"{args.get('repo', 'repository')} / {args.get('operation', 'write')}",
                "connector_request",
            )
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
            model_profile=d.get("model_profile"),
            model=d.get("model"),
            attachments=list(d.get("attachments") or []),
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
