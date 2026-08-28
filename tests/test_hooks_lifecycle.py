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


# ── Notification / PostToolBatch / InstructionsLoaded (FIXED-305) ────────────
#
# The three events that close backlog #14. All three observe: each fires after
# the thing it describes has already happened, so what is proved here is that the
# call site runs and that the payload it carries is metadata, not content. A
# handler that could read a turn's standing context or a notification's body out
# of these would be a new way for a repository's `config/hooks.json` to reach
# what the owner's own surfaces redact.


def _notification_session(principal_id: str = OWNER_PRINCIPAL) -> str:
    """The synthetic session a notification's audit rows are written under."""
    return f"notification_{principal_id}"


def test_an_approval_notification_fires_notification(workspace: Path) -> None:
    from raiker.notify.approval_notifier import notify_approval_pending

    _write_hooks(workspace, "Notification")
    store = SQLiteStore(workspace)

    notification_id = notify_approval_pending(
        store,
        acting_principal_id=OWNER_PRINCIPAL,
        approval_id="apr_1",
        tool_name="write_file",
        risk_level="high",
    )

    assert notification_id is not None
    assert "hook_executed" in _hook_events(store, _notification_session())


def test_a_notification_hook_carries_the_kind_and_ids_and_no_copy(
    workspace: Path,
) -> None:
    # The notification's own title and body are owner-facing copy, and the tool
    # name and criterion are in it. A `command` handler a repository introduced
    # must not be able to read any of that, so the dispatched context is asserted
    # field by field rather than by shape.
    from raiker.hooks.contracts import HookInput
    from raiker.hooks.dispatcher import HookDispatcher
    from raiker.notify.approval_notifier import notify_critical_approval_pending

    _write_hooks(workspace, "Notification")
    store = SQLiteStore(workspace)
    seen: list[HookInput] = []
    original = HookDispatcher.dispatch

    def record(self: HookDispatcher, hook_input: HookInput, **rest: Any) -> Any:
        seen.append(hook_input)
        return original(self, hook_input, **rest)

    HookDispatcher.dispatch = record  # type: ignore[method-assign]
    try:
        notify_critical_approval_pending(
            store,
            acting_principal_id=OWNER_PRINCIPAL,
            approval_id="apr_critical",
            tool_name="delete_file",
            criterion="irreversible",
            risk_level="critical",
        )
    finally:
        HookDispatcher.dispatch = original  # type: ignore[method-assign]

    assert len(seen) == 1
    context = seen[0].context
    assert context["kind"] == "critical_approval_pending"
    assert context["subject_id"] == "apr_critical"
    assert set(context) == {"kind", "notification_id", "subject_id"}
    # Nothing from the owner-facing copy reached the handler.
    blob = json.dumps(context)
    assert "delete_file" not in blob
    assert "irreversible" not in blob


def test_a_failing_notification_hook_never_breaks_the_notification(
    workspace: Path,
) -> None:
    # The module's standing contract: a hook failure must not affect the approval
    # flow. The notification row and its id are the flow's output, so both have to
    # survive a dispatcher that raises on construction.
    from raiker.hooks import factory
    from raiker.notify.approval_notifier import notify_approval_pending

    _write_hooks(workspace, "Notification")
    store = SQLiteStore(workspace)
    original = factory.dispatcher_for_workspace

    def explode(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("hook subsystem is down")

    factory.dispatcher_for_workspace = explode  # type: ignore[assignment]
    try:
        notification_id = notify_approval_pending(
            store,
            acting_principal_id=OWNER_PRINCIPAL,
            approval_id="apr_2",
            tool_name="write_file",
        )
    finally:
        factory.dispatcher_for_workspace = original  # type: ignore[assignment]

    assert notification_id is not None
    assert store.list_notifications(OWNER_PRINCIPAL)


def test_the_owner_switch_stops_the_notification_event(workspace: Path) -> None:
    from raiker.notify.approval_notifier import notify_approval_pending

    _write_hooks(workspace, "Notification")
    store = SQLiteStore(workspace)
    store.put_user_settings(
        OWNER_PRINCIPAL, json.dumps({"hooks": {"disabled": True}}), utc_now()
    )

    notify_approval_pending(
        store,
        acting_principal_id=OWNER_PRINCIPAL,
        approval_id="apr_3",
        tool_name="write_file",
    )

    assert _hook_events(store, _notification_session()) == []


class _ScriptedRouter:
    """A model whose turn is fixed in advance, so the turn under test is the runtime's."""

    def __init__(self, responses: list[Any]) -> None:
        self._responses = responses
        self._calls = 0

    def chat(self, provider: str, model: str, messages: Any, tools: Any = None) -> Any:
        index = min(self._calls, len(self._responses) - 1)
        self._calls += 1
        return self._responses[index]

    async def achat(
        self, provider: str, model: str, messages: Any, tools: Any = None, **_: Any
    ) -> Any:
        return self.chat(provider, model, messages, tools)


def _turn(workspace: Path, responses: list[Any]) -> tuple[Any, str]:
    """Run one real turn with hooks attached, and return the orchestrator and session id."""
    from raiker.contracts.ids import new_id
    from raiker.contracts.models import (
        ClientMetadata,
        PromptEnvelope,
        PromptOptions,
        PromptPayload,
        UserMetadata,
    )
    from raiker.hooks.factory import dispatcher_for_workspace
    from raiker.policy.config import StaticPolicyConfig
    from raiker.policy.engine import PolicyEngine
    from raiker.runtime.identity.lifecycle import TurnMachineIdentityLifecycle
    from raiker.runtime.orchestrator import RuntimeOrchestrator
    from raiker.tools.broker import ToolBroker

    store = SQLiteStore(workspace)
    writer = EventLogWriter(store)
    broker = ToolBroker(
        workspace_root=workspace,
        policy_engine=PolicyEngine(StaticPolicyConfig(workspace)),
        store=store,
        writer=writer,
        hook_dispatcher=dispatcher_for_workspace(store, acting_principal_id=OWNER_PRINCIPAL),
        principal_id=OWNER_PRINCIPAL,
    )
    orchestrator = RuntimeOrchestrator(
        workspace_root=workspace,
        writer=writer,
        tool_broker=broker,
        model_router=_ScriptedRouter(responses),  # type: ignore[arg-type]
    )
    envelope = PromptEnvelope(
        request_id=new_id("req_"),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
        client=ClientMetadata(type="test_harness", name="tests", version="0.0.0"),
        user=UserMetadata(),
        prompt=PromptPayload(text="List the files."),
        options=PromptOptions(max_tool_calls=10, approval_mode="manual"),
    )
    store.create_session(envelope.session_id, str(workspace))
    store.insert_turn(envelope.session_id, envelope.turn_id, envelope.prompt.text)
    identity = TurnMachineIdentityLifecycle(workspace, store, writer).start(
        owner_principal_id=OWNER_PRINCIPAL,
        session_id=envelope.session_id,
        turn_id=envelope.turn_id,
        role_ids=("assistant",),
    )
    orchestrator.handle(envelope, identity=identity)
    return orchestrator, envelope.session_id


def _hook_contexts(event_name: str) -> tuple[list[dict[str, Any]], Any]:
    """Record every dispatched context for one event, and the undo for the patch."""
    from raiker.hooks.contracts import HookInput
    from raiker.hooks.dispatcher import HookDispatcher

    contexts: list[dict[str, Any]] = []
    original = HookDispatcher.dispatch

    def record(self: HookDispatcher, hook_input: HookInput, **rest: Any) -> Any:
        if hook_input.event_name == event_name:
            contexts.append(dict(hook_input.context))
        return original(self, hook_input, **rest)

    HookDispatcher.dispatch = record  # type: ignore[method-assign]
    return contexts, original


def test_a_turn_fires_instructionsloaded_with_counts_and_no_content(
    workspace: Path,
) -> None:
    from raiker.hooks.dispatcher import HookDispatcher
    from raiker.models.contracts import ModelResponse

    (workspace / "secret-note.md").write_text("launch code 12345", encoding="utf-8")
    _write_hooks(workspace, "InstructionsLoaded")
    contexts, original = _hook_contexts("InstructionsLoaded")
    try:
        _orchestrator, session_id = _turn(
            workspace, [ModelResponse(text="Nothing to do.", finish_reason="stop")]
        )
    finally:
        HookDispatcher.dispatch = original  # type: ignore[method-assign]

    assert "hook_executed" in _hook_events(SQLiteStore(workspace), session_id)
    assert len(contexts) == 1
    context = contexts[0]
    # The bundle's own metadata-only payload, and nothing beyond it.
    assert "included_count" in context
    assert "source_types" in context
    assert "items" not in context
    assert "launch code" not in json.dumps(context)


def test_a_tool_batch_fires_posttoolbatch_once_with_its_shape(workspace: Path) -> None:
    from raiker.hooks.dispatcher import HookDispatcher
    from raiker.models.contracts import ModelResponse, ToolCallProposal

    (workspace / "README.md").write_text("hi", encoding="utf-8")
    _write_hooks(workspace, "PostToolBatch")
    contexts, original = _hook_contexts("PostToolBatch")
    try:
        _orchestrator, session_id = _turn(
            workspace,
            [
                ModelResponse(
                    text="",
                    tool_calls=[
                        ToolCallProposal(
                            call_id="call_ls",
                            tool_name="list_directory",
                            arguments={"path": "."},
                        ),
                        ToolCallProposal(
                            call_id="call_ls2",
                            tool_name="list_directory",
                            arguments={"path": "."},
                        ),
                    ],
                    finish_reason="tool_calls",
                ),
                ModelResponse(text="Here are the files.", finish_reason="stop"),
            ],
        )
    finally:
        HookDispatcher.dispatch = original  # type: ignore[method-assign]

    assert "hook_executed" in _hook_events(SQLiteStore(workspace), session_id)
    # One event for the one batch the model proposed, not one per call.
    assert len(contexts) == 1
    context = contexts[0]
    assert context["call_count"] == 2
    assert context["tool_names"] == ["list_directory", "list_directory"]
    assert context["executed_count"] == 2
    assert context["refused_count"] == 0
    assert context["parked_for_approval"] is False
    # Two independent reads are evaluated together, and the handler is told so.
    assert context["concurrent"] is True


def test_a_turn_with_no_tool_call_fires_no_posttoolbatch(workspace: Path) -> None:
    # The event describes a batch. A turn that proposed none has no batch to
    # report, and firing an empty one would make a handler that counts a turn's
    # work count turns instead.
    from raiker.hooks.dispatcher import HookDispatcher
    from raiker.models.contracts import ModelResponse

    _write_hooks(workspace, "PostToolBatch")
    contexts, original = _hook_contexts("PostToolBatch")
    try:
        _turn(workspace, [ModelResponse(text="No tools needed.", finish_reason="stop")])
    finally:
        HookDispatcher.dispatch = original  # type: ignore[method-assign]

    assert contexts == []


def test_an_activity_row_names_the_event_and_the_handler(workspace: Path) -> None:
    """The Hooks tab lists rows by verb and time; at twenty events that is not enough.

    An owner watching for one rule could not tell whether the row that just
    appeared was theirs. Both facts that answer it are already in the payload the
    row is built from, so the summary is a label rather than new data — and it is
    asserted through `DashboardService`, which is the object the page reads.
    """
    from raiker.notify.approval_notifier import notify_approval_pending

    _write_hooks(workspace, "Notification")
    store = SQLiteStore(workspace)
    notify_approval_pending(
        store,
        acting_principal_id=OWNER_PRINCIPAL,
        approval_id="apr_summary",
        tool_name="write_file",
    )

    activity = DashboardService(workspace).list_hooks(OWNER_PRINCIPAL)["activity"]
    summaries = {str(entry["summary"] or "") for entry in activity}

    # The verb is the row's tag, not part of the label.
    assert "Notification" in summaries
    assert "Notification · watch-Notification" in summaries
    # The label is built from the row's own metadata, never from a hook's input
    # or output — so it cannot carry the content those payloads exclude.
    assert not any("apr_summary" in summary for summary in summaries)
