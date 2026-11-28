"""Prompt layout for cache reuse: stable head, history, per-turn tail.

A provider reuses a cached prefix only up to the first byte that differs. The
memory brief is frozen per conversation (Hermes Agent) and the clock and
workspace context come after the history, so a long chat stays cheap and fast;
forgetting a memory still takes effect on the very next turn.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.memory.store import (
    MemoryForgetGovernance,
    MemoryGovernance,
    forget_memory,
    write_memory,
)
from raiker.models.contracts import ModelMessage
from raiker.models.providers.anthropic_messages import _to_anthropic_messages
from raiker.runtime import orchestrator as orch
from raiker.storage.sqlite import SQLiteStore

OWNER = "principal_owner"


def test_turn_context_travels_in_the_user_turn_and_the_system_prompt_stays_fixed() -> None:
    def turn(history: list[ModelMessage], clock: str) -> tuple[str, list[dict[str, Any]]]:
        return _to_anthropic_messages([
            ModelMessage(role="system", content="rules"),
            *history,
            ModelMessage(role="system", content=f"clock {clock}", turn_context=True),
            ModelMessage(role="user", content="next question"),
        ])

    first_system, first = turn([], "09:00")
    history = [ModelMessage(role="user", content="hi"), ModelMessage(role="assistant", content="hello")]
    second_system, second = turn(history, "09:05")
    assert first_system == second_system == "rules"
    assert "clock 09:00" in first[0]["content"][0]["text"]
    # The context joins the new user turn; the history before it is untouched
    # and carries the cache breakpoint.
    assert second[1]["content"][-1].get("_cache_breakpoint") is True
    assert [block["text"] for block in second[2]["content"]] == [
        "<turn_context>\nclock 09:05\n</turn_context>", "next question",
    ]


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    root = tmp_path / "ws"
    root.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=root)
    return root


@pytest.fixture
def store(ws: Path) -> SQLiteStore:
    return SQLiteStore(ws)


def _remember(store: SQLiteStore, ws: Path, text: str) -> str:
    return write_memory(
        text, workspace_root=ws, scope="user", store=store, owner_principal_id=OWNER,
        governance=MemoryGovernance("e", "s", None, "human_correction", 1.0, 1.0, "until_forget", "approved", OWNER),
    ).memory_id


def _bundle(content: str, ids: list[str]) -> Any:
    item = SimpleNamespace(
        source=SimpleNamespace(source_type="memory_brief", trust_level="untrusted_external"),
        title="Memory brief", content=content, metadata={"memory_ids": ids},
    )
    return SimpleNamespace(included_items=[item])


def _frozen(store: SQLiteStore, bundle: Any, session: str = "sess_1") -> str | None:
    fake = SimpleNamespace(tool_broker=SimpleNamespace(store=store), _source_owner=lambda _e: OWNER)
    envelope = SimpleNamespace(session_id=session)
    return orch.RuntimeOrchestrator._frozen_memory_brief(fake, envelope, bundle)  # type: ignore[arg-type]


def test_the_brief_is_frozen_until_a_memory_in_it_is_forgotten(store: SQLiteStore, ws: Path) -> None:
    orch._BRIEF_SNAPSHOTS.clear()
    tea = _remember(store, ws, "I prefer green tea")
    first = _frozen(store, _bundle("- tea", [tea]))
    # A memory kept mid-conversation changes the gatherer's brief, not the snapshot.
    coffee = _remember(store, ws, "I drink coffee at 8")
    assert _frozen(store, _bundle("- tea\n- coffee", [tea, coffee])) == first

    forget_memory(
        tea, workspace_root=ws, store=store, owner_principal_id=OWNER,
        governance=MemoryForgetGovernance("e", "s", None, "human_forget", OWNER),
    )
    rebuilt = _frozen(store, _bundle("- coffee", [coffee]))
    assert rebuilt is not None and "tea" not in rebuilt and "coffee" in rebuilt


def test_memory_off_drops_the_snapshot_the_same_turn(store: SQLiteStore, ws: Path) -> None:
    orch._BRIEF_SNAPSHOTS.clear()
    tea = _remember(store, ws, "I prefer green tea")
    assert _frozen(store, _bundle("- tea", [tea])) is not None
    empty = SimpleNamespace(included_items=[])
    assert _frozen(store, empty) is None
    assert orch._BRIEF_SNAPSHOTS == {}


def test_local_templates_never_see_a_system_message_mid_conversation() -> None:
    from raiker.models.contracts import fold_turn_context

    folded = fold_turn_context([
        ModelMessage(role="system", content="rules"),
        ModelMessage(role="user", content="hi"),
        ModelMessage(role="assistant", content="hello"),
        ModelMessage(role="system", content="clock 09:05", turn_context=True),
        ModelMessage(role="user", content="next"),
    ])
    assert [message.role for message in folded] == ["system", "user", "assistant", "user"]
    assert folded[-1].content == "<turn_context>\nclock 09:05\n</turn_context>\n\nnext"
    # Before the conversation starts, turn context stays a system message.
    first = fold_turn_context([
        ModelMessage(role="system", content="rules"),
        ModelMessage(role="system", content="clock", turn_context=True),
        ModelMessage(role="user", content="hi"),
    ])
    assert [message.role for message in first] == ["system", "system", "user"]
