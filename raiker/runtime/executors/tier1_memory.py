from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from raiker.memory.store import (
    MemoryForgetGovernance,
    MemoryGovernance,
    forget_memory,
    write_memory,
)
from raiker.runtime.executors.base import ExecutionResult
from raiker.storage.sqlite import SQLiteStore

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction


class MemoryWriteExecutor:
    capability = "memory_write_execution"

    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store

    def _build_governance(self, action: GovernedAction) -> MemoryGovernance:
        args = action.arguments
        return MemoryGovernance(
            source_event_id=str(args.get("source_event_id", action.action_id)),
            source_session_id=str(args.get("source_session_id", "executor")),
            source_turn_id=str(args.get("source_turn_id")) if args.get("source_turn_id") else None,
            source_type=str(args.get("source_type", "executor")),
            confidence=float(args.get("confidence", 0.75)),
            trust_score=float(args.get("trust_score", 0.75)),
            retention=str(args.get("retention", "until_forget")),
            approval_state=str(args.get("approval_state", "policy_allowed")),
            created_by=str(args.get("created_by", action.principal_id)),
        )

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        text = str(action.arguments.get("text", "")).strip()
        if not text:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="missing_argument:text",
                summary="Memory write denied: no text provided.",
            )
        try:
            governance = self._build_governance(action)
        except (ValueError, TypeError) as exc:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=f"invalid_metadata:{exc}",
                summary="Memory write denied: invalid governance metadata.",
            )
        entry = write_memory(
            text,
            workspace_root=self._workspace_root,
            scope=str(action.arguments.get("scope", "project")),
            source_event_id=governance.source_event_id,
            memory_type=str(action.arguments.get("memory_type", "project")),
            tags=tuple(action.arguments.get("tags", [])),
            source=str(action.arguments.get("source", "agent")),
            store=self._store,
            governance=governance,
            # A non-account principal (the terminal client) leaves this None so
            # write_memory falls back to the instance's original owner.
            owner_principal_id=self._store.account_scope(principal.principal_id),
        )
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary=f"Wrote memory {entry.memory_id} ({entry.sensitivity}).",
            artifacts={
                "memory_id": entry.memory_id,
                "scope": entry.scope,
                "sensitivity": entry.sensitivity,
                "retention": entry.retention,
            },
        )


class MemoryForgetExecutor:
    capability = "memory_forget_execution"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        memory_id = str(action.arguments.get("memory_id", "")).strip()
        if not memory_id:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="missing_argument:memory_id",
                summary="Memory forget denied: no memory_id provided.",
            )
        governance = MemoryForgetGovernance(
            source_event_id=str(action.arguments.get("source_event_id", action.action_id)),
            source_session_id=str(action.arguments.get("source_session_id", "executor")),
            source_turn_id=str(action.arguments.get("source_turn_id")) if action.arguments.get("source_turn_id") else None,
            source_type=str(action.arguments.get("source_type", "executor")),
            deleted_by=str(action.arguments.get("deleted_by", action.principal_id)),
        )
        store = SQLiteStore(self._workspace_root)
        found = forget_memory(
            memory_id,
            workspace_root=self._workspace_root,
            store=store,
            governance=governance,
            owner_principal_id=store.account_scope(principal.principal_id),
        )
        if not found:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="memory_not_found",
                summary=f"Memory {memory_id} not found.",
            )
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary=f"Forgot memory {memory_id}.",
            artifacts={"memory_id": memory_id},
        )
