from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path

import pytest

from raiker.contracts.models import (
    ClientMetadata,
    PromptEnvelope,
    PromptOptions,
    PromptPayload,
    UserMetadata,
)
from raiker.control.dashboard import DashboardService
from raiker.events.writer import EventLogWriter
from raiker.models.contracts import ModelMessage, ModelResponse, ReasoningOptions, ToolSpec
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.runtime.conversation_compaction import (
    ContextBudgetPlanner,
    ContextCompactionRecord,
    ContextCompactionStore,
    compacted_conversation_messages,
    estimate_message_tokens,
    protected_context,
)
from raiker.runtime.model_facts_store import ModelFactsStore
from raiker.runtime.orchestrator import RuntimeOrchestrator
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.broker import ToolBroker


@pytest.fixture()
def store(tmp_path: Path) -> SQLiteStore:
    value = SQLiteStore(tmp_path)
    value.bootstrap()
    value.create_session("s1", str(tmp_path))
    return value


def _turn(store: SQLiteStore, index: int, *, chars: int = 80) -> None:
    turn_id = f"turn_{index}"
    store.insert_turn("s1", turn_id, f"u{index}" + "u" * chars)
    store.complete_turn(turn_id, "completed", f"a{index}" + "a" * chars)
    with store.connect() as connection:
        connection.execute(
            "UPDATE turns SET created_at = ? WHERE turn_id = ?",
            (f"2026-08-{index + 1:02d}T12:00:00Z", turn_id),
        )


def test_estimator_and_planner_trigger_at_ninety_percent(store: SQLiteStore) -> None:
    assert estimate_message_tokens([ModelMessage("system", "x" * 360)]) == 90
    for index in range(4):
        _turn(store, index, chars=100)

    plan = ContextBudgetPlanner().plan(
        store=store,
        owner_principal_id="p1",
        session_id="s1",
        capacity_tokens=200,
        fixed_messages=[ModelMessage("system", "x" * 200)],
        current_prompt="z" * 100,
        latest_compaction=None,
    )
    assert plan.threshold_tokens == 180
    assert plan.estimated_tokens >= plan.threshold_tokens
    assert plan.should_compact is True
    assert [row["turn_id"] for row in plan.eligible_turns] == ["turn_0", "turn_1"]
    assert plan.compact_through_turn_id == "turn_1"


def test_unknown_capacity_never_claims_compaction(store: SQLiteStore) -> None:
    _turn(store, 0, chars=500)
    plan = ContextBudgetPlanner().plan(
        store=store,
        owner_principal_id="p1",
        session_id="s1",
        capacity_tokens=None,
        fixed_messages=[],
        current_prompt="next",
        latest_compaction=None,
    )
    assert plan.should_compact is False
    assert plan.threshold_tokens is None


def test_completed_compaction_is_owner_scoped_and_does_not_change_transcript(
    store: SQLiteStore,
) -> None:
    _turn(store, 0)
    before = store.list_turns("s1")
    record = ContextCompactionRecord(
        compaction_id="compact_1",
        owner_principal_id="p1",
        session_id="s1",
        through_turn_id="turn_0",
        summary_text="Earlier summary",
        protected_context="Protected state",
        source_turn_count=1,
        estimated_input_tokens_before=100,
        estimated_summary_tokens=10,
        provider="openai",
        model="gpt-5",
        status="completed",
        reason_code=None,
        created_at="2026-08-11T12:00:00Z",
    )
    compactions = ContextCompactionStore(store)
    compactions.record_success(record)

    assert compactions.latest("p1", "s1") == record
    assert compactions.latest("p2", "s1") is None
    assert store.list_turns("s1") == before


def test_failed_record_never_becomes_the_active_summary(store: SQLiteStore) -> None:
    compactions = ContextCompactionStore(store)
    completed = ContextCompactionRecord(
        "compact_ok", "p1", "s1", "turn_1", "Good summary", "", 2, 200, 20,
        "anthropic", "claude", "completed", None, "2026-08-10T12:00:00Z",
    )
    failed = ContextCompactionRecord(
        "compact_fail", "p1", "s1", None, None, "", 0, 300, 0,
        "anthropic", "claude", "failed", "provider_unavailable", "2026-08-11T12:00:00Z",
    )
    compactions.record_success(completed)
    compactions.record_failure(failed)
    assert compactions.latest("p1", "s1") == failed
    assert compactions.active("p1", "s1") == completed


def test_compacted_replay_still_bounds_new_history(store: SQLiteStore) -> None:
    for index in range(4):
        _turn(store, index, chars=40)
    record = ContextCompactionRecord(
        "compact_ok", "p1", "s1", "turn_0", "Earlier summary", "", 1, 100, 5,
        "ollama", "local", "completed", None, "2026-08-11T12:00:00Z",
    )
    messages = compacted_conversation_messages(store, "s1", record, char_budget=100)
    assert messages[0].role == "system"
    assert [message.content[:2] for message in messages[1:]] == ["u3", "a3"]


def test_protected_context_serializes_ids_not_source_content(store: SQLiteStore) -> None:
    store.save_agent_plan(
        session_id="s1",
        principal_id="p1",
        turn_id="turn_plan",
        steps_json='[{"id":"step_1","text":"Keep this","status":"pending"}]',
    )
    text = protected_context(store, "p1", "s1")
    assert "turn_plan" in text
    assert "step_1" in text
    assert "Protected runtime state" in text


class _RecordingCompactionRouter:
    def __init__(self) -> None:
        self.calls: list[tuple[list[ModelMessage], Sequence[ToolSpec] | None, object]] = []

    async def achat(
        self,
        provider: str,
        model: str,
        messages: Sequence[ModelMessage],
        tools: Sequence[ToolSpec] | None = None,
        *,
        reasoning: ReasoningOptions | None = None,
    ) -> ModelResponse:
        del provider, model
        self.calls.append((list(messages), tools, reasoning))
        if reasoning == ReasoningOptions(enabled=False):
            return ModelResponse(
                text="The owner asked to retain the earlier numbered facts.",
                usage={"input_tokens": 80, "output_tokens": 12},
            )
        return ModelResponse(
            text="The compacted context is available.",
            usage={"input_tokens": 90, "output_tokens": 8},
        )


def test_runtime_compacts_as_a_separate_tool_free_accounted_request(
    store: SQLiteStore, tmp_path: Path
) -> None:
    for index in range(4):
        _turn(store, index, chars=1_200)
    ModelFactsStore(store).set_owner_context_capacity(
        "p1",
        "test-provider",
        "test-model",
        tokens=1_024,
        endpoint_identity="test-endpoint",
        reason="test capacity",
        recorded_by="test",
    )
    writer = EventLogWriter(store)
    router = _RecordingCompactionRouter()
    broker = ToolBroker(
        workspace_root=tmp_path,
        policy_engine=PolicyEngine(StaticPolicyConfig(tmp_path)),
        store=store,
        writer=writer,
        principal_id="p1",
    )
    runtime = RuntimeOrchestrator(
        workspace_root=tmp_path,
        writer=writer,
        tool_broker=broker,
        model_router=router,  # type: ignore[arg-type]
        default_provider=("test-provider", "test-model"),
    )
    envelope = PromptEnvelope(
        request_id="req_compact",
        session_id="s1",
        turn_id="turn_current",
        client=ClientMetadata("test_harness", "tests", "1"),
        user=UserMetadata("p1"),
        prompt=PromptPayload("What did we decide?"),
        options=PromptOptions(),
    )

    response = asyncio.run(runtime.ahandle(envelope))

    assert response.message == "The compacted context is available."
    assert len(router.calls) == 2
    compaction_messages, compaction_tools, compaction_reasoning = router.calls[0]
    assert compaction_tools is None
    assert compaction_reasoning == ReasoningOptions(enabled=False)
    assert "Conversation to compact" in compaction_messages[-1].content
    assert any("Earlier conversation was compacted" in message.content for message in router.calls[1][0])
    with store.connect() as connection:
        request_kinds = [
            str(row["request_kind"])
            for row in connection.execute(
                "SELECT request_kind FROM model_usage_ledger ORDER BY rowid"
            ).fetchall()
        ]
    assert request_kinds == ["compaction", "turn"]
    assert ContextCompactionStore(store).active("p1", "s1") is not None
    latest_view = DashboardService(tmp_path).get_context_usage("s1", "p1")
    assert latest_view.latest_compaction is not None
    assert latest_view.latest_compaction["status"] == "completed"
    assert latest_view.latest_compaction["source_turn_count"] == 2
