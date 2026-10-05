"""Tell the owner once when a search index is found damaged (BUG-322, DEC-24 step 6)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from raiker.notify.approval_notifier import dispatch_notification_hook, fire_os_notification

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

#: Its own kind, so the notice leads to the repair and the delivery policy can
#: place it. It is maintenance, not a security event: quiet hours hold it.
INDEX_DAMAGED_KIND = "search_index_damaged"

#: What each index is to the owner. The table names stay in Diagnostics.
INDEX_LABELS: dict[str, str] = {
    "approved_memory_fts": "Memory search",
    "conversation_fts": "Conversation search",
    "managed_file_chunk_fts": "File search",
    "vector_records": "Search by meaning",
}


def notify_search_index_damaged(store: SQLiteStore, index_name: str, damaged_count: int) -> str | None:
    """Write the notice for an index the host check just found damaged.

    ``None`` when there is no owner account yet. Never raises: a notice is a
    courtesy on top of the attention item the same check already recorded.
    """
    owner = store.original_account_principal_id()
    if not owner:
        return None
    label = INDEX_LABELS.get(index_name, index_name)
    title = f"{label} needs repairing"
    body = (
        f"{damaged_count} stored vector{'s' if damaged_count != 1 else ''} could not be read, so those "
        "memories are not found by meaning. Remove them under Observability and they will be indexed again."
        if index_name == "vector_records"
        else "This search index is damaged, so searches through it fail. Rebuild it under Observability; "
        "nothing it was built from is changed."
    )
    try:
        notification_id = store.insert_notification(
            principal_id=owner,
            kind=INDEX_DAMAGED_KIND,
            title=title,
            body=body,
            subject_id=index_name,
        )
    except Exception:  # noqa: BLE001 - the attention item already says it
        return None
    fire_os_notification(title, body, store=store, notification_id=notification_id)
    dispatch_notification_hook(
        store,
        owner_principal_id=owner,
        kind=INDEX_DAMAGED_KIND,
        notification_id=notification_id,
        subject_id=index_name,
    )
    return notification_id
