"""DEC-23 step 4 — an enforcing hook that cannot answer does not wave the action through.

A hook the owner gave decision authority is enforcement. When it hung or
crashed, the dispatcher recorded the failure and carried on as though the hook
had no objection — so the guard let through exactly what it was there to stop.
Now its failure counts as *ask*: the action goes to the owner. An advisory hook
(no authority) still only records its failure, since it could not have stopped
anything had it run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.events.writer import EventLogWriter
from raiker.hooks import dispatcher as dispatcher_module
from raiker.hooks.contracts import HookInput
from raiker.hooks.dispatcher import HookDispatcher
from raiker.hooks.handlers.command import CommandHookError, CommandHookTimeout
from raiker.hooks.registry import HooksRegistry
from raiker.storage.sqlite import SQLiteStore


def _registry(*, authority: bool) -> HooksRegistry:
    return HooksRegistry.from_config(
        {
            "schema_version": "1.0",
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "shell",
                        "handlers": [
                            {
                                "id": "guard",
                                "type": "command",
                                "command": ["guard"],
                                "decision_authority": authority,
                            }
                        ],
                    }
                ]
            },
        }
    )


def _dispatch(dispatcher: HookDispatcher, session_id: str | None = None) -> object:
    return dispatcher.dispatch(
        HookInput(event_name="PreToolUse", tool_name="shell", tool_input={"command": "ls"}),
        session_id=session_id,
        turn_id=None,
    )


@pytest.mark.parametrize("failure", [CommandHookTimeout("slow"), CommandHookError("crashed")])
def test_an_enforcing_hook_that_fails_asks_the_owner(
    monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    def broken(*_args: object, **_kwargs: object) -> object:
        raise failure

    monkeypatch.setattr(dispatcher_module, "run_command", broken)
    outcome = _dispatch(HookDispatcher(_registry(authority=True), workspace_root="."))

    assert outcome.decision == "ask"  # type: ignore[attr-defined]
    assert any("guard" in reason for reason in outcome.reasons)  # type: ignore[attr-defined]


def test_an_advisory_hook_that_fails_changes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*_args: object, **_kwargs: object) -> object:
        raise CommandHookTimeout("slow")

    monkeypatch.setattr(dispatcher_module, "run_command", broken)
    outcome = _dispatch(HookDispatcher(_registry(authority=False), workspace_root="."))

    assert outcome.decision == "no_decision"  # type: ignore[attr-defined]


def test_the_failure_says_it_failed_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import json

    from raiker.events.query import EventViewer

    def broken(*_args: object, **_kwargs: object) -> object:
        raise CommandHookTimeout("slow")

    monkeypatch.setattr(dispatcher_module, "run_command", broken)
    store = SQLiteStore(tmp_path)
    dispatcher = HookDispatcher(
        _registry(authority=True), workspace_root=tmp_path, writer=EventLogWriter(store)
    )
    _dispatch(dispatcher, session_id="sess_hooks")

    viewer = EventViewer(store)
    timeouts = [
        json.dumps(viewer.read_event_payload(row["event_id"]) or {})
        for row in viewer.list_events(limit=50)
        if row.get("event_type") == "hook_timeout"
    ]
    assert timeouts and '"failed_closed": true' in timeouts[0]


def test_a_denying_hook_still_wins_over_one_that_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Failing closed only ever adds *ask*; a deny elsewhere is still a deny."""
    registry = HooksRegistry.from_config(
        {
            "schema_version": "1.0",
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "shell",
                        "handlers": [
                            {"id": "guard", "type": "command", "command": ["guard"], "decision_authority": True},
                            {"id": "b", "type": "builtin", "builtin": "block_destructive_shell"},
                        ],
                    }
                ]
            },
        }
    )

    def broken(*_args: object, **_kwargs: object) -> object:
        raise CommandHookError("crashed")

    monkeypatch.setattr(dispatcher_module, "run_command", broken)
    outcome = HookDispatcher(registry, workspace_root=".").dispatch(
        HookInput(event_name="PreToolUse", tool_name="shell", tool_input={"command": "rm -rf /"}),
        session_id=None,
        turn_id=None,
    )
    assert outcome.decision == "deny"
