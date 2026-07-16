from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from raiker.contracts.models import ClientMetadata, PolicyDecision, ToolAction
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.memory.policy import MemorySensitivity, classify_memory_sensitivity
from raiker.memory.review import MemoryReviewQueue
from raiker.memory.store import (
    MemoryForgetGovernance,
    MemoryGovernance,
    forget_memory,
    get_memory,
    write_memory,
)
from raiker.storage.sqlite import SQLiteStore


@dataclass(frozen=True)
class GovernedMemoryResult:
    status: str
    payload: dict[str, Any]


class GovernedMemoryService:
    def __init__(
        self,
        workspace_root: str | Path,
        *,
        store: SQLiteStore | None = None,
        writer: EventLogWriter | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.store = store or SQLiteStore(self.workspace_root)
        self.writer = writer

    @staticmethod
    def _required_float(arguments: dict[str, Any], key: str, default: float) -> float:
        value = arguments.get(key, default)
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid_memory_metadata:{key}") from exc

    @staticmethod
    def _required_str(arguments: dict[str, Any], key: str, default: str) -> str:
        value = str(arguments.get(key, default)).strip()
        if not value:
            raise ValueError(f"missing_memory_metadata:{key}")
        return value

    def _append_event(
        self,
        *,
        session_id: str,
        turn_id: str | None,
        event_type: str,
        payload: dict[str, Any],
        client: ClientMetadata | None,
    ) -> None:
        if self.writer is None:
            return
        self.writer.append(
            make_event(
                session_id=session_id,
                turn_id=turn_id,
                event_type=event_type,
                actor="memory_governance",
                payload=payload,
                client=client,
            )
        )

    def _build_governance(
        self,
        action: ToolAction,
        *,
        session_id: str,
        turn_id: str | None,
    ) -> MemoryGovernance:
        return MemoryGovernance(
            source_event_id=self._required_str(action.arguments, "source_event_id", action.action_id),
            source_session_id=self._required_str(
                action.arguments, "source_session_id", session_id
            ),
            source_turn_id=str(action.arguments.get("source_turn_id", turn_id))
            if turn_id is not None or action.arguments.get("source_turn_id") is not None
            else None,
            source_type=self._required_str(
                action.arguments, "source_type", action.proposed_by
            ),
            confidence=self._required_float(action.arguments, "confidence", 0.75),
            trust_score=self._required_float(action.arguments, "trust_score", 0.75),
            retention=self._required_str(action.arguments, "retention", "until_forget"),
            approval_state=self._required_str(
                action.arguments, "approval_state", "policy_allowed"
            ),
            created_by=self._required_str(action.arguments, "created_by", action.proposed_by),
        )

    def _build_forget_governance(
        self,
        action: ToolAction,
        *,
        session_id: str,
        turn_id: str | None,
    ) -> MemoryForgetGovernance:
        return MemoryForgetGovernance(
            source_event_id=self._required_str(action.arguments, "source_event_id", action.action_id),
            source_session_id=self._required_str(
                action.arguments, "source_session_id", session_id
            ),
            source_turn_id=str(action.arguments.get("source_turn_id", turn_id))
            if turn_id is not None or action.arguments.get("source_turn_id") is not None
            else None,
            source_type=self._required_str(
                action.arguments, "source_type", action.proposed_by
            ),
            deleted_by=self._required_str(action.arguments, "deleted_by", action.proposed_by),
        )

    def write_from_action(
        self,
        action: ToolAction,
        decision: PolicyDecision,
        *,
        session_id: str,
        turn_id: str | None,
        client: ClientMetadata | None,
        owner_principal_id: str | None = None,
    ) -> dict[str, Any]:
        if decision.decision != "allow":
            return {
                "status": "failed",
                "error": {
                    "type": "policy_bypass_denied",
                    "reason": "memory_write_requires_allow_decision",
                },
            }
        text = str(action.arguments.get("text", ""))
        if not text.strip():
            return {
                "status": "failed",
                "error": {"type": "empty_text", "message": "Cannot write empty memory."},
            }
        sensitivity = classify_memory_sensitivity(text)
        if sensitivity in {MemorySensitivity.CREDENTIAL_LIKE, MemorySensitivity.SECRET_LIKE}:
            return {
                "status": "denied",
                "error": {
                    "type": "policy_denied",
                    "reason": "secret_or_credential_like_memory_blocked",
                    "sensitivity": sensitivity.value,
                },
            }
        try:
            governance = self._build_governance(action, session_id=session_id, turn_id=turn_id)
        except ValueError as exc:
            return {"status": "failed", "error": {"type": str(exc)}}
        entry = write_memory(
            text,
            workspace_root=self.workspace_root,
            scope=str(action.arguments.get("scope", "project")),
            source_event_id=governance.source_event_id,
            memory_type=str(action.arguments.get("memory_type", "project")),
            tags=tuple(action.arguments.get("tags", [])),
            source=str(action.arguments.get("source", "agent")),
            store=self.store,
            governance=governance,
            owner_principal_id=owner_principal_id or action.proposed_by,
        )
        self._append_event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="memory_record_created",
            payload={
                "action_id": action.action_id,
                "memory_id": entry.memory_id,
                "scope": entry.scope,
                "sensitivity": entry.sensitivity,
                "retention": entry.retention,
                "approval_state": entry.approval_state,
                "source_event_id": entry.source_event_id,
            },
            client=client,
        )
        return {
            "status": "success",
            "memory_id": entry.memory_id,
            "scope": entry.scope,
            "sensitivity": entry.sensitivity,
            "created_at": entry.created_at,
            "approval_state": entry.approval_state,
            "retention": entry.retention,
            "confidence": entry.confidence,
            "trust_score": entry.trust_score,
            "provenance": entry.provenance,
        }

    def forget_from_action(
        self,
        action: ToolAction,
        decision: PolicyDecision,
        *,
        session_id: str,
        turn_id: str | None,
        client: ClientMetadata | None,
        owner_principal_id: str | None = None,
    ) -> dict[str, Any]:
        if decision.decision != "allow":
            return {
                "status": "failed",
                "error": {
                    "type": "policy_bypass_denied",
                    "reason": "memory_forget_requires_allow_decision",
                },
            }
        memory_id = str(action.arguments.get("memory_id", "")).strip()
        if not memory_id:
            return {
                "status": "failed",
                "error": {
                    "type": "missing_memory_id",
                    "message": "memory_id is required.",
                },
            }
        existing = get_memory(
            memory_id, workspace_root=self.workspace_root,
            owner_principal_id=owner_principal_id or action.proposed_by,
        )
        try:
            governance = self._build_forget_governance(
                action, session_id=session_id, turn_id=turn_id
            )
        except ValueError as exc:
            return {"status": "failed", "error": {"type": str(exc)}}
        found = forget_memory(
            memory_id,
            workspace_root=self.workspace_root,
            store=self.store,
            governance=governance,
            owner_principal_id=owner_principal_id or action.proposed_by,
        )
        if not found:
            return {
                "status": "failed",
                "error": {
                    "type": "not_found",
                    "message": f"Memory '{memory_id}' not found.",
                },
            }
        self._append_event(
            session_id=session_id,
            turn_id=turn_id,
            event_type="memory_record_forgotten",
            payload={
                "action_id": action.action_id,
                "memory_id": memory_id,
                "scope": existing.scope if existing is not None else "unknown",
                "source_event_id": governance.source_event_id,
            },
            client=client,
        )
        return {"status": "success", "memory_id": memory_id}


def memory_governance_summary(workspace_root: str | Path = ".") -> dict[str, object]:
    return MemoryReviewQueue(workspace_root).export_summary()
