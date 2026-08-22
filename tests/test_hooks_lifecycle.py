"""The seven lifecycle events BUG-223 wired, proved one at a time.

``tests/test_hooks_surface.py`` derives the dispatched set from the source, which
catches a *missing* call site. It cannot catch a call site that exists and never
runs — a guard behind a condition that is never true reads identically to one
that fires on every turn. So each event is exercised here through the object that
owns its boundary, and the proof is the durable record: a hook that ran left
``hook_matched`` and ``hook_executed`` in the event log, and a hook that did not
left nothing.

``block_destructive_shell`` is the observer. It returns ``no_decision`` for every
tool that is not ``shell``, so it executes without changing anything — which is
exactly what an observation-only event should be able to demonstrate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import utc_now
from raiker.control.dashboard import DashboardService
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager

OWNER_PRINCIPAL = "principal_owner"


def _config(*events: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "hooks": {
            event: [
                {
                    "matcher": "*",
                    "handlers": [
                        {
                            "id": f"watch-{event}",
                            "type": "builtin",
                            "builtin": "block_destructive_shell",
                        }
                    ],
                }
            ]
            for event in events
        },
    }


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir(exist_ok=True)
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    return tmp_path


def _write_hooks(workspace: Path, *events: str) -> None:
    (workspace / "config" / "hooks.json").write_text(
        json.dumps(_config(*events)), encoding="utf-8"
    )


def _owned_session(store: SQLiteStore, session_id: str) -> str:
    """A real session row, because a task is foreign-keyed to one."""
    from raiker.sessions.manager import SessionManager

    row = store.get_principal(OWNER_PRINCIPAL)
    user_id = str(row["delegated_by_user_id"]) if row else None
    SessionManager(store, store.paths.workspace_root).get_or_create(
        session_id, user_id=user_id
    )
    return session_id


def _hook_events(store: SQLiteStore, session_id: str) -> list[str]:
    """Hook-emitted event types recorded for one session, oldest first."""
    path = EventLogWriter(store).path_for_session(session_id)
    if not path.exists():
        return []
    return [
        json.loads(line)["event_type"]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line)["event_type"].startswith("hook_")
    ]


# ── TaskCreated / TaskCompleted ──────────────────────────────────────────────


def test_creating_a_task_fires_taskcreated(workspace: Path) -> None:
    _write_hooks(workspace, "TaskCreated")
    store = SQLiteStore(workspace)

    TaskManager(store, EventLogWriter(store)).create_task(
        session_id=_owned_session(store, "sess_task"),
        title="Reindex",
        objective="Reindex the workspace",
    )

    assert "hook_executed" in _hook_events(store, "sess_task")


@pytest.mark.parametrize(
    ("finish", "argument"),
    [("complete_task", "done"), ("fail_task", "broke"), ("cancel_task", "stopped")],
)
def test_every_terminal_state_fires_taskcompleted(
    workspace: Path, finish: str, argument: str
) -> None:
    # Terminal is terminal. A rule that cleans up after a task has to run when the
    # task failed or was cancelled too, or it only ever tidies the happy path.
    _write_hooks(workspace, "TaskCompleted")
    store = SQLiteStore(workspace)
    manager = TaskManager(store, EventLogWriter(store))
    task = manager.create_task(
        session_id=_owned_session(store, "sess_term"), title="Work", objective="Do the work"
    )

    getattr(manager, finish)(task.task_id, argument)

    assert "hook_executed" in _hook_events(store, "sess_term")


def test_a_task_fires_nothing_when_no_rule_names_it(workspace: Path) -> None:
    _write_hooks(workspace, "PreToolUse")
    store = SQLiteStore(workspace)

    manager = TaskManager(store, EventLogWriter(store))
    task = manager.create_task(
        session_id=_owned_session(store, "sess_quiet"), title="Work", objective="Do the work"
    )
    manager.complete_task(task.task_id, "done")

    assert _hook_events(store, "sess_quiet") == []


def test_the_owner_switch_stops_the_task_events_too(workspace: Path) -> None:
    # The switch has to reach every event, not only the ones the gateway owns —
    # otherwise turning hooks off leaves the background ones running.
    _write_hooks(workspace, "TaskCreated")
    store = SQLiteStore(workspace)
    store.put_user_settings(
        OWNER_PRINCIPAL, json.dumps({"hooks": {"disabled": True}}), utc_now()
    )

    TaskManager(store, EventLogWriter(store)).create_task(
        session_id=_owned_session(store, "sess_off"), title="Work", objective="Do the work"
    )

    assert _hook_events(store, "sess_off") == []


# ── SessionEnd ───────────────────────────────────────────────────────────────


def test_archiving_a_conversation_fires_sessionend(workspace: Path) -> None:
    _write_hooks(workspace, "SessionEnd")
    store = SQLiteStore(workspace)
    _owned_session(store, "sess_archive")

    result = DashboardService(workspace).set_session_archived(
        "sess_archive", True, OWNER_PRINCIPAL
    )

    assert result.ok is True
    assert "hook_executed" in _hook_events(store, "sess_archive")


def test_restoring_a_conversation_does_not_fire_sessionend(workspace: Path) -> None:
    # Un-archiving is the opposite decision. Firing "this ended" on it would make
    # a rule that archives elsewhere, or notifies, run at exactly the wrong time.
    _write_hooks(workspace, "SessionEnd")
    store = SQLiteStore(workspace)
    _owned_session(store, "sess_restore")
    DashboardService(workspace).set_session_archived("sess_restore", True, OWNER_PRINCIPAL)
    before = len(_hook_events(store, "sess_restore"))

    DashboardService(workspace).set_session_archived("sess_restore", False, OWNER_PRINCIPAL)

    assert len(_hook_events(store, "sess_restore")) == before


def test_deleting_a_conversation_fires_sessionend_before_the_row_goes(
    workspace: Path,
) -> None:
    # Dispatched before the delete so a handler can still read what it is being
    # told about; the transcript file is removed with the session either way.
    _write_hooks(workspace, "SessionEnd")
    store = SQLiteStore(workspace)
    _owned_session(store, "sess_delete")

    dispatched: list[str] = []
    service = DashboardService(workspace)
    original = service._dispatch_session_end_hook  # noqa: SLF001

    def _record(session_id: str, reason: str) -> None:
        dispatched.append(reason)
        assert store.load_session("sess_delete") is not None
        original(session_id, reason)

    service._dispatch_session_end_hook = _record  # type: ignore[method-assign]  # noqa: SLF001
    result = service.delete_session("sess_delete", OWNER_PRINCIPAL)

    assert result.ok is True
    assert dispatched == ["deleted"]


# ── Stop / StopFailure ───────────────────────────────────────────────────────


def _response(status: str) -> Any:
    from raiker.contracts.models import AgentResponse

    return AgentResponse(
        request_id="req_1",
        session_id="sess_turn",
        turn_id="turn_1",
        status=status,
        message="whatever happened",
    )


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("completed", "Stop"),
        ("failed", "StopFailure"),
        ("stopped", "StopFailure"),
        ("needs_approval", "StopFailure"),
    ],
)
def test_a_turn_that_did_not_finish_is_not_reported_as_a_clean_stop(
    workspace: Path, status: str, expected: str
) -> None:
    """The split is the point: only `completed` produces `Stop`.

    A turn parked on an approval has not finished — it is waiting — and a turn the
    owner stopped did what it was told. Reporting either as `Stop` would let a
    rule written to react to completion fire on a run that never completed.
    """
    from raiker.cli.commands import build_prompt_envelope
    from raiker.gateway.agent_gateway import AgentGateway

    _write_hooks(workspace, expected)
    gateway = AgentGateway(workspace, principal_id=OWNER_PRINCIPAL)
    envelope = build_prompt_envelope("hello", session_id="sess_turn")

    gateway._dispatch_turn_end_hook(envelope, _response(status))  # noqa: SLF001

    assert "hook_executed" in _hook_events(SQLiteStore(workspace), "sess_turn")


@pytest.mark.parametrize(
    ("status", "configured"),
    [("completed", "StopFailure"), ("failed", "Stop")],
)
def test_the_other_turn_end_event_stays_quiet(
    workspace: Path, status: str, configured: str
) -> None:
    from raiker.cli.commands import build_prompt_envelope
    from raiker.gateway.agent_gateway import AgentGateway

    _write_hooks(workspace, configured)
    gateway = AgentGateway(workspace, principal_id=OWNER_PRINCIPAL)
    envelope = build_prompt_envelope("hello", session_id="sess_turn")

    gateway._dispatch_turn_end_hook(envelope, _response(status))  # noqa: SLF001

    assert _hook_events(SQLiteStore(workspace), "sess_turn") == []


def test_a_real_turn_ends_with_stopfailure_when_it_fails(
    workspace: Path, monkeypatch: pytest.MonkeyPatch, offline_default_model: None
) -> None:
    """Through the gateway, not around it — `_finalize_turn` has to call it.

    A helper that is correct and never reached is the failure mode this whole
    file exists for, so one event is proved end to end through a real turn.
    """
    from raiker.cli.commands import build_prompt_envelope
    from raiker.gateway.agent_gateway import AgentGateway

    monkeypatch.chdir(workspace)
    source = Path(__file__).resolve().parents[1] / "raiker" / "config"
    for name in ("model-profiles.json", "channel-connectors.json"):
        (workspace / "config" / name).write_text(
            (source / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    _write_hooks(workspace, "StopFailure")

    response = AgentGateway(workspace, principal_id=OWNER_PRINCIPAL).submit_prompt(
        build_prompt_envelope("!echo hi")
    )

    assert response.status == "failed"
    assert "hook_executed" in _hook_events(SQLiteStore(workspace), response.session_id)


# ── SubagentStart / SubagentStop ─────────────────────────────────────────────


def _broker_with_hooks(workspace: Path) -> Any:
    from raiker.hooks.factory import dispatcher_for_workspace
    from raiker.policy.engine import PolicyEngine, StaticPolicyConfig
    from raiker.tools.broker import ToolBroker

    store = SQLiteStore(workspace)
    return ToolBroker(
        workspace_root=workspace,
        policy_engine=PolicyEngine(StaticPolicyConfig(workspace)),
        store=store,
        writer=EventLogWriter(store),
        hook_dispatcher=dispatcher_for_workspace(store),
        principal_id=OWNER_PRINCIPAL,
    )


def _spawn_context(workspace: Path) -> Any:
    from raiker.tools.broker import ToolExecutionContext

    _owned_session(SQLiteStore(workspace), "sess_spawn")
    return ToolExecutionContext(
        session_id="sess_spawn",
        turn_id="turn_spawn",
        acting_principal_id=OWNER_PRINCIPAL,
        owner_principal_id=OWNER_PRINCIPAL,
        verified_identity=None,  # type: ignore[arg-type]
    )


def test_a_delegation_fires_both_of_its_boundaries(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Both ends, not just the start: a rule that records what a subagent found
    # needs the stop, and a rule that notices one running needs the start.
    _write_hooks(workspace, "SubagentStart", "SubagentStop")
    import raiker.tools.subagent_tools as subagent_tools

    monkeypatch.setattr(
        subagent_tools,
        "spawn_subagent",
        lambda *args, **kwargs: {"status": "success", "subagent_id": "sub_1", "steps_executed": 2},
    )

    broker = _broker_with_hooks(workspace)
    result = broker._spawn_subagent(  # noqa: SLF001
        {"objective": "find the config", "name": "research"}, _spawn_context(workspace)
    )

    assert result["status"] == "success"
    # Two rules, one handler each: matched/executed/decision for each boundary.
    executed = [
        name for name in _hook_events(SQLiteStore(workspace), "sess_spawn")
        if name == "hook_executed"
    ]
    assert len(executed) == 2


def test_a_failed_delegation_still_fires_its_stop(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_hooks(workspace, "SubagentStop")
    import raiker.tools.subagent_tools as subagent_tools

    monkeypatch.setattr(
        subagent_tools,
        "spawn_subagent",
        lambda *args, **kwargs: {"status": "failed", "error": {"type": "subagent_failed"}},
    )

    broker = _broker_with_hooks(workspace)
    broker._spawn_subagent(  # noqa: SLF001
        {"objective": "find the config"}, _spawn_context(workspace)
    )

    assert "hook_executed" in _hook_events(SQLiteStore(workspace), "sess_spawn")
