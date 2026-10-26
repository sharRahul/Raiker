"""QUI-F19 — undo windows for sends.

An approved connector write (sending an email, posting a message) is not sent
the moment it is approved. It is **held** for :data:`HOLD_SECONDS`, during which
the status line reads *Sending in 10 s · Undo*; **Undo**, or **Stop** on the
conversation it belongs to, takes it back and nothing leaves this computer.

The hold is an addition to approval, never a replacement: nothing is held that
was not approved, and the send that follows is the same single-use intent the
approval named.

The send happens only inside the request that held it. If the host stops
during the hold the intent stays ``held`` and is never sent afterwards: a send
the owner can no longer watch or undo is not one Raiker makes on its own.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from raiker.contracts.ids import utc_now
from raiker.storage.sqlite import SQLiteStore

#: How long an approved send waits for Undo.
HOLD_SECONDS = 10.0
#: How often the hold looks for an Undo while it waits.
POLL_SECONDS = 0.2


def _at(seconds: float) -> str:
    return (datetime.now(UTC) + timedelta(seconds=seconds)).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def hold(store: SQLiteStore, intent_id: str, *, seconds: float = HOLD_SECONDS) -> str | None:
    """Claim a pending intent into its undo window. ``None`` if it was already consumed."""
    until = _at(seconds)
    claimed = store._execute(
        "UPDATE connector_write_intents SET status = 'held', held_until = ? "
        "WHERE intent_id = ? AND status = 'pending_approval'",
        (until, intent_id),
    )
    return until if claimed == 1 else None


async def wait_for_release(store: SQLiteStore, intent_id: str, *, seconds: float = HOLD_SECONDS) -> bool:
    """Wait out the window; ``True`` when the intent is now claimed for sending.

    The claim is one conditional update (``held`` → ``executing``), so an Undo
    that lands at the last moment either wins and nothing is sent, or loses
    because the send already began — never both.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + seconds
    while loop.time() < deadline:
        await asyncio.sleep(min(POLL_SECONDS, max(0.0, deadline - loop.time())))
        row = store._row("SELECT status FROM connector_write_intents WHERE intent_id = ?", (intent_id,))
        if row is None or row["status"] != "held":
            return False
    claimed = store._execute(
        "UPDATE connector_write_intents SET status = 'executing' WHERE intent_id = ? AND status = 'held'",
        (intent_id,),
    )
    return claimed == 1


def undo(store: SQLiteStore, *, principal_id: str, approval_id: str) -> bool:
    """Take back a held send. ``False`` when there is nothing held to take back."""
    changed = store._execute(
        "UPDATE connector_write_intents SET status = 'undone', undone_at = ? "
        "WHERE approval_id = ? AND principal_id = ? AND status = 'held'",
        (utc_now(), approval_id, principal_id),
    )
    return changed == 1
