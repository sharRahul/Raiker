"""Read-only summary models for the Raiker web workbench (plan phases 3 and 4).

Every model in this module is *derived from stored state only*. Nothing here
mutates the runtime, reaches the network, reads a credential value, or returns
workspace file content. The web application needs honest aggregates so it can
answer four questions without inventing them in the browser:

* Which extensions are installed, connected, runtime-enabled, and actually
  usable — as four independent facts rather than one optimistic badge.
* What a checkpoint restore would touch *before* anyone asks for one.
* Which files a project owns, and which governed turn last wrote each of them.
* Is the runtime ready, is anything waiting, and what changed — with a
  copyable, redacted support bundle when the owner needs to share it.

The browser must never derive these from metadata alone, so they live here and
are served read-only.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from datetime import UTC
from pathlib import Path
from typing import Any

from raiker.api.redaction import redact_response_body
from raiker.checkpoints.service import CheckpointService
from raiker.contracts.ids import utc_now
from raiker.control.dashboard import DashboardService
from raiker.runtime.connector_ecosystem import (
    ConnectorCatalog,
    ConnectorVault,
    credential_status,
)
from raiker.storage.sqlite import SQLiteStore

# Directory names that are runtime plumbing rather than project work. They are
# skipped by the project file explorer so the listing reads as the owner's
# files, not Raiker's bookkeeping.
_SKIPPED_DIRECTORIES = frozenset(
    {".git", ".raiker", "__pycache__", "node_modules", ".venv", ".mypy_cache", ".pytest_cache"}
)

# Hard ceilings. The explorer is a navigation aid, not a filesystem crawler:
# it stops early and says so rather than walking an unbounded tree.
_MAX_FILES = 500
_MAX_DEPTH = 6

# Deferred surfaces. They are listed so the interface can say "not yet
# available" in the same place the owner looks for extensions, instead of
# hiding them and letting the gap read as an oversight.
_DEFERRED_EXTENSION_KINDS: tuple[dict[str, str], ...] = (
    {
        "kind": "plugin",
        "status": "not_available",
        "detail": (
            "Plugin-provided panels need a route, permission, and accessibility "
            "contract before any plugin may render in this application."
        ),
    },
    {
        "kind": "channel",
        "status": "not_available",
        "detail": (
            "Channels and webhooks need an accepted delivery contract and threat "
            "model before Raiker offers controls for them."
        ),
    },
)


@dataclass(frozen=True)
class ExtensionView:
    """One extension's lifecycle as four independent, server-derived facts.

    ``installed``, ``connected``, ``enabled``, and ``usable`` are deliberately
    separate: a connector can be installed without an account, connected without
    being enabled for the session, and enabled while still unusable because its
    capability gate is off or its host is not on the egress allowlist.
    ``blocked_reason`` names the first unmet condition so the interface never has
    to guess why something is unavailable.
    """

    extension_id: str
    kind: str
    display_name: str
    category: str
    installed: bool
    connected: bool
    enabled: bool
    usable: bool
    blocked_reason: str | None
    detail: str
    # Optional governance facts. Present for connectors bound to a capability
    # gate; ``None`` where the concept does not apply to this extension kind.
    capability: str | None = None
    gate_state: str | None = None
    decision_mode: str | None = None
    egress_host: str | None = None
    egress_allowed: bool | None = None
    # MCP transport/containment facts. ``monitor_state`` is the circuit breaker:
    # ``active`` | ``paused`` | ``killed``.
    transport: str | None = None
    monitor_state: str | None = None
    tool_count: int = 0
    last_activity_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExtensionsOverviewView:
    extensions: tuple[ExtensionView, ...]
    counts: dict[str, int]
    vault_configured: bool
    connector_egress_allowlist_configured: bool
    deferred: tuple[dict[str, str], ...] = _DEFERRED_EXTENSION_KINDS

    def to_dict(self) -> dict[str, Any]:
        return {
            "extensions": [e.to_dict() for e in self.extensions],
            "counts": dict(self.counts),
            "vault_configured": self.vault_configured,
            "connector_egress_allowlist_configured": self.connector_egress_allowlist_configured,
            "deferred": [dict(d) for d in self.deferred],
        }


@dataclass(frozen=True)
class ProjectFileView:
    """Metadata for one project file. Never carries file content."""

    workspace_path: str
    name: str
    is_directory: bool
    size_bytes: int
    modified_at: str
    depth: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FileProvenanceEntryView:
    """One governed write that touched a file, as recorded by checkpoint capture.

    Content addresses and sizes only — the pre-image bytes are never returned.
    ``turn_id`` and ``action_id`` let the interface link back to the turn and the
    approval that produced the change.
    """

    turn_id: str | None
    action_id: str | None
    session_id: str
    capability: str
    principal_id: str
    capture_status: str
    existed_before: bool
    pre_image_size: int
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProjectFilesView:
    project_id: str
    root_subpath: str
    root_exists: bool
    files: tuple[ProjectFileView, ...]
    truncated: bool
    provenance: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    note: str = (
        "Metadata only. Raiker never serves workspace file content to the browser; "
        "changes are made through the governed approval path."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "root_subpath": self.root_subpath,
            "root_exists": self.root_exists,
            "files": [f.to_dict() for f in self.files],
            "truncated": self.truncated,
            "provenance": {k: list(v) for k, v in self.provenance.items()},
            "note": self.note,
        }


class WebReadModels:
    """Read-only aggregates for the web workbench.

    Constructed per request, like ``DashboardService``. Holding no state keeps
    every read a fresh view of the store rather than a cached claim.
    """

    def __init__(self, workspace_root: str | Path) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.store = SQLiteStore(self.workspace_root)
        self.dashboard = DashboardService(self.workspace_root)

    # ── Extensions ───────────────────────────────────────────────────────
    def extensions_overview(
        self, *, acting_principal_id: str, user_id: str | None = None
    ) -> ExtensionsOverviewView:
        """Aggregate connectors and MCP servers into one lifecycle view."""
        del user_id  # MCP profiles are already scoped to the acting principal.
        extensions: list[ExtensionView] = [
            *self._connector_extensions(acting_principal_id),
            *self._mcp_extensions(acting_principal_id),
        ]
        counts = {
            "total": len(extensions),
            "installed": sum(1 for e in extensions if e.installed),
            "connected": sum(1 for e in extensions if e.connected),
            "enabled": sum(1 for e in extensions if e.enabled),
            "usable": sum(1 for e in extensions if e.usable),
        }
        return ExtensionsOverviewView(
            extensions=tuple(extensions),
            counts=counts,
            vault_configured=ConnectorVault(self.store).configured(),
            connector_egress_allowlist_configured=bool(
                os.environ.get("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", "").strip()
            ),
        )

    def _connector_extensions(self, acting_principal_id: str) -> list[ExtensionView]:
        # Governed connector facts (gate, decision mode, egress) are keyed by the
        # capability-bound connector id; catalog entries are keyed by store id.
        # Where both exist for the same connector they are merged, so the owner
        # sees one row per connector rather than two half-truths.
        governed = {
            c.connector_id: c
            for c in self.dashboard.get_connections(acting_principal_id).connectors
        }
        rows: list[ExtensionView] = []
        for definition in ConnectorCatalog().list():
            connector_id = definition.connector_id
            installation = self._connector_installation(acting_principal_id, connector_id)
            credential = self._connector_credential(acting_principal_id, connector_id)
            auth_status = (
                credential_status(credential.get("expires_at")) if credential else "not_connected"
            )
            gate = governed.get(connector_id)
            installed = installation is not None
            connected = auth_status == "connected"
            enabled = bool(installation and installation.get("enabled"))
            gate_open = gate is None or (gate.capability_enabled and gate.decision_mode != "deny")
            egress_ok = gate is None or gate.egress_allowed
            usable = installed and connected and enabled and gate_open and egress_ok
            rows.append(
                ExtensionView(
                    extension_id=f"connector:{connector_id}",
                    kind="connector",
                    display_name=definition.name,
                    category=definition.category,
                    installed=installed,
                    connected=connected,
                    enabled=enabled,
                    usable=usable,
                    blocked_reason=_connector_block_reason(
                        installed=installed,
                        connected=connected,
                        enabled=enabled,
                        auth_status=auth_status,
                        gate_open=gate_open,
                        egress_ok=egress_ok,
                        gate_state=gate.gate_state if gate else None,
                        decision_mode=gate.decision_mode if gate else None,
                    ),
                    detail=definition.description,
                    capability=gate.capability if gate else None,
                    gate_state=gate.gate_state if gate else None,
                    decision_mode=gate.decision_mode if gate else None,
                    egress_host=gate.egress_host if gate else definition.host,
                    egress_allowed=gate.egress_allowed if gate else None,
                    last_activity_at=self._connector_last_invocation(
                        acting_principal_id, connector_id
                    ),
                )
            )
        # Governed connectors with no catalog entry still belong in the hub: they
        # are real capabilities the owner can be blocked on.
        for connector_id, gate in governed.items():
            if any(row.extension_id == f"connector:{connector_id}" for row in rows):
                continue
            gate_open = gate.capability_enabled and gate.decision_mode != "deny"
            usable = gate.credential_configured and gate_open and gate.egress_allowed
            rows.append(
                ExtensionView(
                    extension_id=f"connector:{connector_id}",
                    kind="connector",
                    display_name=gate.display_name,
                    category="Governed connector",
                    installed=True,
                    connected=gate.credential_configured,
                    enabled=gate.capability_enabled,
                    usable=usable,
                    blocked_reason=_connector_block_reason(
                        installed=True,
                        connected=gate.credential_configured,
                        # A governed connector with no catalog entry has no
                        # per-session installation to enable, so the gate — not a
                        # session switch — is what can block it.
                        enabled=True,
                        auth_status="connected" if gate.credential_configured else "not_connected",
                        gate_open=gate_open,
                        egress_ok=gate.egress_allowed,
                        gate_state=gate.gate_state,
                        decision_mode=gate.decision_mode,
                    ),
                    detail=f"Actions: {', '.join(gate.actions) or 'none registered'}",
                    capability=gate.capability,
                    gate_state=gate.gate_state,
                    decision_mode=gate.decision_mode,
                    egress_host=gate.egress_host,
                    egress_allowed=gate.egress_allowed,
                )
            )
        return sorted(rows, key=lambda row: row.display_name.lower())

    def _mcp_extensions(self, acting_principal_id: str) -> list[ExtensionView]:
        rows: list[ExtensionView] = []
        for server in self.dashboard.list_mcp_servers(acting_principal_id):
            connected = server.status == "connected"
            enabled = server.monitor_state == "active"
            usable = connected and enabled
            rows.append(
                ExtensionView(
                    extension_id=f"mcp:{server.server_id}",
                    kind="mcp_server",
                    display_name=server.name,
                    category="MCP server",
                    installed=True,
                    connected=connected,
                    enabled=enabled,
                    usable=usable,
                    blocked_reason=_mcp_block_reason(
                        status=server.status, monitor_state=server.monitor_state
                    ),
                    detail=(
                        f"{server.transport} transport · "
                        f"{server.tool_count} tool{'' if server.tool_count == 1 else 's'} discovered"
                    ),
                    transport=server.transport,
                    monitor_state=server.monitor_state,
                    tool_count=server.tool_count,
                    last_activity_at=server.last_connected_at,
                )
            )
        return sorted(rows, key=lambda row: row.display_name.lower())

    def _connector_installation(self, principal_id: str, connector_id: str) -> dict[str, Any] | None:
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT * FROM connector_installations WHERE principal_id=? AND connector_id=?",
                (principal_id, connector_id),
            ).fetchone()
        return dict(row) if row else None

    def _connector_credential(self, principal_id: str, connector_id: str) -> dict[str, Any] | None:
        # Expiry/updated timestamps only — the credential value is never read.
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT expires_at, updated_at FROM connector_credentials "
                "WHERE principal_id=? AND connector_id=?",
                (principal_id, connector_id),
            ).fetchone()
        return dict(row) if row else None

    def _connector_last_invocation(self, principal_id: str, connector_id: str) -> str | None:
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT started_at FROM connector_invocations "
                "WHERE principal_id=? AND connector_id=? ORDER BY started_at DESC LIMIT 1",
                (principal_id, connector_id),
            ).fetchone()
        return str(row["started_at"]) if row else None

    # ── Checkpoint restore preflight ─────────────────────────────────────
    def checkpoint_restore_plan(
        self, checkpoint_id: str, *, principal_id: str, user_id: str | None = None
    ) -> dict[str, Any] | None:
        """Metadata-only preflight for restoring to a checkpoint.

        Returns ``None`` when the checkpoint does not exist or does not belong to
        this owner. Computing a plan changes nothing: it reports which files a
        restore would rewrite, delete, or skip, and whether any of them were last
        changed by a different principal. Executing the restore still goes
        through the governed approval path.
        """
        if self.dashboard.get_checkpoint(checkpoint_id, user_id) is None:
            return None
        plan = CheckpointService(self.store).compute_restore_plan(
            checkpoint_id, restoring_principal_id=principal_id
        )
        return dict(plan)

    # ── Conversation branching (GAP-CHAT C14 — branch from here) ─────────
    # A branch is the *opposite* of a restore, and the distinction is why they are
    # separate endpoints rather than two modes of one. A restore rewrites the
    # workspace and is therefore an approval-gated governed mutation. A branch
    # writes no workspace file at all: it creates a second conversation seeded from
    # the checkpoint's own state summary and memory candidates, and leaves the
    # first one exactly as it was. Nothing about the original conversation is
    # rewritten, which is the property that made "edit and resend" safe to ship
    # and "replace the message and discard what followed" not.

    def conversation_branch_plan(
        self, checkpoint_id: str, *, user_id: str | None = None
    ) -> dict[str, Any] | None:
        """What branching from this checkpoint would seed, without doing it.

        ``None`` when the checkpoint does not exist or belongs to another owner.
        """
        if self.dashboard.get_checkpoint(checkpoint_id, user_id) is None:
            return None
        try:
            return dict(CheckpointService(self.store).plan_fork(checkpoint_id))
        except ValueError:
            return None

    def branch_conversation(
        self, checkpoint_id: str, *, title: str | None = None, user_id: str | None = None
    ) -> dict[str, Any] | None:
        """Materialise the branch, owned by the same user as the source.

        The new session is created with the *source owner's* ``user_id``, so a
        branch can never widen who can read a conversation. ``None`` when the
        checkpoint does not exist or belongs to another owner.
        """
        checkpoint = self.dashboard.get_checkpoint(checkpoint_id, user_id)
        if checkpoint is None:
            return None
        source = self.store.load_session(checkpoint.session_id)
        owner = str(source.get("user_id")) if source and source.get("user_id") else user_id
        try:
            return dict(
                CheckpointService(self.store).execute_fork(
                    checkpoint_id, title=title, user_id=owner
                )
            )
        except ValueError:
            return None

    def conversation_branch_origin(
        self, session_id: str, *, user_id: str | None = None
    ) -> dict[str, Any] | None:
        """Where a branched conversation came from, or ``None`` when it is a root.

        The lineage is what makes two branches of one conversation legible: the
        branch says which conversation and which checkpoint it grew from, and the
        summary it was seeded with.
        """
        session = self.store.load_session(session_id)
        if session is None or (user_id is not None and session.get("user_id") != user_id):
            return None
        seed = CheckpointService(self.store).load_fork_seed(session_id)
        if seed is None:
            return None
        source_id = str(seed.get("source_session_id") or "")
        source = self.store.load_session(source_id) if source_id else None
        return {
            "session_id": session_id,
            "source_session_id": source_id,
            "source_title": (str(source.get("title")) if source and source.get("title") else None),
            "forked_from_checkpoint_id": str(seed.get("forked_from_checkpoint_id") or ""),
            "summary": str(seed.get("summary") or ""),
            "created_at": str(seed.get("created_at") or ""),
        }

    # ── Project files ────────────────────────────────────────────────────
    def project_files(
        self, project_id: str, *, user_id: str | None = None
    ) -> ProjectFilesView | None:
        """List a project's files as metadata plus governed-write provenance."""
        row = self.store.load_project(project_id, user_id)
        if row is None:
            return None
        root_subpath = str(row.get("root_subpath") or "")
        root = self._contained_path(root_subpath)
        if root is None or not root.is_dir():
            return ProjectFilesView(
                project_id=project_id,
                root_subpath=root_subpath,
                root_exists=False,
                files=(),
                truncated=False,
            )
        files, truncated = self._walk(root)
        return ProjectFilesView(
            project_id=project_id,
            root_subpath=root_subpath,
            root_exists=True,
            files=files,
            truncated=truncated,
            provenance=self._provenance_for(project_id, {f.workspace_path for f in files}),
        )

    def _contained_path(self, subpath: str) -> Path | None:
        """Resolve a workspace-relative path, refusing anything that escapes.

        Fail closed: a path that resolves outside the workspace root — through
        ``..``, an absolute component, or a symlink — returns ``None`` rather
        than a path the caller might read.
        """
        if subpath.strip() == "":
            return None
        candidate = (self.workspace_root / subpath).resolve()
        if candidate != self.workspace_root and self.workspace_root not in candidate.parents:
            return None
        return candidate

    def _walk(self, root: Path) -> tuple[tuple[ProjectFileView, ...], bool]:
        entries: list[ProjectFileView] = []
        truncated = False
        stack: list[tuple[Path, int]] = [(root, 0)]
        while stack:
            directory, depth = stack.pop(0)
            if depth > _MAX_DEPTH:
                truncated = True
                continue
            try:
                children = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
            except OSError:
                continue
            for child in children:
                if child.name in _SKIPPED_DIRECTORIES or child.is_symlink():
                    continue
                if len(entries) >= _MAX_FILES:
                    return tuple(entries), True
                try:
                    stat = child.stat()
                except OSError:
                    continue
                is_directory = child.is_dir()
                entries.append(
                    ProjectFileView(
                        workspace_path=child.relative_to(self.workspace_root).as_posix(),
                        name=child.name,
                        is_directory=is_directory,
                        size_bytes=0 if is_directory else int(stat.st_size),
                        modified_at=_iso_from_timestamp(stat.st_mtime),
                        depth=depth,
                    )
                )
                if is_directory:
                    stack.append((child, depth + 1))
        return tuple(entries), truncated

    def _provenance_for(
        self, project_id: str, known_paths: set[str]
    ) -> dict[str, list[dict[str, Any]]]:
        """Map each listed file to the governed writes recorded against it."""
        provenance: dict[str, list[dict[str, Any]]] = {}
        sessions = self.store.list_sessions(limit=200, project_id=project_id)
        for session in sessions:
            entries = self.store.list_checkpoint_capture_entries(
                session_id=str(session["session_id"]), limit=500
            )
            for entry in entries:
                path = str(entry["workspace_path"])
                if path not in known_paths:
                    continue
                provenance.setdefault(path, []).append(
                    FileProvenanceEntryView(
                        turn_id=entry.get("turn_id"),
                        action_id=entry.get("action_id"),
                        session_id=str(entry["session_id"]),
                        capability=str(entry.get("capability") or ""),
                        principal_id=str(entry.get("principal_id") or ""),
                        capture_status=str(entry.get("capture_status") or ""),
                        existed_before=bool(entry.get("existed_before")),
                        pre_image_size=int(entry.get("pre_image_size") or 0),
                        created_at=str(entry.get("created_at") or ""),
                    ).to_dict()
                )
        for path in provenance:
            provenance[path].sort(key=lambda item: str(item["created_at"]), reverse=True)
            del provenance[path][8:]
        return provenance

    # ── Redacted support bundle ──────────────────────────────────────────
    def diagnostics_export(self, *, acting_principal_id: str) -> dict[str, Any]:
        """A copyable support bundle of the runtime's own readiness facts.

        The bundle is assembled from existing read models and then passed through
        the same redactor the API applies to every response, so a bundle the
        owner pastes into an issue cannot carry a secret out of the workspace.
        """
        diagnostics = self.dashboard.get_diagnostics(acting_principal_id).to_dict()
        readiness = self.dashboard.control.get_runtime_readiness(acting_principal_id)
        bundle = {
            "generated_at": utc_now(),
            "scope": "local single-user runtime",
            "runtime_mode": diagnostics.get("runtime_mode"),
            "production_ready_local_single_user_runtime": diagnostics.get(
                "production_ready_local_single_user_runtime"
            ),
            "counts": diagnostics.get("counts", {}),
            "missing_config": diagnostics.get("missing_config", []),
            "disabled_capabilities": diagnostics.get("disabled_capabilities", []),
            "readiness": diagnostics.get("readiness", {}),
            "provider_health": [
                {k: v for k, v in provider.items() if k != "detail"}
                for provider in diagnostics.get("provider_health", [])
            ],
            "gates": [
                {
                    "capability": gate.capability,
                    "state": gate.state,
                    "decision_mode": gate.decision_mode,
                    "runtime_enabled": gate.runtime_enabled,
                }
                for gate in readiness.gates
            ],
            "note": (
                "Redacted diagnostic summary. Contains no credential, token, prompt, "
                "file content, or workspace path outside the runtime's own state."
            ),
        }
        redacted: dict[str, Any] = redact_response_body(bundle)
        return redacted


# Gate states that are "on" but below the runtime level a governed call needs.
# A surface blocked here is *not* blocked by an off switch: the owner has
# already enabled the capability, and turning it on again — which is what
# "the gate is closed" tells them to do — changes nothing. Reaching
# `enabled_runtime` additionally requires an active runtime-enablement mode
# (Settings → Runtime mode). BUG-11.
_ENABLED_BELOW_RUNTIME_STATES = frozenset({"enabled_read_only", "enabled_policy_gated"})


def _connector_block_reason(
    *,
    installed: bool,
    connected: bool,
    enabled: bool,
    auth_status: str,
    gate_open: bool,
    egress_ok: bool,
    gate_state: str | None = None,
    decision_mode: str | None = None,
) -> str | None:
    """Name the first unmet condition, in the order the owner must fix them."""
    if not installed:
        return "not_installed"
    if auth_status == "reauth_required":
        return "reauthentication_required"
    if not connected:
        return "account_not_connected"
    if not enabled:
        return "not_enabled_for_session"
    if not gate_open:
        if decision_mode == "deny":
            return "capability_decision_mode_deny"
        if (gate_state or "") in _ENABLED_BELOW_RUNTIME_STATES:
            return "capability_below_runtime_level"
        return "capability_gate_closed"
    if not egress_ok:
        return "egress_host_not_allowlisted"
    return None


def _mcp_block_reason(*, status: str, monitor_state: str) -> str | None:
    if monitor_state == "killed":
        return "connection_killed"
    if monitor_state == "paused":
        return "circuit_breaker_paused"
    if status != "connected":
        return "not_connected"
    return None


def _iso_from_timestamp(timestamp: float) -> str:
    from datetime import datetime

    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat(timespec="seconds")


__all__ = [
    "ExtensionView",
    "ExtensionsOverviewView",
    "FileProvenanceEntryView",
    "ProjectFileView",
    "ProjectFilesView",
    "WebReadModels",
]
