"""Tell the owner when remote access stops because two-step sign-in did (BUG-358)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from raiker.notify.approval_notifier import dispatch_notification_hook, fire_os_notification

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

#: A security event, not maintenance: the owner's other devices just lost access.
REMOTE_ACCESS_SUSPENDED_KIND = "remote_access_suspended"


def notify_remote_access_suspended(store: SQLiteStore, *, reason: str) -> str | None:
    """Write the notice; ``None`` when there is no owner. Never raises."""
    owner = store.original_account_principal_id()
    if not owner:
        return None
    title = "Remote access is suspended"
    body = (
        "Two-step sign-in was turned off, so Raiker no longer answers your other devices. "
        "Turn it on again in Settings → Security to restore remote access."
        if reason == "mfa_disabled"
        else "Raiker no longer answers your other devices. Open Settings → Security → Remote access to see why."
    )
    try:
        notification_id = store.insert_notification(
            principal_id=owner,
            kind=REMOTE_ACCESS_SUSPENDED_KIND,
            title=title,
            body=body,
            subject_id="remote_access",
        )
    except Exception:  # noqa: BLE001 - the event log and Settings already say it
        return None
    fire_os_notification(title, body, store=store, notification_id=notification_id)
    dispatch_notification_hook(
        store,
        owner_principal_id=owner,
        kind=REMOTE_ACCESS_SUSPENDED_KIND,
        notification_id=notification_id,
        subject_id="remote_access",
    )
    return notification_id
