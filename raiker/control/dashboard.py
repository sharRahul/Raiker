from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from raiker.control.service import RuntimeControlService
from raiker.models.registry import ModelProfileRegistry
from raiker.models.session_state import TERMINAL_MODEL_SESSION_ID
from raiker.runtime.authority.models import PrincipalType
from raiker.storage.sqlite import SQLiteStore

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
    selected: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ModelsView:
    profiles: tuple[ModelProfileView, ...]
    current_profile_id: str | None
    # The runtime never silently falls back to hosted providers; hosted runtime is not enabled.
    no_silent_hosted_fallback: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "profiles": [p.to_dict() for p in self.profiles],
            "current_profile_id": self.current_profile_id,
            "no_silent_hosted_fallback": self.no_silent_hosted_fallback,
        }


@dataclass(frozen=True)
class DiagnosticsView:
    runtime_mode: str
    production_ready_local_single_user_runtime: bool
    summary: dict[str, Any]
    disabled_capabilities: tuple[str, ...]
    counts: dict[str, int]
    scope_note: str = "Status reflects the local single-user runtime only."

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_mode": self.runtime_mode,
            "production_ready_local_single_user_runtime": self.production_ready_local_single_user_runtime,
            "summary": dict(self.summary),
            "disabled_capabilities": list(self.disabled_capabilities),
            "counts": dict(self.counts),
            "scope_note": self.scope_note,
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

    # ── Models / diagnostics ────────────────────────────────────────────
    def get_models(self) -> ModelsView:
        registry = ModelProfileRegistry.load()
        state = self.store.load_model_session_state(TERMINAL_MODEL_SESSION_ID)
        current = state.profile_id if state is not None else None
        profiles = tuple(
            ModelProfileView(
                profile_id=p.profile_id,
                provider=p.provider,
                model=p.model,
                default_state=p.default_state,
                local_only=p.local_only,
                requires_network=p.requires_network,
                endpoint_kind=str(p.raw.get("endpoint_kind", "unknown")),
                selected=(p.profile_id == current),
            )
            for p in registry.list_profiles()
        )
        return ModelsView(profiles=profiles, current_profile_id=current)

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
        return DiagnosticsView(
            runtime_mode=readiness.mode.mode_name,
            production_ready_local_single_user_runtime=bool(
                readiness.summary.get("production_ready_local_single_user_runtime", False)
            ),
            summary=readiness.summary,
            disabled_capabilities=disabled,
            counts=counts,
        )

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
    "AuthError",
    "AuthSessionView",
    "CheckpointView",
    "DashboardService",
    "DiagnosticsView",
    "EventView",
    "ModelProfileView",
    "ModelsView",
    "SessionDetailView",
    "SessionView",
    "TaskView",
    "TurnDetailView",
    "TurnView",
]
