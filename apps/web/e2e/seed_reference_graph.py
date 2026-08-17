"""Seed one workspace with the reference-graph case, for the live map evidence.

Run against a workspace whose owner account already exists — the browser makes
it — because the citation rows are scoped to that owner's principal and there is
no honest way to know it in advance.

What it plants is the pair the fix is about: a conversation grounded in two
files, one of which is still on disk and one of which has been deleted since.
Everything else about the map is already covered by the seeded unit tests; this
exists so the *rendering* of an unresolved reference can be photographed.

    python seed_reference_graph.py <workspace-root>
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from raiker.storage.sqlite import SQLiteStore  # noqa: E402

KEPT = "docs/backup-runbook.md"
DELETED = "docs/retired-playbook.md"


def main(workspace: str) -> int:
    root = Path(workspace)
    store = SQLiteStore(root)

    with store.connect() as connection:
        row = connection.execute(
            "SELECT principal_id FROM principals WHERE principal_type = 'human' "
            "ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
        user = connection.execute(
            "SELECT user_id FROM users ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
    if row is None or user is None:
        print("no owner account yet — sign in through the UI first", file=sys.stderr)
        return 2
    principal_id = str(row["principal_id"])
    user_id = str(user["user_id"])

    # One file the answer rested on that is still there, and one that is not.
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / KEPT).write_text(
        "Restores are verified against the encrypted NAS target.\n", encoding="utf-8"
    )
    (root / DELETED).unlink(missing_ok=True)

    session_id = "sess_reference_graph_evidence"
    if store.load_session(session_id) is None:
        store.create_session(
            session_id, str(root), title="Restore drill", user_id=user_id, origin="chat"
        )
    store.insert_turn(session_id, "turn_reference_graph", "What does the runbook say?")
    store.record_turn_sources(
        session_id=session_id,
        turn_id="turn_reference_graph",
        principal_id=principal_id,
        rows=[
            {
                "source_id": f"s{ordinal + 1}",
                "ordinal": ordinal,
                "kind": "file",
                "title": path,
                "locator": path,
                "tool_name": "read_file",
                "detail": "read in full",
                "attachment_id": "",
                "passage": passage,
            }
            for ordinal, (path, passage) in enumerate(
                [
                    (KEPT, "Restores are verified against the encrypted NAS target."),
                    (DELETED, "Deploys pause while a restore drill is running."),
                ]
            )
        ],
    )
    print(f"seeded {KEPT} (on disk) and {DELETED} (deleted) for {principal_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
