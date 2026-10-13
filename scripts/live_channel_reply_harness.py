# SPDX-License-Identifier: Apache-2.0
"""Set up the Telegram channel the 2026-10-13 live round sends messages to.

BUG-315's round proves that the answer to the owner's own Telegram message goes
back over Telegram, and that one carrying sensitive information is held for the
owner. Pairing a real bot needs a Telegram account this host does not have, and
turning a channel on needs a delivered test first (DEC-14 step 3) — which a
round with no real bot cannot give. So this pairs and turns the channel on with
the product's own control service and store, opens the channel capability the
way an owner does, and leaves everything that decides an outcome to the running
host: the inbound route, the turn, the sensitivity check and the governed send.

    python scripts/live_channel_reply_harness.py <workspace> telegram <owner_sender_id>

Not reachable from the product; a harness for live rounds only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from raiker.cli.principal_resolver import resolve_local_principal
from raiker.contracts.ids import utc_now
from raiker.control.service import RuntimeControlService
from raiker.storage.sqlite import SQLiteStore


def telegram(workspace: Path, owner_sender_id: str) -> dict[str, object]:
    principal, err = resolve_local_principal(workspace, None)
    if principal is None:
        raise SystemExit(f"no owner: {err}")
    owner = principal.principal_id
    control = RuntimeControlService(workspace)
    control.activate_runtime_mode("local_single_user_runtime", owner, "live round 2026-10-13")
    store = SQLiteStore(workspace)
    with store.connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref)"
            " VALUES (?, ?, ?, ?)",
            ("external_channel_runtime", owner, utc_now(), "docs/threat-models/channels.md"),
        )
    opened = control.set_capability_state(
        "external_channel_runtime", "enabled_runtime", owner, "live round 2026-10-13",
        confirmation_token="live-round",
    )
    paired = control.pair_channel(owner, "channel.telegram", "Telegram", [owner_sender_id])
    if not paired.ok:
        raise SystemExit(f"pair: {paired.reason_code}")
    pairing_id = str(paired.data["pairing_id"])
    store.set_channel_pairing_routing(
        pairing_id, routing_mode="new_turn", target_session_id=None,
        owner_sender_id=owner_sender_id, approval_relay_enabled=False,
    )
    with store.connect() as connection:
        connection.execute("UPDATE channel_pairings SET enabled = 1 WHERE pairing_id = ?", (pairing_id,))
    return {"pairing_id": pairing_id, "gate": bool(opened.ok)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument("action", choices=["telegram"])
    parser.add_argument("owner_sender_id")
    args = parser.parse_args()
    print(json.dumps(telegram(args.workspace.resolve(), args.owner_sender_id)))


if __name__ == "__main__":
    main()
