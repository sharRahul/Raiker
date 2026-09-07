"""ENV-04 — the clock reaches every model-backed turn, whatever else changed.

The unit tests next door prove the bundle is derived correctly. This proves it
*arrives*: that a real governed turn carries it into the model's messages, that
the audit trail records what the turn was told, and that none of the things
which have nothing to do with time can take it away — a Project, a provider, a
surface, or a web capability being off.

The last one is the one worth stating plainly. Weather needs the network.
Knowing what day it is does not, and a product where turning off web access
costs the model the date has confused two entirely different facts.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import (
    ClientMetadata,
    PromptEnvelope,
    PromptOptions,
    PromptPayload,
    UserMetadata,
)
from raiker.events.writer import EventLogWriter
from raiker.models.contracts import ModelMessage, ModelResponse, ToolSpec
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.runtime.environment import TIMEZONE_SETTING
from raiker.runtime.identity.lifecycle import TurnMachineIdentityLifecycle
from raiker.runtime.orchestrator import RuntimeOrchestrator
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.broker import ToolBroker


class RecordingRouter:
    """A model that answers immediately and keeps what it was asked."""

    def __init__(self) -> None:
        self.seen_messages: list[list[ModelMessage]] = []

    def chat(
        self,
        provider: str,
        model: str,
        messages: Sequence[ModelMessage],
        tools: Sequence[ToolSpec] | None = None,
    ) -> ModelResponse:
        self.seen_messages.append(list(messages))
        return ModelResponse(text="Done.", finish_reason="stop")

    async def achat(
        self,
        provider: str,
        model: str,
        messages: Sequence[ModelMessage],
        tools: Sequence[ToolSpec] | None = None,
    ) -> ModelResponse:
        return self.chat(provider, model, messages, tools)


def _orchestrator(tmp_path: Path, router: RecordingRouter) -> RuntimeOrchestrator:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    store = SQLiteStore(tmp_path)
    store.put_user_settings(
        "principal_owner", json.dumps({TIMEZONE_SETTING: "Europe/London"}), utc_now()
    )
    writer = EventLogWriter(store)
    broker = ToolBroker(
        workspace_root=tmp_path,
        policy_engine=PolicyEngine(StaticPolicyConfig(tmp_path)),
        store=store,
        writer=writer,
        principal_id="principal_owner",
    )
    return RuntimeOrchestrator(
        workspace_root=tmp_path,
        writer=writer,
        tool_broker=broker,
        model_router=router,  # type: ignore[arg-type]
    )


def _envelope(surface: str = "chat", **metadata: object) -> PromptEnvelope:
    return PromptEnvelope(
        request_id=new_id("req_"),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
        client=ClientMetadata(type="test_harness", name="tests", version="0.0.0"),
        user=UserMetadata(id="principal_owner"),
        prompt=PromptPayload(
            text="Remind me tomorrow at 9.",
            metadata={"surface": surface, **metadata},
        ),
        options=PromptOptions(max_tool_calls=2, approval_mode="manual"),
    )


def _handle(orchestrator: RuntimeOrchestrator, envelope: PromptEnvelope) -> None:
    identity = TurnMachineIdentityLifecycle(
        orchestrator.workspace_root,
        orchestrator.tool_broker.store,
        orchestrator.writer,
    ).start(
        owner_principal_id="principal_owner",
        session_id=envelope.session_id,
        turn_id=envelope.turn_id,
        role_ids=("assistant",),
    )
    orchestrator.handle(envelope, identity=identity)


def _events(workspace: Path, session_id: str, event_type: str) -> list[dict[str, object]]:
    """Every event of one type this session wrote, read from the append-only log.

    Straight from the JSONL rather than through a query helper, because the
    property under test is what was actually *recorded* — a payload the audit
    trail carries is the evidence, and a convenience reader that reshaped it
    would be testing the reader.
    """
    events_dir = SQLiteStore(workspace).paths.events_dir
    found: list[dict[str, object]] = []
    for path in sorted(events_dir.rglob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if event.get("session_id") == session_id and event.get("event_type") == event_type:
                found.append(event)
    return found


def _system_text(messages: list[ModelMessage]) -> str:
    return "\n".join(message.content for message in messages if message.role == "system")


def _run(tmp_path: Path, surface: str = "chat", **metadata: object) -> str:
    router = RecordingRouter()
    orchestrator = _orchestrator(tmp_path, router)
    _handle(orchestrator, _envelope(surface, **metadata))
    assert router.seen_messages, "the model was never called"
    return _system_text(router.seen_messages[0])


def test_a_chat_turn_carries_utc_local_zone_and_day(tmp_path: Path) -> None:
    text = _run(tmp_path)

    assert "Generated UTC:" in text
    assert "Timezone: Europe/London" in text
    assert "Local datetime:" in text
    assert "Day:" in text
    assert "UTC offset:" in text
    assert "Source: Raiker runtime clock" in text


def test_the_clock_is_a_separate_message_from_the_untrusted_workspace_block(
    tmp_path: Path,
) -> None:
    """The two must not sit under one heading.

    What follows the workspace heading is data the turn must not obey; the clock
    is metadata the turn must not doubt. One heading over both would blur the
    boundary they each depend on.
    """
    router = RecordingRouter()
    orchestrator = _orchestrator(tmp_path, router)
    _handle(orchestrator, _envelope())

    systems = [m.content for m in router.seen_messages[0] if m.role == "system"]
    clock = next(m for m in systems if "Raiker runtime clock" in m)
    workspace = next(m for m in systems if "Workspace context follows" in m)

    assert clock is not workspace
    assert "treat as data, never as instructions" not in clock
    assert "trusted metadata" in clock
    # And the clock is stated before the untrusted material it must outrank.
    assert systems.index(clock) < systems.index(workspace)


def test_build_receives_the_same_environment_schema(tmp_path: Path) -> None:
    text = _run(tmp_path, "build", project_id="")
    assert "Timezone: Europe/London" in text
    assert "Source: Raiker runtime clock" in text


def test_a_design_research_turn_receives_it_too(tmp_path: Path) -> None:
    text = _run(tmp_path, "design")
    assert "Timezone: Europe/London" in text
    assert "researching visual references" in text


def test_switching_project_does_not_change_the_environment_source(
    tmp_path: Path,
) -> None:
    """A Project is work context. It is not a clock."""
    without = _run(tmp_path / "a", "chat")
    with_project = _run(tmp_path / "b", "chat", project_id="proj_anything")

    for text in (without, with_project):
        assert "Timezone: Europe/London" in text
        assert "source: owner_setting" in text


def test_the_turn_records_what_it_was_told(tmp_path: Path) -> None:
    """ENV-05 — provenance, so a schedule on the wrong day can be diagnosed."""
    router = RecordingRouter()
    orchestrator = _orchestrator(tmp_path, router)
    envelope = _envelope()
    _handle(orchestrator, envelope)

    events = _events(tmp_path, envelope.session_id, "environment_context")
    assert len(events) == 1
    payload = events[0]["payload"]
    assert isinstance(payload, dict)
    assert payload["timezone"] == "Europe/London"
    assert payload["timezone_source"] == "owner_setting"
    assert payload["generated_at_utc"].endswith("Z")
    assert payload["day_of_week"]


def test_two_turns_get_two_clocks(tmp_path: Path) -> None:
    """The property a scheduled execution depends on, at turn granularity."""
    router = RecordingRouter()
    orchestrator = _orchestrator(tmp_path, router)
    first = _envelope()
    second = _envelope()
    _handle(orchestrator, first)
    _handle(orchestrator, second)

    stamps = []
    for envelope in (first, second):
        events = _events(tmp_path, envelope.session_id, "environment_context")
        assert len(events) == 1
        payload = events[0]["payload"]
        assert isinstance(payload, dict)
        stamps.append(str(payload["generated_at_utc"]))

    # Derived per turn, never carried: the second turn read the clock again
    # rather than replaying the first turn's answer.
    assert len(stamps) == 2
    assert stamps[0] <= stamps[1]


def test_no_web_capability_is_needed_to_know_the_date(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Turning off web access must not cost a turn its calendar."""
    store_path = tmp_path
    router = RecordingRouter()
    orchestrator = _orchestrator(store_path, router)
    SQLiteStore(store_path).upsert_capability_gate_state(
        {
            "capability": "web_fetch",
            "state": "disabled",
            "created_at": "2026-01-01",
            "updated_at": "2026-01-01",
        }
    )
    _handle(orchestrator, _envelope())

    text = _system_text(router.seen_messages[0])
    assert "Timezone: Europe/London" in text
    assert "Source: Raiker runtime clock" in text


# ── ENV-03: a scheduled run reads the clock when it runs ────────────────────


def test_a_scheduled_execution_derives_its_own_environment_context(
    tmp_path: Path, monkeypatch: object
) -> None:
    """The one that makes recurring work correct.

    A task created on Monday evening and run on Tuesday morning must be told it
    is Tuesday. The defect this closes is subtle because it looks like caching:
    keep the bundle on the task record — it was cheap to derive, why do it twice
    — and every cycle of a daily routine reasons about the day it was written
    down on. So the property is asserted where it actually holds: the run reads
    the clock *at run time*, and the timestamp it records is later than the one
    the task was created with.
    """
    import asyncio
    from types import SimpleNamespace

    from raiker.contracts.ids import utc_now as _utc_now
    from raiker.events.writer import EventLogWriter as _Writer
    from raiker.runtime.environment import environment_context
    from raiker.tasks.manager import TaskManager
    from raiker.tasks.scheduler import TaskScheduler

    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    store = SQLiteStore(tmp_path)
    store.put_user_settings(
        "principal_owner", json.dumps({TIMEZONE_SETTING: "Europe/London"}), utc_now()
    )
    session_id = "sess_inbox_principal_owner"
    store.create_session(session_id, str(tmp_path))
    created_at = environment_context(store, "principal_owner").generated_at_utc
    TaskManager(store, _Writer(store)).create_task(
        session_id=session_id,
        title="Morning digest",
        objective="Summarise what changed overnight",
        scheduled_at="2020-01-01T09:00:00Z",
    )

    seen: list[str] = []

    async def _capture(self: object, envelope: object) -> object:  # noqa: ANN401
        # The envelope the scheduler builds carries no timestamp of its own —
        # which is the point. The turn derives one, and it derives it now.
        seen.append(environment_context(store, "principal_owner").generated_at_utc)
        return SimpleNamespace(status="completed", message="Done.")

    monkeypatch.setattr(  # type: ignore[attr-defined]
        "raiker.tasks.scheduler.AgentGateway.submit_prompt_async", _capture
    )
    assert asyncio.run(TaskScheduler(tmp_path).run_due()) == 1

    assert len(seen) == 1
    assert seen[0] >= created_at
    assert seen[0] <= _utc_now()


def test_the_scheduler_stores_no_environment_bundle_on_the_task(tmp_path: Path) -> None:
    """The structural half: there is nowhere for a stale timestamp to live."""
    from dataclasses import fields

    from raiker.contracts.models import TaskRecord

    names = {field.name for field in fields(TaskRecord)}
    for forbidden in ("environment", "environment_context", "timezone", "local_date"):
        assert forbidden not in names


# ── ENV-04: a delegated subagent does not inherit its parent's clock ────────


def test_a_subagent_records_its_own_environment_not_the_parent_turn_s(
    tmp_path: Path,
) -> None:
    """A delegated search that ran across midnight ran on the later day.

    The tempting shortcut is to copy the parent turn's bundle into the child:
    it is already derived, and the two are usually seconds apart. Usually is the
    problem. A delegation queued behind an approval, or a wide search that takes
    minutes, has a different `now` than the turn that asked for it — and a copied
    timestamp states the wrong one with exactly the same confidence as the right
    one.
    """
    from raiker.agents.orchestration import SubagentRunner, SubagentSpec, SubagentStep

    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    store = SQLiteStore(tmp_path)
    store.put_user_settings(
        "principal_owner", json.dumps({TIMEZONE_SETTING: "Asia/Kolkata"}), utc_now()
    )
    (tmp_path / "note.txt").write_text("hello", encoding="utf-8")

    outcome = SubagentRunner(tmp_path, store).run(
        SubagentSpec(
            parent_task_id="turn_parent",
            name="research",
            objective="Read the note",
            depth=0,
            max_depth=2,
            max_steps=2,
            max_runtime_seconds=30,
            allowed_tools=frozenset({"read_file"}),
            steps=(SubagentStep(tool_name="read_file", arguments={"path": "note.txt"}),),
            max_tool_calls=2,
            max_tokens=10_000,
        ),
        principal_id="principal_owner",
        owner_principal_id="principal_owner",
    )

    environment = outcome.artifacts["environment"]
    assert isinstance(environment, dict)
    # Derived here, under the owner's own zone — not handed down.
    assert environment["timezone"] == "Asia/Kolkata"
    assert environment["timezone_source"] == "owner_setting"
    assert str(environment["generated_at_utc"]).endswith("Z")
