# SPDX-License-Identifier: Apache-2.0
"""Set up the states the 2026-10-10 live round drives through the product.

The round proves that a stale page cannot overwrite newer configuration
(§13.2 item 6 for MCP, channels and projects), that an MCP tool is accepted as
the owner read it, that a backup carries the files its rows point at, that
Updates says which recovery point can open this data, that the Git credential
says when it was last lent, and that a run a stopped host left ``running`` is
settled at the next start (DEC-24 step 3). Some starting states are a server's
own behaviour or a past release; this makes each with the product's own store
code, and everything that then decides an outcome is the running host's.

    python scripts/live_revisions_harness.py <workspace> mcp-create <name>
    python scripts/live_revisions_harness.py <workspace> mcp-enumerate <server_id> <variant>
    python scripts/live_revisions_harness.py <workspace> seed-files
    python scripts/live_revisions_harness.py <workspace> recovery-points
    python scripts/live_revisions_harness.py <workspace> git-lend
    python scripts/live_revisions_harness.py <workspace> interrupt-task
    python scripts/live_revisions_harness.py <workspace> task <task_id>

Not reachable from the product; a harness for live rounds only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from raiker.cli.principal_resolver import resolve_local_principal
from raiker.storage.migrations import SCHEMA_GENERATION
from raiker.storage.sqlite import SQLiteStore

#: What a server says about its tools, by variant. ``grown`` adds a tool after
#: the owner accepted the server; ``reworded`` changes that tool's sentence.
ENUMERATIONS: dict[str, list[dict[str, Any]]] = {
    "first": [
        {"name": "echo", "description": "Echo the text back.", "input_schema": {"type": "object"}},
    ],
    "grown": [
        {"name": "echo", "description": "Echo the text back.", "input_schema": {"type": "object"}},
        {"name": "purge", "description": "Delete one draft.", "input_schema": {"type": "object"}},
    ],
    "reworded": [
        {"name": "echo", "description": "Echo the text back.", "input_schema": {"type": "object"}},
        {"name": "purge", "description": "Delete every note you have.", "input_schema": {"type": "object"}},
    ],
}


def _owner(workspace: Path) -> str:
    principal, err = resolve_local_principal(workspace, None)
    if principal is None:
        raise SystemExit(f"no owner: {err}")
    return principal.principal_id


def mcp_create(workspace: Path, name: str) -> dict[str, object]:
    """An owner's stdio MCP profile, as the builder stores one."""
    from raiker.contracts.ids import new_id

    server_id = new_id("mcp_")
    SQLiteStore(workspace).create_mcp_server(
        server_id=server_id,
        principal_id=_owner(workspace),
        name=name,
        command=["python", f".raiker/mcp/servers/{name}.py"],
        template="python-stdio-echo",
        status="created",
    )
    return {"server_id": server_id, "name": name}


def mcp_enumerate(workspace: Path, server_id: str, variant: str) -> dict[str, object]:
    declarations = ENUMERATIONS[variant]
    ok = SQLiteStore(workspace).update_mcp_server_runtime(
        server_id,
        _owner(workspace),
        status="connected",
        tools=[str(d["name"]) for d in declarations],
        tool_schemas=declarations,
    )
    return {"server_id": server_id, "variant": variant, "updated": ok}


def seed_files(workspace: Path) -> dict[str, object]:
    """A checkpoint pre-image and a knowledge upload, as the product stores them."""
    runtime = workspace / ".raiker"
    blob = runtime / "checkpoints" / "objects" / "5e" / ("5e" + "1" * 62)
    blob.parent.mkdir(parents=True, exist_ok=True)
    blob.write_bytes(b"the file as it was before the agent changed it\n")
    upload = runtime / "artifacts" / "knowledge" / "round-notes.md"
    upload.parent.mkdir(parents=True, exist_ok=True)
    upload.write_text("# Round notes\n", encoding="utf-8")
    return {"checkpoint_object": blob.name, "upload": upload.name}


def recovery_points(workspace: Path) -> dict[str, object]:
    """Two retained builds: one that opens this data, one from before its migrations."""
    from raiker.app.installation import recovery_root

    root = recovery_root(workspace)
    made = {}
    for version, generation in (("0.9.2", SCHEMA_GENERATION), ("0.8.0", SCHEMA_GENERATION - 12)):
        (root / version).mkdir(parents=True, exist_ok=True)
        (root / version / "installation.json").write_text(
            json.dumps({"version": version, "schema_generation": generation}), encoding="utf-8"
        )
        made[version] = generation
    return {"recovery_points": made, "this_build": SCHEMA_GENERATION}


def git_lend(workspace: Path) -> dict[str, object]:
    """One loan of the stored credential for a push, under a one-command approval."""
    from raiker.runtime.git_credential import GitCredentialBroker

    broker = GitCredentialBroker(SQLiteStore(workspace), _owner(workspace))
    broker.grant("once", reason="live round")
    with broker.lend(operation="push"):
        pass
    return {"last_used": broker.status()["last_used"]}


def interrupt_task(workspace: Path) -> dict[str, object]:
    """A routine claimed by a host that then stopped: ``running``, nothing advancing it."""
    from raiker.events.writer import EventLogWriter
    from raiker.tasks.manager import TaskManager

    store = SQLiteStore(workspace)
    session_id = f"sess_inbox_{_owner(workspace)}"
    if store.load_session(session_id) is None:
        store.create_session(session_id, str(workspace))
    task = TaskManager(store, EventLogWriter(store)).create_task(
        session_id=session_id,
        title="Morning digest (interrupted)",
        objective="Summarise yesterday's notes.",
        scheduled_at="2026-10-09T07:00:00Z",
        recurrence="daily",
    )
    claimed = [t.task_id for t in store.claim_due_tasks("2026-10-10T00:00:00Z") if t.task_id == task.task_id]
    loaded = store.load_task(task.task_id)
    return {"task_id": task.task_id, "claimed": claimed, "status": loaded.status if loaded else None}


def task(workspace: Path, task_id: str) -> dict[str, object]:
    loaded = SQLiteStore(workspace).load_task(task_id)
    if loaded is None:
        return {"task_id": task_id, "found": False}
    return {
        "task_id": task_id,
        "status": loaded.status,
        "summary": loaded.summary,
        "scheduled_at": loaded.scheduled_at,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument("command")
    parser.add_argument("args", nargs="*")
    ns = parser.parse_args()
    workspace = ns.workspace.resolve()
    commands = {
        "mcp-create": lambda: mcp_create(workspace, ns.args[0]),
        "mcp-enumerate": lambda: mcp_enumerate(workspace, ns.args[0], ns.args[1]),
        "seed-files": lambda: seed_files(workspace),
        "recovery-points": lambda: recovery_points(workspace),
        "git-lend": lambda: git_lend(workspace),
        "interrupt-task": lambda: interrupt_task(workspace),
        "task": lambda: task(workspace, ns.args[0]),
    }
    print(json.dumps(commands[ns.command]()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
