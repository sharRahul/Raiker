from __future__ import annotations

from dataclasses import dataclass

from raiker.contracts.ids import utc_now
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore


@dataclass(frozen=True)
class ApprovalResolution:
    approval_id: str
    action_id: str
    status: str
    executes_action: bool = False


class ApprovalInbox:
    def __init__(self, store: SQLiteStore, writer: EventLogWriter | None = None) -> None:
        self.store = store
        self.writer = writer

    def list_pending(self) -> list[dict[str, object]]:
        return self.store.list_approvals(status="pending")

    def resolve(
        self,
        approval_id: str,
        *,
        approve: bool,
        resolved_by: str = "local_user",
        reason: str = "",
        user_id: str | None = None,
    ) -> ApprovalResolution:
        approval = self.store.load_approval(approval_id, user_id=user_id)
        if approval is None:
            raise ValueError("approval_not_found")
        if approval["status"] != "pending":
            raise ValueError("approval_already_resolved")
        current_hash = self.store.tool_action_payload_sha256(
            str(approval["tool_name"]),
            str(approval["arguments_json"]),
            str(approval["risk_level"]),
        )
        stored_hash = approval.get("action_payload_sha256")
        if stored_hash is not None and str(stored_hash) != current_hash:
            raise ValueError("approval_payload_tampered")
        status = "approved" if approve else "denied"
        self.store.resolve_approval(
            approval_id, status=status, resolved_by=resolved_by, resolved_at=utc_now()
        )
        if self.writer is not None:
            self.writer.append(
                make_event(
                    session_id=str(approval.get("session_id", "approval_inbox")),
                    turn_id=approval.get("turn_id"),
                    event_type="approval_received" if approve else "approval_denied",
                    actor="approval_inbox",
                    payload={
                        "approval_id": approval_id,
                        "action_id": approval["action_id"],
                        "status": status,
                        "reason": reason,
                        # Resolution is metadata-only: it records a decision, never executes.
                        "executes_action": False,
                    },
                )
            )
        return ApprovalResolution(
            approval_id=approval_id,
            action_id=str(approval["action_id"]),
            status=status,
            executes_action=False,
        )
