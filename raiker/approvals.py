from __future__ import annotations

from dataclasses import dataclass

from raiker.contracts.ids import utc_now
from raiker.storage.sqlite import SQLiteStore


@dataclass(frozen=True)
class ApprovalResolution:
    approval_id: str
    action_id: str
    status: str


class ApprovalInbox:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def list_pending(self) -> list[dict[str, object]]:
        return self.store.list_approvals(status="pending")

    def resolve(self, approval_id: str, *, approve: bool, resolved_by: str = "local_user") -> ApprovalResolution:
        approval = self.store.load_approval(approval_id)
        if approval is None:
            raise ValueError("approval_not_found")
        if approval["status"] != "pending":
            raise ValueError("approval_already_resolved")
        status = "approved" if approve else "denied"
        self.store.resolve_approval(approval_id, status=status, resolved_by=resolved_by, resolved_at=utc_now())
        return ApprovalResolution(approval_id=approval_id, action_id=str(approval["action_id"]), status=status)
