"""Owner-facing asynchronous notification delivery (Workstream D / D2).

Approvals never block a flow: the agent parks the turn (`WAITING_FOR_APPROVAL`),
the owner is notified out-of-band, and Workstream A's relay resumes execution
once the owner approves from any surface. This package holds the delivery side —
the dashboard notification-center row plus an optional OS-level notification hook.
All copy is redacted, metadata-only (never a raw payload, token, or file content).
"""

from raiker.notify.approval_notifier import (
    fire_os_notification,
    notify_approval_pending,
    notify_critical_approval_pending,
    resolve_owner_principal_id,
)

__all__ = [
    "fire_os_notification",
    "notify_approval_pending",
    "notify_critical_approval_pending",
    "resolve_owner_principal_id",
]
