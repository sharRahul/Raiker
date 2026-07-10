from __future__ import annotations

import difflib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from raiker.approval_previews import redact_secret_like_text
from raiker.control.dtos import ControlResult
from raiker.control.service import RuntimeControlService
from raiker.models.endpoint_policy import MODEL_EGRESS_ALLOWLIST_ENV
from raiker.models.policy_state import HOSTED_MODEL_GATE, PRIVATE_NETWORK_MODEL_GATE
from raiker.models.registry import ModelProfileRegistry
from raiker.models.session_state import TERMINAL_MODEL_SESSION_ID
from raiker.runtime.authority.models import PrincipalType
from raiker.runtime.authority.router import CAPABILITY_GATE_MAP
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.filesystem import FilesystemSafetyError, proposed_write_snapshot

# Capability states that mean the gate is off / fail-closed.
_DISABLED_STATES = {"disabled", "planned"}


@dataclass(frozen=True)
class SessionView:
    session_id: str
    title: str | None
    status: str
    created_at: str
    updated_at: str
    turn_count: int

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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ModelsView:
    profiles: tuple[ModelProfileView, ...]
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "profiles": [p.to_dict() for p in self.profiles],
            "current_profile_id": self.current_profile_id,
            "hosted_model_gate_state": self.hosted_model_gate_state,
            "private_network_model_gate_state": self.private_network_model_gate_state,
            "model_egress_allowlist_configured": self.model_egress_allowlist_configured,
            "remote_profile_count": self.remote_profile_count,
            "fallback_sequence": list(self.fallback_sequence),
            "no_silent_hosted_fallback": self.no_silent_hosted_fallback,
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
    # Resolving an approval records a decision; it never executes the action.
    executes_action: bool = False

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

    # ── Sessions / turns ────────────────────────────────────────────────
    def list_sessions(self, limit: int = 50) -> list[SessionView]:
        return [self._session_view(row) for row in self.store.list_sessions(limit=limit)]

    def get_session(self, session_id: str) -> SessionDetailView | None:
        row = self.store.load_session(session_id)
        if row is None:
            return None
        turns = tuple(self._turn_view(t) for t in self.store.list_turns(session_id))
        return SessionDetailView(session=self._session_view(row), turns=turns)

    def get_turn(self, turn_id: str) -> TurnDetailView | None:
        row = self.store.load_turn(turn_id)
        if row is None:
            return None
        events = tuple(
            self._event_view(e) for e in self.store.list_event_index(turn_id=turn_id, limit=500)
        )
        return TurnDetailView(turn=self._turn_view(row), events=events)

    # ── Events / checkpoints / tasks ────────────────────────────────────
    def list_events(
        self,
        session_id: str | None = None,
        turn_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[EventView]:
        rows = self.store.list_event_index(
            session_id=session_id, turn_id=turn_id, event_type=event_type, limit=limit
        )
        return [self._event_view(r) for r in rows]

    def list_checkpoints(self, session_id: str | None = None, limit: int = 50) -> list[CheckpointView]:
        return [
            self._checkpoint_view(r) for r in self.store.list_checkpoints(session_id, limit=limit)
        ]

    def get_checkpoint(self, checkpoint_id: str) -> CheckpointView | None:
        row = self.store.load_checkpoint_by_id(checkpoint_id)
        return self._checkpoint_view(row) if row is not None else None

    def list_tasks(self, session_id: str | None = None, status: str | None = None) -> list[TaskView]:
        return [self._task_view(t) for t in self.store.list_tasks(session_id=session_id, status=status)]

    # ── Approvals (read-only views; resolution lives in ApprovalInbox) ───
    def list_approvals(self, status: str = "pending") -> list[ApprovalView]:
        return [self._approval_view(row) for row in self.store.list_approvals(status=status)]

    def get_approval(self, approval_id: str) -> ApprovalDetailView | None:
        row = self.store.load_approval(approval_id)
        if row is None:
            return None
        return self._approval_detail(row)

    # ── Models / diagnostics ────────────────────────────────────────────
    def get_models(self) -> ModelsView:
        registry = ModelProfileRegistry.load()
        state = self.store.load_model_session_state(TERMINAL_MODEL_SESSION_ID)
        current = state.profile_id if state is not None else None
        hosted_gate = self.control.get_capability_gate(HOSTED_MODEL_GATE)
        private_gate = self.control.get_capability_gate(PRIVATE_NETWORK_MODEL_GATE)
        profiles = tuple(
            ModelProfileView(
                profile_id=p.profile_id,
                provider=p.provider,
                model=p.model,
                default_state=p.default_state,
                local_only=p.local_only,
                requires_network=p.requires_network,
                endpoint_kind=str(p.raw.get("endpoint_kind", "unknown")),
                requires_egress_policy=bool(p.raw.get("requires_egress_policy", False)),
                requires_budget_policy=bool(p.raw.get("requires_budget_policy", False)),
                runtime_gate=self._runtime_gate_for_profile(str(p.raw.get("endpoint_kind", "unknown"))),
                off_machine=str(p.raw.get("endpoint_kind", "unknown")) in {"remote_hosted", "private_network"},
                selected=(p.profile_id == current),
            )
            for p in registry.list_profiles()
            # Test-harness profiles (mock/deterministic) are not selectable outside
            # test mode (the provider factory fails closed), so the web surface
            # lists working backends only.
            if not bool(p.raw.get("test_only", False))
        )
        return ModelsView(
            profiles=profiles,
            current_profile_id=current,
            hosted_model_gate_state=hosted_gate.state if hosted_gate is not None else "unknown",
            private_network_model_gate_state=private_gate.state if private_gate is not None else "unknown",
            model_egress_allowlist_configured=bool(
                os.environ.get(MODEL_EGRESS_ALLOWLIST_ENV, "").strip()
            ),
            remote_profile_count=sum(1 for p in profiles if p.off_machine),
            fallback_sequence=tuple(
                self.store.load_model_fallback_sequence(TERMINAL_MODEL_SESSION_ID)
            ),
        )

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
        self.store.save_model_fallback_sequence(TERMINAL_MODEL_SESSION_ID, cleaned)
        return ControlResult(ok=True, data={"fallback_sequence": cleaned})

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
        models = self.get_models()
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
        created_at = str(row.get("created_at", ""))
        return ApprovalView(
            approval_id=str(row["approval_id"]),
            action_id=str(row.get("action_id", "")),
            status=str(row.get("status", "")),
            tool_name=tool_name,
            capability=CAPABILITY_GATE_MAP.get(tool_name, tool_name),
            risk_level=str(row.get("risk_level", "")),
            session_id=str(row.get("session_id", "")),
            turn_id=row.get("turn_id"),
            created_at=created_at,
            age_seconds=cls._age_seconds(created_at),
            requires_approval=str(row.get("status", "")) == "pending",
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
