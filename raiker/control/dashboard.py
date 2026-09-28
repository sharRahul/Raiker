from __future__ import annotations

import base64
import contextlib
import hashlib
import hmac
import json
import os
import re
import shutil
import stat
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from raiker.auth.app_key import ensure_app_key
from raiker.control.knowledge_scope import (
    KNOWLEDGE_SOURCE_EXTENSIONS,
    REVIEW_ACCEPTED_FILE_BUDGET,
    REVIEW_DEPTH_BUDGET,
    REVIEW_TIME_BUDGET_SECONDS,
    REVIEW_VISITED_ENTRY_BUDGET,
    SKIPPED_DIRECTORY_NAMES,
)
from raiker.control.project_paths import (
    LEGACY_PROJECT_ROOT as _LEGACY_PROJECT_ROOT,
)
from raiker.control.project_paths import (
    MANAGED_PROJECT_ROOT as _MANAGED_PROJECT_ROOT,
)
from raiker.control.project_paths import (
    contained_project_root as _contained_project_root,
)
from raiker.control.project_paths import (
    project_root_parts as _project_root_parts,
)
from raiker.control.service import RuntimeControlService
from raiker.runtime.authority.models import PrincipalType
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.history import TaskAttemptView, TaskEventView
from raiker.tasks.scheduler import RECURRING_INTERVALS

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
class _SourceReviewWalk:
    """What one bounded review walk found, and what it cost to find it."""

    supported: int
    unsupported: int
    total_bytes: int
    examples: tuple[str, ...]
    #: Every entry looked at, accepted or skipped. The number the old cap was
    #: mistaken for.
    visited: int
    truncated_reason: str | None


def _walk_source_for_review(path: Path, base: Path) -> _SourceReviewWalk:
    """Walk *path* for an indexing plan, under four budgets that actually bind.

    NEW-MAP-03. The previous walk was ``path.rglob("*")`` with a counter that
    only advanced on entries it accepted, so everything it skipped was free:
    every directory, every hidden path, every name under ``node_modules``, every
    file it could not ``stat``. A cap of 5,000 therefore bounded the *answer*
    and not the *work*, and a folder with a large dependency tree beside it was
    walked in full to report the six files an owner cared about.

    Three things change:

    * **Excluded directories are pruned before descent** rather than after
      every entry inside them has been produced. ``os.walk`` lets the walker
      edit the directory list in place, which is the difference between not
      entering ``node_modules`` and enumerating it and discarding the result.
    * **Every entry visited is counted**, whatever happens to it, so the visit
      budget is a bound on the work and the file budget stays a bound on the
      answer.
    * **Depth and elapsed time are their own budgets.** A pathological tree is
      deep rather than wide, and a slow drive is neither — no counter of entries
      notices either one.

    Symlinked directories are not followed (``os.walk`` does not by default),
    which is what stops a cycle; the containment check below is unchanged and
    still judges every accepted file against the selected root.
    """
    started = time.monotonic()
    supported = 0
    unsupported = 0
    total_bytes = 0
    visited = 0
    examples: list[str] = []
    truncated: str | None = None

    def _example(resolved: Path) -> None:
        if len(examples) < 8:
            with contextlib.suppress(ValueError):
                examples.append(resolved.relative_to(base).as_posix())

    def _consider(candidate: Path) -> None:
        """Count one file, if it is one Raiker could read."""
        nonlocal supported, unsupported, total_bytes
        try:
            resolved = candidate.resolve()
            if resolved != base and base not in resolved.parents:
                return
            size = candidate.stat().st_size
        except (OSError, ValueError):
            return
        if candidate.suffix.casefold() in KNOWLEDGE_SOURCE_EXTENSIONS and size <= 5 * 1024 * 1024:
            supported += 1
            total_bytes += size
            _example(resolved)
        else:
            unsupported += 1

    if path.is_file():
        visited = 1
        _consider(path)
        return _SourceReviewWalk(
            supported, unsupported, total_bytes, tuple(examples), visited, None
        )

    base_depth = len(path.parts)
    for dirpath, dirnames, filenames in os.walk(path, onerror=None):
        here = Path(dirpath)
        depth = len(here.parts) - base_depth
        # Pruned in place, before anything inside them is produced. This is the
        # whole finding: the previous walk enumerated these and threw the
        # entries away one at a time.
        dirnames[:] = [
            name
            for name in dirnames
            if name not in SKIPPED_DIRECTORY_NAMES and not name.startswith(".")
        ]
        visited += len(dirnames)
        if depth >= REVIEW_DEPTH_BUDGET:
            dirnames.clear()
            truncated = truncated or "depth_cap"

        for name in filenames:
            visited += 1
            if visited >= REVIEW_VISITED_ENTRY_BUDGET:
                truncated = "visited_entry_cap"
                break
            if time.monotonic() - started >= REVIEW_TIME_BUDGET_SECONDS:
                truncated = "time_cap"
                break
            if name.startswith("."):
                continue
            _consider(here / name)
            # The accepted-file budget is checked after the file is counted, so
            # the number the owner reads is the number that was reached.
            if supported + unsupported >= REVIEW_ACCEPTED_FILE_BUDGET:
                truncated = "accepted_file_cap"
                break

        if truncated in {"visited_entry_cap", "time_cap", "accepted_file_cap"}:
            break
        if visited >= REVIEW_VISITED_ENTRY_BUDGET:
            truncated = "visited_entry_cap"
            break
        if time.monotonic() - started >= REVIEW_TIME_BUDGET_SECONDS:
            truncated = "time_cap"
            break

    return _SourceReviewWalk(
        supported, unsupported, total_bytes, tuple(examples), visited, truncated
    )


def _runs_on_this_platform(profile: Any) -> bool:
    """Whether a profile's runtime can exist on the machine Raiker is on.

    MLX is an Apple-silicon framework, so on Windows and Linux its four slot
    profiles were four rows in every provider list, four entries in the model
    picker, and four things to set up that nothing on the machine could ever
    serve. A profile whose runtime cannot exist here is not a choice, so it is
    not published. Profiles that declare nothing are published everywhere —
    llama.cpp included, which runs on macOS as happily as it does anywhere.
    """
    required = profile.raw.get("requires_platform")
    if not required:
        return True
    platforms = required if isinstance(required, list) else [required]
    return sys.platform in {str(name) for name in platforms}


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


def _handler_target(handler: Any) -> str:
    """What a hook handler points at, in one line for the rule's card.

    An `http` handler's destination is the URL it posts to — the fact an owner
    needs when the grant does not cover it, because the host in that URL is what
    they have to add.
    """
    if handler.type == "command" and handler.command:
        return " ".join(handler.command)
    if handler.type == "builtin":
        return handler.builtin or ""
    if handler.type == "http":
        return handler.url or ""
    return handler.model or "owner-selected model"


def _declaration_summaries(stored: Any) -> tuple[dict[str, Any], ...]:
    """The owner-facing summary of what a server declared for each of its tools.

    Backlog #16 (MCP half). The card used to show a row of tool-name chips and
    nothing else, so a server whose tools had no declared arguments looked
    identical to one whose tools were fully described — and the owner could not
    tell whether the model was calling them with real arguments or guesses.

    Re-bounded on the way out (`decode_declarations`), so an older row written
    before those bounds existed is still safe to render, and the *argument
    names* are carried rather than the whole schema: the card answers "what does
    this tool take", not "paste me a JSON Schema".
    """
    from raiker.tools.mcp_schema import decode_declarations

    summaries: list[dict[str, Any]] = []
    for declaration in decode_declarations(stored):
        schema = declaration.input_schema or {}
        properties = schema.get("properties") if isinstance(schema, dict) else None
        argument_names = sorted(properties) if isinstance(properties, dict) else []
        required = schema.get("required") if isinstance(schema, dict) else None
        summaries.append(
            {
                "name": declaration.name,
                "title": declaration.title,
                "description": declaration.description,
                "has_schema": declaration.input_schema is not None,
                "schema_reason": declaration.schema_reason,
                "arguments": argument_names,
                "required": sorted(str(item) for item in required) if isinstance(required, list) else [],
            }
        )
    return tuple(summaries)


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
    # Backlog #16 (MCP half) — what each of those tools said it takes, bounded
    # by `raiker.tools.mcp_schema` before it was stored. One entry per tool that
    # declared something: its name, the server's own sentence, and whether the
    # declared argument schema is carried or why it is not. Still never
    # arguments a call passed or output it returned.
    tool_declarations: tuple[dict[str, Any], ...] = ()
    # BUG-234 — what this server offers that Raiker does not use, one sentence
    # each: capabilities it declared beyond `tools`, and what the transport was
    # observed doing. Empty when a server offers only what Raiker uses. The rule
    # is "supported, or named as unsupported" — never silently degraded.
    unsupported_features: tuple[dict[str, str], ...] = ()
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


def _stored_content_parts(summary: Any) -> tuple[dict[str, Any], ...]:
    """A stored answer's declared parts, or nothing when it declared none.

    BUG-300. A live turn carries ``content_parts`` because the response object
    derives them; a turn read back from the record is just a string, and every
    surface that reopened one showed the raw ``raiker:table`` fence with its
    JSON. The splitter is pure, so the answer is the same answer split the same
    way — what this adds is that the surfaces reading the record get it too.

    Empty when the answer declared nothing, so the payload for an ordinary turn
    is byte-for-byte what it was and a client that ignores the field sees what
    it always saw.
    """
    from raiker.runtime.typed_parts import content_parts, renders_as_parts

    if not isinstance(summary, str) or not summary:
        return ()
    parts = content_parts(summary)
    if not renders_as_parts(parts):
        return ()
    return tuple(part.to_dict() for part in parts)


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
    # Backlog #25 - the per-turn tool rows, rebuilt from the durable record.
    # Live, these arrive on the stream and the client assembles them; a reload
    # had no stream and so lost half of what the turn said it did. Rebuilt
    # server-side through the same `raiker.tools.presentation` function the live
    # path uses, so a reloaded row can never say more than the one it replaces.
    tool_rows: tuple[dict[str, Any], ...] = ()
    # BUG-300 - the parts this answer declared, so a turn reopened from the
    # record renders as the table it was rather than as the fence that declared
    # one. Derived here rather than in the browser for the same reason the tool
    # rows above are: the split is part of what the runtime decided the answer
    # was, and two implementations of it would eventually disagree. Empty for
    # every answer that declared nothing, which is nearly all of them.
    content_parts: tuple[dict[str, Any], ...] = ()

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
    #: MEM-10 - what it would take to have a semantic space at all. `spaces`
    #: above is read from the vectors that exist, so on a default install it
    #: holds only the lexical fallback and the page can offer no better choice.
    #: These two say why: the embedding models this install could call, and how
    #: many approved memories are waiting to be embedded into one.
    embedding_providers: tuple[dict[str, Any], ...] = ()
    unindexed_memories: int = 0
    unindexed_file_chunks: int = 0
    #: The retrieval implementation, stated separately from the embedding model:
    #: the owner should not have to infer whether growing history changes lookup.
    vector_search_strategy: str = "exact_then_approximate"
    vector_search_exact_limit: int = 512

    def to_dict(self) -> dict[str, Any]:
        return {
            "incognito": self.incognito,
            "embedding_backend": self.embedding_backend,
            "retrieval": dict(self.retrieval),
            "spaces": [dict(space) for space in self.spaces],
            "embedding_providers": [dict(item) for item in self.embedding_providers],
            "unindexed_memories": self.unindexed_memories,
            "unindexed_file_chunks": self.unindexed_file_chunks,
            "vector_search_strategy": self.vector_search_strategy,
            "vector_search_exact_limit": self.vector_search_exact_limit,
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
    # Which kind of root this project has, and what to call it. Carried on the
    # list rather than fetched per card, because the delete confirmation has to
    # say whether a folder survives *before* the owner opens anything.
    root_kind: str = "managed"
    root_label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProjectRootMigrationReport:
    """The safe, repeatable outcome of moving legacy project folders."""

    migrated: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    unchanged: tuple[str, ...] = ()
    retained_residues: tuple[str, ...] = ()


def _default_root_label(row: dict[str, Any]) -> str:
    """A short name for the project's root, without resolving the grant.

    The grant's path arrives on the row from `list_projects`, so naming an
    attached folder costs no extra query. A managed project falls back to its
    subpath's last segment, which is its slug.
    """
    granted = str(row.get("root_grant_path") or "")
    if granted:
        return Path(granted).name or granted
    subpath = str(row.get("root_subpath") or "")
    return subpath.rsplit("/", 1)[-1] if subpath else ""


def _copy_project_tree_exclusive(source: Path, destination: Path) -> None:
    """Copy a tree into an exclusively reserved directory without replacement."""
    for child in source.iterdir():
        target = destination / child.name
        if child.is_symlink():
            raise OSError("project_root_symlink_not_migrated")
        if child.is_dir():
            target.mkdir()
            _copy_project_tree_exclusive(child, target)
        elif child.is_file():
            with child.open("rb") as reader, target.open("xb") as writer:
                shutil.copyfileobj(reader, writer)
            shutil.copystat(child, target, follow_symlinks=False)
        else:
            raise OSError("project_root_special_file_not_migrated")


_PROJECT_ROOT_MIGRATION_DIR = "project-migrations"
_PROJECT_ROOT_STAGE_TREE = "tree"
_PROJECT_ROOT_STAGE_COMPLETE = ".complete"


def _copy_project_tree_resuming(source: Path, destination: Path) -> None:
    """Complete a reserved publication without replacing any existing entry."""
    for child in source.iterdir():
        target = destination / child.name
        if child.is_symlink():
            raise OSError("project_root_symlink_not_migrated")
        if child.is_dir():
            if target.is_symlink() or (target.exists() and not target.is_dir()):
                raise FileExistsError(target)
            if not target.exists():
                target.mkdir()
            _copy_project_tree_resuming(child, target)
        elif child.is_file():
            if target.exists() or target.is_symlink():
                if not target.is_file() or not _same_file(child, target):
                    raise FileExistsError(target)
                continue
            with child.open("rb") as reader, target.open("xb") as writer:
                shutil.copyfileobj(reader, writer)
            shutil.copystat(child, target, follow_symlinks=False)
        else:
            raise OSError("project_root_special_file_not_migrated")


def _same_file(left: Path, right: Path) -> bool:
    if left.stat().st_size != right.stat().st_size:
        return False
    with left.open("rb") as first, right.open("rb") as second:
        while first_chunk := first.read(64 * 1024):
            if first_chunk != second.read(len(first_chunk)):
                return False
        return not second.read(1)


def _same_project_tree(left: Path, right: Path) -> bool:
    """Return true only when two regular project trees have identical content."""
    try:
        left_children = sorted(left.iterdir(), key=lambda child: child.name)
        right_children = sorted(right.iterdir(), key=lambda child: child.name)
    except OSError:
        return False
    if [child.name for child in left_children] != [child.name for child in right_children]:
        return False
    for left_child, right_child in zip(left_children, right_children, strict=True):
        if left_child.is_symlink() or right_child.is_symlink():
            return False
        if left_child.is_dir():
            if not right_child.is_dir() or not _same_project_tree(left_child, right_child):
                return False
        elif left_child.is_file():
            if not right_child.is_file() or not _same_file(left_child, right_child):
                return False
        else:
            return False
    return True


def _write_reservation(path: Path, reservation: dict[str, str]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(reservation, sort_keys=True))
        handle.flush()
        os.fsync(handle.fileno())


def _read_reservation(path: Path) -> dict[str, str] | None:
    if path.is_symlink() or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return (
        data
        if isinstance(data, dict) and all(isinstance(value, str) for value in data.values())
        else None
    )


def _project_migration_area(workspace: Path) -> Path:
    """Return Raiker-owned staging storage, never a project file namespace."""
    runtime = workspace / ".raiker"
    area = runtime / _PROJECT_ROOT_MIGRATION_DIR
    for directory in (runtime, area):
        if _is_reparse_point(directory) or (directory.exists() and not directory.is_dir()):
            raise OSError("project_migration_storage_invalid")
    area.mkdir(parents=True, exist_ok=True)
    if _is_reparse_point(area) or not area.is_dir():
        raise OSError("project_migration_storage_invalid")
    return area


def _is_reparse_point(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return path.is_symlink() or bool(
        getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


@dataclass(frozen=True)
class _SourceIdentity:
    """One reading of a project tree, in the two forms the migration needs.

    ``strict`` answers "is this tree still exactly what it was?". ``moved``
    answers the same question about a tree that has just been renamed, and
    differs in exactly one field: a rename bumps the renamed directory's own
    ``st_ctime_ns`` while leaving its inode, size, mtime and every child
    untouched, so the strict form can never hold after a move. Everything that
    would betray a swapped-in tree — the device and inode, the mtime, and every
    child's metadata and bytes — is in both.
    """

    strict: str
    moved: str


def _source_identity(source: Path) -> _SourceIdentity | None:
    """Return a stable content identity for a regular project tree."""
    try:
        before = source.stat(follow_symlinks=False)
    except OSError:
        return None
    if source.is_symlink() or not source.is_dir():
        return None
    digest = hashlib.sha256()
    moved_digest = hashlib.sha256()

    def metadata(info: os.stat_result, *, ctime: bool = True) -> bytes:
        fields = f"{info.st_dev}:{info.st_ino}:{info.st_size}:{info.st_mtime_ns}"
        if ctime:
            fields += f":{info.st_ctime_ns}"
        return f"{fields}\0".encode()

    def include_metadata(kind: bytes, relative: Path, info: os.stat_result) -> None:
        entry = kind + b"\0" + relative.as_posix().encode() + b"\0" + metadata(info)
        digest.update(entry)
        moved_digest.update(entry)

    # The root is the one entry the two readings disagree about, because it is
    # the one inode a rename of this tree touches.
    root_header = b"directory\0.\0"
    digest.update(root_header + metadata(before))
    moved_digest.update(root_header + metadata(before, ctime=False))

    def include(directory: Path, relative: Path) -> bool:
        try:
            children = sorted(directory.iterdir(), key=lambda child: child.name)
        except OSError:
            return False
        for child in children:
            child_relative = relative / child.name
            if child.is_symlink():
                return False
            if child.is_dir():
                try:
                    child_before = child.stat(follow_symlinks=False)
                except OSError:
                    return False
                include_metadata(b"directory", child_relative, child_before)
                if not include(child, child_relative):
                    return False
                try:
                    child_after = child.stat(follow_symlinks=False)
                except OSError:
                    return False
                if (
                    child_before.st_dev,
                    child_before.st_ino,
                    child_before.st_size,
                    child_before.st_mtime_ns,
                    child_before.st_ctime_ns,
                ) != (
                    child_after.st_dev,
                    child_after.st_ino,
                    child_after.st_size,
                    child_after.st_mtime_ns,
                    child_after.st_ctime_ns,
                ):
                    return False
                continue
            if not child.is_file():
                return False
            try:
                child_before = child.stat(follow_symlinks=False)
                include_metadata(b"file", child_relative, child_before)
                with child.open("rb") as reader:
                    while chunk := reader.read(64 * 1024):
                        digest.update(chunk)
                        moved_digest.update(chunk)
                child_after = child.stat(follow_symlinks=False)
            except OSError:
                return False
            if (
                child_before.st_dev,
                child_before.st_ino,
                child_before.st_size,
                child_before.st_mtime_ns,
                child_before.st_ctime_ns,
            ) != (
                child_after.st_dev,
                child_after.st_ino,
                child_after.st_size,
                child_after.st_mtime_ns,
                child_after.st_ctime_ns,
            ):
                return False
        return True

    if not include(source, Path(".")):
        return None
    try:
        after = source.stat(follow_symlinks=False)
    except OSError:
        return None
    if (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_ctime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ):
        return None
    return _SourceIdentity(digest.hexdigest(), moved_digest.hexdigest())


def _source_is_unchanged(source: Path, identity: _SourceIdentity) -> bool:
    current = _source_identity(source)
    return current is not None and current.strict == identity.strict


def _retain_migrated_source(
    workspace: Path, source: Path, identity: _SourceIdentity, migration_area: Path
) -> Path | None:
    """Retain a verified legacy tree as recoverable, inactive migration residue."""
    if not _source_is_unchanged(source, identity):
        return None
    try:
        if _project_migration_area(workspace) != migration_area:
            return None
    except OSError:
        return None
    residue = migration_area / f"residue-{uuid4().hex}"
    try:
        source.rename(residue)
    except OSError:
        return None
    # The rename is the one change the strict form cannot survive, so the residue
    # is checked against the reading that tolerates exactly that — and against
    # `identity`, taken before the migration published, so a tree swapped in
    # after the check above is still caught here and put back where it was.
    moved = _source_identity(residue)
    if moved is None or moved.moved != identity.moved:
        if not source.exists():
            with contextlib.suppress(OSError):
                residue.rename(source)
        return None
    return residue


def _stage_project_tree(source: Path, migration_area: Path) -> tuple[Path, Path]:
    stage = migration_area / uuid4().hex
    stage.mkdir()
    tree = stage / _PROJECT_ROOT_STAGE_TREE
    tree.mkdir()
    if source.exists():
        _copy_project_tree_exclusive(source, tree)
    complete = stage / _PROJECT_ROOT_STAGE_COMPLETE
    complete.touch(exist_ok=False)
    return stage, tree


def _new_reservation(
    workspace: Path, project_id: str, raw_root: str, stage_name: str
) -> dict[str, str]:
    reservation = {
        "project_id": project_id,
        "raw_root": raw_root,
        "stage_name": stage_name,
        "reservation_id": hmac.new(
            ensure_app_key(workspace), f"{project_id}\0{raw_root}".encode(), hashlib.sha256
        ).hexdigest(),
    }
    payload = json.dumps(reservation, separators=(",", ":"), sort_keys=True).encode()
    reservation["authentication"] = hmac.new(
        ensure_app_key(workspace), payload, hashlib.sha256
    ).hexdigest()
    return reservation


def _reservation_tree(
    workspace: Path,
    migration_area: Path,
    reservation: dict[str, str],
    project_id: str,
    raw_root: str,
) -> tuple[Path, Path] | None:
    if reservation.get("project_id") != project_id or reservation.get("raw_root") != raw_root:
        return None
    reservation_id = reservation.get("reservation_id", "")
    authentication = reservation.get("authentication", "")
    if not reservation_id or not authentication:
        return None
    payload = json.dumps(
        {
            "project_id": project_id,
            "raw_root": raw_root,
            "stage_name": reservation.get("stage_name", ""),
            "reservation_id": reservation_id,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    expected = hmac.new(ensure_app_key(workspace), payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(authentication, expected):
        return None
    stage_name = reservation.get("stage_name", "")
    if len(stage_name) != 32 or any(char not in "0123456789abcdef" for char in stage_name):
        return None
    stage = migration_area / stage_name
    tree = stage / _PROJECT_ROOT_STAGE_TREE
    if stage.is_symlink() or tree.is_symlink() or not stage.is_dir() or not tree.is_dir():
        return None
    if not (stage / _PROJECT_ROOT_STAGE_COMPLETE).is_file():
        return None
    return stage, tree


def _find_reservation(
    workspace: Path, migration_area: Path, project_id: str, raw_root: str
) -> tuple[dict[str, str], Path, Path] | None:
    candidates: list[tuple[dict[str, str], Path, Path]] = []
    for sidecar in migration_area.glob("*.json"):
        reservation = _read_reservation(sidecar)
        if reservation is None:
            continue
        staged = _reservation_tree(workspace, migration_area, reservation, project_id, raw_root)
        if staged is not None:
            candidates.append((reservation, *staged))
    if len(candidates) > 1:
        raise OSError("project_migration_reservation_ambiguous")
    return candidates[0] if candidates else None


def migrate_project_roots(workspace_root: Path, store: SQLiteStore) -> ProjectRootMigrationReport:
    """Move legacy ``projects/<slug>`` folders below `.raiker/projects` safely.

    A row changes only after its source and destination have passed containment
    validation. Existing destination folders are never merged or replaced.
    """
    workspace = Path(workspace_root).resolve()
    migrated: list[str] = []
    conflicts: list[str] = []
    unchanged: list[str] = []
    retained_residues: list[str] = []
    projects = store.list_projects()
    managed_roots: list[tuple[str, ...]] = [
        parsed[1]
        for project in projects
        if (parsed := _project_root_parts(str(project.get("root_subpath") or "")))
        and parsed[0] == _MANAGED_PROJECT_ROOT
    ]

    def migration_order(project: dict[str, Any]) -> tuple[int, int]:
        parsed = _project_root_parts(str(project.get("root_subpath") or ""))
        if parsed is not None and parsed[0] == _LEGACY_PROJECT_ROOT:
            return 0, len(parsed[1])
        return 1, 0

    for project in sorted(projects, key=migration_order):
        project_id = str(project["project_id"])
        raw_root = str(project.get("root_subpath") or "")
        source_info = _contained_project_root(workspace, raw_root)
        if source_info is None:
            conflicts.append(project_id)
            continue
        kind, relative, source = source_info
        if kind == _MANAGED_PROJECT_ROOT:
            unchanged.append(project_id)
            continue
        destination_subpath = "/".join((_MANAGED_PROJECT_ROOT, *relative))
        destination_info = _contained_project_root(workspace, destination_subpath)
        if destination_info is None:  # defensive: it is constructed above
            conflicts.append(project_id)
            continue
        destination = destination_info[2]
        was_moved_with_parent = any(
            len(relative) > len(parent) and relative[: len(parent)] == parent
            for parent in managed_roots
        )
        if source.is_symlink() or destination.is_symlink():
            conflicts.append(project_id)
            continue
        try:
            migration_area = _project_migration_area(workspace)
        except OSError:
            conflicts.append(project_id)
            continue
        try:
            owned_reservation = _find_reservation(workspace, migration_area, project_id, raw_root)
        except OSError:
            conflicts.append(project_id)
            continue
        nested_duplicate = (
            was_moved_with_parent
            and source.exists()
            and destination.exists()
            and destination.is_dir()
            and _same_project_tree(source, destination)
        )
        if destination.exists() and (
            destination.is_symlink()
            or not destination.is_dir()
            or (source.exists() and owned_reservation is None and not nested_duplicate)
            or (not source.exists() and owned_reservation is None and not was_moved_with_parent)
        ):
            conflicts.append(project_id)
            continue
        if source.exists() and not source.is_dir():
            conflicts.append(project_id)
            continue
        source_identity = _source_identity(source) if source.exists() else None
        if source.exists() and source_identity is None:
            conflicts.append(project_id)
            continue

        def publish(
            destination: Path = destination,
            destination_subpath: str = destination_subpath,
            source: Path = source,
            migration_area: Path = migration_area,
            was_moved_with_parent: bool = was_moved_with_parent,
            project_id: str = project_id,
            raw_root: str = raw_root,
        ) -> None:
            source_revalidated = _contained_project_root(workspace, raw_root)
            if (
                source_revalidated is None
                or source_revalidated[0] != _LEGACY_PROJECT_ROOT
                or source_revalidated[2] != source
                or source.is_symlink()
            ):
                raise OSError("project_root_source_invalid")
            destination.parent.mkdir(parents=True, exist_ok=True)
            revalidated = _contained_project_root(workspace, destination_subpath)
            if revalidated is None or revalidated[2] != destination:
                raise OSError("project_root_destination_invalid")
            if _project_migration_area(workspace) != migration_area:
                raise OSError("project_migration_storage_invalid")
            if destination.exists():
                if destination.is_symlink() or not destination.is_dir():
                    raise FileExistsError(destination)
                staged = _find_reservation(workspace, migration_area, project_id, raw_root)
                if staged is not None:
                    _copy_project_tree_resuming(
                        source if source.exists() else staged[2], destination
                    )
                    return
                if (
                    was_moved_with_parent
                    and source.exists()
                    and _same_project_tree(source, destination)
                ):
                    return
                if was_moved_with_parent and not source.exists():
                    return
                raise FileExistsError(destination)

            pending = _find_reservation(workspace, migration_area, project_id, raw_root)
            if pending is not None:
                destination.mkdir()
                _copy_project_tree_resuming(source if source.exists() else pending[2], destination)
                return
            stage, tree = _stage_project_tree(source, migration_area)
            reservation = _new_reservation(workspace, project_id, raw_root, stage.name)
            _write_reservation(
                migration_area / f"{reservation['reservation_id']}.json", reservation
            )
            destination.mkdir()
            _copy_project_tree_resuming(tree, destination)

        try:
            updated = store.publish_project_root_atomic(
                project_id,
                raw_root,
                destination_subpath,
                publish,
            )
        except Exception:  # noqa: BLE001 - migration failures preserve the legacy row for retry
            conflicts.append(project_id)
            continue
        if updated:
            migrated.append(project_id)
            managed_roots.append(relative)
            if source_identity is not None and not was_moved_with_parent:
                residue = _retain_migrated_source(
                    workspace, source, source_identity, migration_area
                )
                if residue is not None:
                    retained_residues.append(str(residue.relative_to(workspace)).replace("\\", "/"))
        else:
            conflicts.append(project_id)
    return ProjectRootMigrationReport(
        tuple(migrated), tuple(conflicts), tuple(unchanged), tuple(retained_residues)
    )


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
class WorkThreadView:
    """One thread of the owner's work, whatever started it (GAP-CHAT C18).

    Chat search covered titles and message text, which answers *"where did I say
    that"* and not *"what am I working on"*. Those are different questions: the
    second one spans conversations the owner typed **and** the threads a routine
    is advancing on its own (C11), it wants the project each sits in, and it
    wants to know which of them is blocked on the owner.

    Every field here is read from a row that already existed. This view invents
    no state; it is the join nothing was performing.
    """

    session_id: str
    title: str
    #: ``chat`` for a conversation the owner started, ``routine`` for a thread a
    #: task is advancing. The distinction is what makes "resume the thread a
    #: routine is advancing" possible at all — it used to be unreachable.
    kind: str
    updated_at: str
    turn_count: int
    #: REM-THREAD-03 — which surface owns this work: ``chat``, ``build`` or
    #: ``design``. A thread is resumed *where it was done*; offering "open in
    #: chat" for a conversation whose repository, diffs and approvals live in
    #: Build sends the owner to a surface that cannot show any of them. Read
    #: from the session row rather than guessed, and ``chat`` for a row written
    #: before sessions recorded it.
    origin: str = "chat"
    project_id: str | None = None
    project_name: str | None = None
    #: Set only on a ``routine`` thread: the task advancing it.
    task_id: str | None = None
    task_status: str | None = None
    cadence: str | None = None
    next_run_at: str | None = None
    #: What this thread is waiting on, in the owner's language, or None when it
    #: is not waiting on anything. Only ever states a blocker the runtime
    #: actually holds — never a guess about staleness.
    waiting_on: str | None = None
    # ── BUG-303: what the library needs to organise a thread ─────────────────
    #
    # These three were already stored on the session row and read only by
    # Sessions, which is the page whose job is *audit*. So the everyday library
    # controls — pin, archive, tags — lived in the evidence inspector, while the
    # page work is actually resumed from could not express any of them. Moving
    # the controls needed the index to be able to carry their state first, and
    # this is that state. Nothing new is invented: a pin, an archive flag and a
    # tag set are organizing labels that grant nothing.
    #
    # A routine thread is a task's own conversation. It is not in the owner's
    # library and cannot be pinned, archived or tagged, so it reports the
    # defaults and the interface offers it no such control.
    pinned: bool = False
    archived: bool = False
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "tags": list(self.tags)}


# ── The work index (NEW-THREAD-01) ───────────────────────────────────────────
#
# Threads derived its Project choices *and* its results from one unpaginated
# read of a hundred rows. Three things followed, and all three read as facts
# about the workspace rather than about the read:
#
# * a project whose newest thread fell outside the first hundred was **not
#   offered as a filter at all**, which is indistinguishable from a project with
#   nothing in it;
# * the window looked like the whole inventory, because nothing said otherwise;
# * typing a query called an unscoped search and hid the filters, so narrowing
#   something down silently widened it.
#
# The browser was being used as the index. These are the bounds that let the
# server be one: filter, then facet over everything that matched, then page.

#: Default rows per page, and the most a caller may ask for.
WORK_THREAD_PAGE_LIMIT = 50
WORK_THREAD_MAX_PAGE_LIMIT = 200

#: How many of the owner's threads the index will consider. Generous enough
#: that an ordinary workspace is answered completely, bounded because an index
#: that reads everything is the defect with a larger number. When it binds, the
#: answer says so rather than quietly describing a slice.
WORK_THREAD_SCAN_LIMIT = 2000


@dataclass(frozen=True)
class WorkThreadFacet:
    """One filter choice, with how many threads it would select."""

    value: str
    label: str
    count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkThreadPage:
    """One page of the work index, and the filters that produced it."""

    threads: list[WorkThreadView]
    #: Opaque, and bound to the owner and the filters. A cursor from one scope
    #: is refused in another rather than paging through a different question.
    next_cursor: str | None
    #: How many threads matched the filters, within the scan bound.
    total: int
    #: Every project the owner has work in — computed with the *project* filter
    #: lifted, so choosing a different one is possible from any page. This is
    #: the finding: a facet computed over the current page can only ever offer
    #: what is already on screen.
    projects: list[WorkThreadFacet]
    #: Same, with the *kind* filter lifted.
    kinds: list[WorkThreadFacet]
    #: BUG-303 — how many threads the *other* archive scope holds, so archiving
    #: from this page is undoable from this page. A control whose effect the
    #: owner cannot reverse on the surface they used is worse than one that has
    #: not moved, which is exactly why Archive stayed in Sessions until now.
    #:
    #: Bounded by the same scan as ``total``, and qualified by the same
    #: ``scan_truncated``: both are counts of what the index looked at.
    archived_count: int
    active_count: int
    #: True when the scan bound was reached, so the counts above describe the
    #: most recent `WORK_THREAD_SCAN_LIMIT` threads rather than all of them.
    scan_truncated: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "threads": [thread.to_dict() for thread in self.threads],
            "next_cursor": self.next_cursor,
            "total": self.total,
            "projects": [facet.to_dict() for facet in self.projects],
            "kinds": [facet.to_dict() for facet in self.kinds],
            "archived_count": self.archived_count,
            "active_count": self.active_count,
            "scan_truncated": self.scan_truncated,
        }


def _work_thread_scope(
    user_id: str | None,
    project_id: str | None,
    kind: str | None,
    query: str,
    archived: bool = False,
) -> str:
    """A short digest of the question a cursor was issued for.

    Carried inside the cursor so a cursor cannot be replayed against a different
    owner or a different filter set — paging is a position in one ordered
    answer, and the position means nothing in another.
    """
    material = "\x1f".join(
        [user_id or "", project_id or "", kind or "", query, "archived" if archived else ""]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def encode_work_thread_cursor(thread: WorkThreadView, scope: str) -> str:
    """Where the next page starts: the last row of this one, plus its scope."""
    raw = "\x1f".join([scope, thread.updated_at, thread.session_id])
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def decode_work_thread_cursor(cursor: str, scope: str) -> tuple[str, str] | None:
    """``(updated_at, session_id)`` the next page follows, or ``None``.

    ``None`` for anything that is not a cursor this scope issued — a corrupted
    string, and a valid cursor from a different filter set alike. A refused
    cursor restarts the listing rather than failing the read: the owner has
    changed the question, and the honest answer is its first page.
    """
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    parts = raw.split("\x1f")
    if len(parts) != 3 or parts[0] != scope:
        return None
    return parts[1], parts[2]


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
    # Backlog #23 — the working method this task's cycles run under: `chat` or
    # `build`. A delegating parent chooses it per child, so one brief can put
    # the reading half in Chat and the change-and-test half in Build.
    surface: str = "chat"
    # C11 — this task's own conversation, or None for a task created before
    # threads existed. The card links to it, and every cycle runs in it, so
    # "what did the overnight run find?" opens a transcript the owner can reply
    # in rather than a status line they can only read.
    thread_session_id: str | None = None
    # How many turns that thread holds. It is the difference between a link
    # worth pressing and one that opens an empty page, so the card can say so
    # instead of the owner discovering it.
    thread_turns: int = 0
    attachments: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TaskDetailView:
    """One task at its own address, with the attempts behind its status.

    BUG-299 / UX-TASK-04. The board says what a task *is* doing; this says what
    it *has* done — every cycle in order, the decision each waited on, the
    continuation that followed and the conversation it produced. It exists
    because two shipped changes promised it: a deduplicated Home row that links
    to "the canonical Tasks detail", and a stop control that can honestly report
    ``outcome_unknown`` and tell the owner to refresh to see the run's state.

    Nothing here is stored separately. The attempts are derived from the
    governed events the task's own lifecycle already writes, so this view can
    never disagree with the audit log — it *is* the audit log, grouped.
    """

    task: TaskView
    attempts: list[TaskAttemptView]
    #: Decisions still open on this task's session. A parked attempt names the
    #: one it is waiting on when the runtime recorded which; this is the queue
    #: the owner can actually act in.
    approvals: list[ApprovalView] = field(default_factory=list)
    #: True when the attempt list was cut off by the read bound, so the page
    #: says "showing the most recent" rather than implying a complete history.
    truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task.to_dict(),
            "attempts": [attempt.to_dict() for attempt in self.attempts],
            "approvals": [approval.to_dict() for approval in self.approvals],
            "truncated": self.truncated,
        }


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
    "web_extract": "Read part of a page",
    "weather_lookup": "Weather",
    "memory_search": "Search memory",
    "memory_write": "Remember",
    "knowledge_graph": "Explore graph",
    "conversation_search": "Search chats",
    "code_map_search": "Search code map",
    "code_map_references": "Find references",
    "document_symbols": "Outline file",
    "find_definition": "Find definition",
    "diagnostics": "Check for problems",
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

#: REM-THREAD-03 — what an untitled thread of each kind is called on the work
#: board. Separate from ``SESSION_LABELS`` because that table describes a node
#: on the knowledge map, and a board row and a graph node are read differently.
WORK_THREAD_ORIGIN_NOUNS: dict[str, str] = {
    "chat": "chat",
    "build": "build session",
    "design": "design session",
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


#: Providers whose availability is a fact about *this machine* — the runtime has
#: to be installed here before any surface may name a model it would serve.
LOCAL_RUNTIME_PROVIDERS: frozenset[str] = frozenset({"ollama", "llama.cpp", "mlx", "vllm"})

#: The declaration a profile carries when it is only meant to be offered once its
#: provider has been found. Shipped on every managed local slot and on the Ollama
#: native default; inert until BUG-270 gave it an enforcer.
DETECT_FIRST_STATE = "disabled_until_provider_detected"


def _names_an_available_model(
    profile: Any,
    effective_model: str,
    presence: dict[str, bool | None],
    deployed_profile_ids: frozenset[str],
) -> bool:
    """Whether a surface may name ``effective_model`` as a model this owner has.

    Three questions in order, and each one is about a different kind of absence:

    1. **Is there a model string at all?** The `<model>` placeholder means the
       owner has not chosen one. This was the whole of the old predicate.
    2. **Does the profile ask to be detected first?** Only profiles declaring
       ``disabled_until_provider_detected`` do, and they are exactly the ones
       whose model string is a promise about software on this machine — the
       Ollama native default naming a third-party model, and the managed
       llama.cpp/MLX slots naming the `local-gguf…` aliases Raiker itself
       invents when a model is deployed into a slot.
    3. **Has that promise been kept?** A saved connection or a completed
       deployment is the owner's own evidence and settles it outright. Failing
       that, the runtime must have been *detected present* — not merely
       "not known to be absent", because an unknown answer about someone else's
       machine is not a licence to claim a model they may not have.
    """
    if not effective_model or "<" in effective_model:
        return False
    if str(getattr(profile, "default_state", "")) != DETECT_FIRST_STATE:
        return True
    if profile.profile_id in deployed_profile_ids:
        return True
    return presence.get(profile.provider) is True


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
    workspace_configured: bool = False
    # Prompt-cache TTL breakpoint the provider uses for this profile ("5m"/"1h"),
    # or None when the provider/profile does not cache. Read-only status.
    prompt_cache_ttl: str | None = None
    # Context capacity and pricing are configuration-owned facts. They stay
    # unset for placeholder or provider-discovered models rather than guessed.
    context_window_tokens: int | None = None
    context_window_source: str | None = None
    # BUG-270 — "does this profile name a model that exists here". It used to be
    # `effective_model != "<model>"`, which is only "does this profile name a
    # model string at all", and that is what let a fresh install print
    # `gemma4:31b-cloud` on a host with no Ollama. A profile that declares
    # `disabled_until_provider_detected` now has to earn this: the runtime is
    # detected on this machine, or the owner has connected it or deployed into
    # it. Everything else is unchanged.
    configured: bool = False
    # Why `configured` came out the way it did, for the profiles whose answer
    # depends on this host. `True`/`False` are detection results; `None` means
    # either nothing has looked yet or the profile's availability does not
    # depend on a local runtime, and the UI says nothing in that case rather
    # than claiming an absence it has not established.
    provider_detected: bool | None = None
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
    # The image models this provider declares, default first, empty for a
    # provider that generates no images. This was read by the Design page and
    # never sent by this view, so the surface asked every profile whether it had
    # an image model and every profile answered `undefined` — the picker was
    # empty on every real install, and only looked correct in a fixture that had
    # no image provider either.
    image_models: tuple[str, ...] = ()

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
    # Backlog #16 — how much of the tool catalogue this turn carries.
    # `tools_deferred` is the count whose schemas are fetched on request rather
    # than sent every time; both are stated because "25 of 50" is the honest
    # form of a saving, and an owner should be able to see that a tool being
    # absent from a request is not a tool being withheld.
    tools_projected: int = 0
    tools_deferred: int = 0

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
    policy denials and unreachable/unsupported backends never fabricate model
    names.

    A failed listing may still carry ``models``, but only ones
    this provider published on a previous, successful call. ``remembered`` says
    which of the two happened, and ``listed_at`` when the provider last spoke, so
    a stale answer is offered as stale rather than as current. The status and
    reason code are unchanged by remembering: a provider that is unreachable is
    still reported unreachable.
    """

    profile_id: str
    provider: str
    status: str  # "available" | "policy_denied" | "unsupported" | "unavailable"
    reason_code: str | None
    models: tuple[str, ...]
    remembered: bool = False
    listed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "provider": self.provider,
            "status": self.status,
            "reason_code": self.reason_code,
            "models": list(self.models),
            "remembered": self.remembered,
            "listed_at": self.listed_at,
        }


@dataclass(frozen=True)
class ProviderCatalogueRefreshView:
    """Safe outcome for one provider in an explicit catalogue refresh."""

    profile_id: str
    provider: str
    status: str
    reason_code: str | None
    model_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ModelsView:
    profiles: tuple[ModelProfileView, ...]
    # Profiles with a concrete configured model are the only choices surfaced
    # by the conversational composer. The full list remains for Models setup.
    chat_profiles: tuple[ModelProfileView, ...]
    current_profile_id: str | None
    hosted_model_gate_state: str
    private_network_model_gate_state: str
    # What the *enforcing* path answers for these two gates right now, which is
    # not the same question as what the gate row says. A saved connection is the
    # owner's consent to use that provider (`provider_runtime_policy_from_gates`,
    # resolution 3), so a hosted provider runs with the gate row still unset.
    # Reporting only `..._state` printed "Off" directly above a connected
    # provider that had just answered — FIXED-322's defect, on a second surface.
    # `state` is untouched, so nothing that already consumes it changes meaning.
    hosted_model_gate_enforced: bool
    private_network_model_gate_enforced: bool
    model_egress_allowlist_configured: bool
    remote_profile_count: int
    ready_provider_count: int = 0
    # BUG-270 — how many models the owner actually has set up, counted where the
    # facts are. The browser used to derive this from `model != "<model>"`, which
    # counted the four empty llama.cpp slots (their `local-gguf…` aliases are
    # model strings) and the undetected Ollama default, and printed
    # "5 models set up" on a machine with none.
    usable_provider_count: int = 0
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
    # The one catalogue every composer reads, keyed by
    # profile: the last models each provider published, from the store rather
    # than from a probe, so this read stays free of the network.
    #
    # `chat_profiles` above is unchanged and still decides what a picker offers
    # *at rest*. This is what search may reach, which is the distinction
    # The rule is: curation orders the quick list, it does not
    # decide what exists.
    catalogues: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profiles": [p.to_dict() for p in self.profiles],
            "chat_profiles": [p.to_dict() for p in self.chat_profiles],
            "catalogues": {
                profile_id: list(models) for profile_id, models in self.catalogues.items()
            },
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
            "hosted_model_gate_enforced": self.hosted_model_gate_enforced,
            "private_network_model_gate_enforced": self.private_network_model_gate_enforced,
            "model_egress_allowlist_configured": self.model_egress_allowlist_configured,
            "remote_profile_count": self.remote_profile_count,
            "ready_provider_count": self.ready_provider_count,
            "usable_provider_count": self.usable_provider_count,
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
    # GCR-38 — one row per host-tick background pass: when it last succeeded,
    # when it last threw, the exception *class* it threw, and how many times in
    # a row. A pass that fails every fifteen seconds used to be invisible.
    background_workers: tuple[dict[str, Any], ...] = ()
    # GCR-45 — which file the built-in model registry was actually read from.
    # It used to depend on the working directory the host was launched from, so
    # the same install could answer differently and nothing said which one won.
    model_profile_source: dict[str, str] = field(default_factory=dict)
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
            "background_workers": [dict(worker) for worker in self.background_workers],
            "model_profile_source": dict(self.model_profile_source),
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


def _env_requirements(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """The environment variables a channel transport declares, and whether each
    is set — never what it is set to."""
    import os as _os

    out: list[dict[str, Any]] = []
    for key, required in (("requires_env", True), ("optional_env", False)):
        for entry in raw.get(key) or []:
            if not isinstance(entry, dict) or not entry.get("name"):
                continue
            name = str(entry["name"])
            out.append(
                {
                    "name": name,
                    "description": str(entry.get("description") or ""),
                    "url": entry.get("url"),
                    "secret": bool(entry.get("secret")),
                    "required": required,
                    "present": bool(_os.environ.get(name, "").strip()),
                }
            )
    return out


# GCR-43 — the service is one class assembled from one part per domain. The
# parts live in `raiker/control/dashboard_parts/` and import the views and
# helpers above, so they are imported here, after those exist and before the
# class that inherits them. The views stay in this module: they are the API's
# read contract, and every route and the contract check import them from here.
from raiker.control.dashboard_parts.approvals import ApprovalService  # noqa: E402
from raiker.control.dashboard_parts.code import CodeService  # noqa: E402
from raiker.control.dashboard_parts.execution import ExecutionService  # noqa: E402
from raiker.control.dashboard_parts.extensions import ExtensionService  # noqa: E402
from raiker.control.dashboard_parts.knowledge import KnowledgeService  # noqa: E402
from raiker.control.dashboard_parts.memory import MemoryService  # noqa: E402
from raiker.control.dashboard_parts.models import ModelService  # noqa: E402
from raiker.control.dashboard_parts.projects import ProjectService  # noqa: E402
from raiker.control.dashboard_parts.security import SecurityService  # noqa: E402
from raiker.control.dashboard_parts.sessions import SessionService  # noqa: E402
from raiker.control.dashboard_parts.tasks import TaskService  # noqa: E402


class DashboardService(
    ApprovalService,
    CodeService,
    ExecutionService,
    ExtensionService,
    KnowledgeService,
    MemoryService,
    ModelService,
    ProjectService,
    SecurityService,
    SessionService,
    TaskService,
):
    """Read-only governed views for the web UI. Reuses storage and control services; never mutates."""

    def __init__(self, workspace_root: str | Path = ".") -> None:
        self.workspace_root = Path(workspace_root)
        self.store = SQLiteStore(self.workspace_root)
        self.project_root_migration_report = migrate_project_roots(self.workspace_root, self.store)
        self.control = RuntimeControlService(self.workspace_root)

    def _is_human(self, acting_principal_id: str | None) -> bool:
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        return principal is not None and principal.principal_type == PrincipalType.HUMAN

    @staticmethod
    def _age_seconds(created_at: str) -> int | None:
        try:
            then = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

        delta = datetime.now(UTC) - then
        return max(0, int(delta.total_seconds()))


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
    "TaskAttemptView",
    "TaskDetailView",
    "TaskEventView",
    "TaskView",
    "TurnDetailView",
    "TurnView",
]
