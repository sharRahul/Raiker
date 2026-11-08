"""SB-4 (beta plan) — every hook event refuses a command hook without an enforced boundary.

For each event the runtime dispatches, a command hook is configured with the
owner's decision authority and dispatched on a host whose native boundary does
not answer its probe. Each time:

* the hook's script is never started on the host — only the boundary's own
  probe runs;
* the failure is recorded as ``native_sandbox_required``;
* on an event that decides (``PreToolUse``, ``PreCompact``, ``ConfigChange``)
  the enforcing hook that could not run fails closed: the owner is asked.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from raiker.events.query import EventViewer
from raiker.events.writer import EventLogWriter
from raiker.hooks.contracts import DECIDING_HOOK_EVENTS, DISPATCHED_HOOK_EVENTS, HookInput
from raiker.hooks.dispatcher import HookDispatcher
from raiker.hooks.registry import HooksRegistry
from raiker.storage.sqlite import SQLiteStore


@pytest.mark.parametrize("event", sorted(DISPATCHED_HOOK_EVENTS))
def test_a_command_hook_is_refused_on_a_host_without_the_boundary(
    event: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "hook").write_text("untrusted hook", encoding="utf-8")
    launches: list[list[str]] = []

    def no_boundary(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        # The runner's probe answers nothing usable: this host has no boundary.
        launches.append([str(part) for part in argv])
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(subprocess, "run", no_boundary)
    registry = HooksRegistry.from_config(
        {
            "schema_version": "1.0",
            "hooks": {
                event: [
                    {
                        "matcher": "*",
                        "handlers": [
                            {"id": "guard", "type": "command", "command": ["hook"], "decision_authority": True}
                        ],
                    }
                ]
            },
        }
    )
    store = SQLiteStore(tmp_path)
    dispatcher = HookDispatcher(registry, workspace_root=tmp_path, writer=EventLogWriter(store))
    outcome = dispatcher.dispatch(
        HookInput(event_name=event, tool_name="shell", tool_input={"command": "ls"}),
        session_id="sess_hooks",
        turn_id=None,
    )

    script = str(tmp_path / "hook")
    assert not any(script in part for argv in launches for part in argv), "the hook ran on the host"
    # Only Raiker's own probes start: the boundary's runner, and the store's
    # SQLCipher capability check when the store first opens.
    raiker_owned = [
        argv for argv in launches
        if Path(argv[0]).stem == "raiker-command-runner" or "raiker.storage.sqlcipher_probe_worker" in argv
    ]
    assert raiker_owned == launches, launches

    viewer = EventViewer(store)
    failures = [
        viewer.read_event_payload(row["event_id"]) or {}
        for row in viewer.list_events(limit=50)
        if row.get("event_type") == "hook_failed"
    ]
    assert failures, f"{event}: the refusal was not recorded"
    assert "native_sandbox_required" in json.dumps(failures[0])
    if event in DECIDING_HOOK_EVENTS:
        assert outcome.decision == "ask", f"{event}: an enforcing hook that could not run let the action through"
