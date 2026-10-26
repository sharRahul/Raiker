"""QUI-F06 — a routine's results, also sent to a connected channel.

A routine's result always lands on Home and in its own conversation. The owner
may also have it sent to a paired channel (Telegram, Slack, a webhook), which
is an unattended outbound send, so two things are required, separately:

* **Consent at the moment the routine is set up.** The form asks for it in
  words; without it nothing is stored and nothing is ever sent.
* **The channel's own gates, on every send.** Each result goes out as a
  governed ``external_channel_runtime`` action through the runtime authority:
  the capability gate, the decision mode (an *ask* parks the send in
  Approvals), an enabled and unpaused pairing, and the egress allowlist all
  apply exactly as for any other channel message.

What happened to the last send is kept on the routine, so a routine whose
channel refused says so rather than looking delivered.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from raiker.contracts.ids import utc_now
from raiker.storage.sqlite import SQLiteStore

#: A channel message is short; the full result stays in the routine's conversation.
MAX_DELIVERY_CHARS = 3500


class DeliveryError(ValueError):
    pass


def set_delivery(store: SQLiteStore, *, task_id: str, owner_principal_id: str, connector_id: str, consent: bool) -> None:
    """Record where a routine's results also go. Refused without explicit consent."""
    if not consent:
        raise DeliveryError("routine_delivery_needs_consent")
    pairing = store.get_channel_pairing_by_connector(connector_id)
    if pairing is None:
        raise DeliveryError("routine_delivery_channel_unknown")
    store._execute(
        "INSERT INTO routine_deliveries (task_id, owner_principal_id, connector_id, consented_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(task_id) DO UPDATE SET connector_id = excluded.connector_id, consented_at = excluded.consented_at",
        (task_id, owner_principal_id, connector_id, utc_now()),
    )


def clear_delivery(store: SQLiteStore, *, task_id: str, owner_principal_id: str) -> bool:
    changed = store._execute(
        "DELETE FROM routine_deliveries WHERE task_id = ? AND owner_principal_id = ?",
        (task_id, owner_principal_id),
    )
    return bool(changed)


def deliveries(store: SQLiteStore, *, owner_principal_id: str) -> list[dict[str, Any]]:
    rows = store._rows(
        "SELECT task_id, connector_id, consented_at, last_status, last_reason, last_at "
        "FROM routine_deliveries WHERE owner_principal_id = ? ORDER BY consented_at",
        (owner_principal_id,),
    )
    found: list[dict[str, Any]] = []
    for row in rows:
        pairing = store.get_channel_pairing_by_connector(str(row["connector_id"]))
        found.append({
            **dict(row),
            "channel_name": str((pairing or {}).get("display_name") or row["connector_id"]),
        })
    return found


def message(title: str, result: str) -> str:
    body = " ".join(result.split()) if len(result) > MAX_DELIVERY_CHARS else result.strip()
    text = f"{title}\n\n{body}" if body else title
    return text if len(text) <= MAX_DELIVERY_CHARS else text[: MAX_DELIVERY_CHARS - 1].rstrip() + "…"


def deliver(workspace_root: str | Path, store: SQLiteStore, *, task_id: str, title: str, result: str) -> str | None:
    """Send one finished run's result, if the owner asked for it. Returns the outcome, or ``None``."""
    row = store._row(
        "SELECT owner_principal_id, connector_id FROM routine_deliveries WHERE task_id = ?", (task_id,)
    )
    if row is None:
        return None
    from raiker.control.service import RuntimeControlService

    outcome = RuntimeControlService(workspace_root).deliver_routine_result(
        str(row["owner_principal_id"]), str(row["connector_id"]), message(title, result)
    )
    status = "delivered" if outcome.ok else "not_delivered"
    store._execute(
        "UPDATE routine_deliveries SET last_status = ?, last_reason = ?, last_at = ? WHERE task_id = ?",
        (status, None if outcome.ok else outcome.reason_code, utc_now(), task_id),
    )
    return status
