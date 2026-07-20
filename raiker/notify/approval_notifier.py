"""Asynchronous approval notifications (Workstream D / D2, ZT policy).

When an AI-proposed action is parked for human approval, the owner is notified
asynchronously so the flow never blocks:

1. a **dashboard notification-center** row (the existing owner-scoped
   ``notifications`` table — surfaced by ``GET /api/notifications``);
2. an optional **OS-level notification hook** — a best-effort, env-gated shell-out
   the owner configures via ``RAIKER_OS_NOTIFY_CMD``. It is off by default, runs
   fully isolated (a failure never touches the approval path), and is passed only
   redacted, metadata-only copy.

This is the single highest-impact friction reducer: the user approves from any
surface, and Workstream A's relay resumes execution with execution-time
re-verification.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

# Environment variable the owner sets to receive OS-level notifications. The
# command receives the title as ``$1`` and the body as ``$2`` (safely quoted).
OS_NOTIFY_ENV = "RAIKER_OS_NOTIFY_CMD"

# Notification kind for the dashboard notification center.
APPROVAL_PENDING_KIND = "approval_pending"


def resolve_owner_principal_id(
    store: SQLiteStore, acting_principal_id: str | None
) -> str | None:
    """Resolve the human owner who should receive the notification.

    If the acting principal is itself an account (a human acting directly), that
    is the owner. Otherwise — the common case of an AI/automation principal — the
    notification goes to the instance's original owner account. Returns ``None``
    when no account exists yet (bootstrap), in which case notification is skipped.
    """
    if acting_principal_id:
        scoped = store.account_scope(acting_principal_id)
        if scoped is not None:
            return scoped
    return store.original_account_principal_id()


def fire_os_notification(title: str, body: str) -> bool:
    """Best-effort OS-level notification via the owner-configured hook.

    Returns True only if the configured command was launched. Off (returns False)
    when ``RAIKER_OS_NOTIFY_CMD`` is unset. Never raises — a hook failure must not
    affect the approval flow.
    """
    command = os.environ.get(OS_NOTIFY_ENV, "").strip()
    if not command:
        return False
    try:
        argv = shlex.split(command) + [title, body]
        subprocess.run(  # noqa: S603 - owner-configured command, redacted args only
            argv,
            check=False,
            capture_output=True,
            timeout=5,
        )
        return True
    except Exception:
        return False


def notify_approval_pending(
    store: SQLiteStore,
    *,
    acting_principal_id: str | None,
    approval_id: str,
    tool_name: str,
    risk_level: str = "",
) -> str | None:
    """Notify the owner that an approval is waiting (dashboard + OS hook).

    Returns the created notification id, or ``None`` when there is no owner
    account to notify (bootstrap) — in which case delivery is silently skipped.
    Copy is metadata-only: the tool name and risk, never the arguments.
    """
    owner_principal_id = resolve_owner_principal_id(store, acting_principal_id)
    if owner_principal_id is None:
        return None
    risk_suffix = f" ({risk_level} risk)" if risk_level else ""
    title = "Approval needed"
    body = (
        f"Raiker is waiting for your approval to run '{tool_name}'{risk_suffix}. "
        "Review it in the approvals queue."
    )
    notification_id = store.insert_notification(
        principal_id=owner_principal_id,
        kind=APPROVAL_PENDING_KIND,
        title=title,
        body=body,
        subject_id=approval_id,
    )
    # Best-effort OS-level push. Isolated: a failure here never affects the row
    # above or the parked turn.
    fire_os_notification(title, body)
    return notification_id
