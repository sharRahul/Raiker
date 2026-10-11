"""§13.2 item 4 — Forget leaves a suppression tombstone.

"Forget excludes immediately and records a suppression tombstone so the same
source does not silently re-create it." A forgotten memory kept its row and its
content checksum but nothing compared new writes against it: the next turn that
said the same sentence was proposed again, and a model that wrote it back with
the memory tool re-created it outright. Restoring is the owner's explicit act.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control.dashboard import DashboardService
from raiker.memory.entity_extraction import propose_completed_turn_memories
from raiker.memory.store import MemoryGovernance, write_memory
from raiker.storage.sqlite import SQLiteStore
from tests.factories import governed_action

OWNER = "principal_owner"
FACT = "Rahul prefers tea"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


def _remember(ws: Path, store: SQLiteStore, text: str = FACT) -> str:
    return write_memory(
        text,
        workspace_root=ws,
        scope="project",
        governance=MemoryGovernance(
            source_event_id="evt_seed", source_session_id="sess_seed",
            source_turn_id="turn_seed", source_type="agent", confidence=0.9,
            trust_score=0.8, retention="until_forget", approval_state="approved",
            created_by="test",
        ),
        store=store,
        owner_principal_id=OWNER,
    ).memory_id


def _propose(store: SQLiteStore, turn: str, text: str = FACT) -> object:
    return propose_completed_turn_memories(
        store, owner_principal_id=OWNER, session_id="sess_1", turn_id=turn,
        source_event_id="evt_1", user_text=text, assistant_text="",
    )


def test_a_forgotten_sentence_is_not_proposed_again(workspace: Path) -> None:
    service = DashboardService(workspace)
    store = service.store
    memory_id = _remember(workspace, store)
    assert service.forget_memory_controlled(memory_id, OWNER).ok

    summary = _propose(store, "turn_later")

    assert summary.suppressed == 1 and summary.proposed == 0  # type: ignore[attr-defined]
    assert store.list_memory_candidates() == []


def test_a_sentence_never_forgotten_is_still_proposed(workspace: Path) -> None:
    store = SQLiteStore(workspace)
    summary = _propose(store, "turn_1", "Alex prefers coffee")
    assert summary.proposed == 1 and summary.suppressed == 0  # type: ignore[attr-defined]


def test_the_memory_tool_cannot_write_back_what_the_owner_forgot(workspace: Path) -> None:
    from raiker.runtime.authority.models import Principal, RiskLevelValue
    from raiker.runtime.executors.tier1_memory import MemoryWriteExecutor

    service = DashboardService(workspace)
    store = service.store
    memory_id = _remember(workspace, store)
    assert service.forget_memory_controlled(memory_id, OWNER).ok

    raw = store.get_principal(OWNER)
    assert raw is not None
    principal = Principal(**raw)
    executor = MemoryWriteExecutor(workspace, store)
    result = executor.execute(
        governed_action(
            "memory_write_execution", principal_id=OWNER, arguments={"text": FACT},
            risk_level=RiskLevelValue.MEDIUM,
        ),
        principal,
    )

    assert not result.ok and result.reason_code == "memory_forgotten_by_owner"
    # Something else is written as before.
    other = executor.execute(
        governed_action(
            "memory_write_execution", principal_id=OWNER,
            arguments={"text": "Alex prefers coffee"}, risk_level=RiskLevelValue.MEDIUM,
        ),
        principal,
    )
    assert other.ok, other.reason_code


def test_the_owner_adding_it_again_restores_it_and_lifts_the_suppression(workspace: Path) -> None:
    service = DashboardService(workspace)
    store = service.store
    memory_id = _remember(workspace, store)
    assert service.forget_memory_controlled(memory_id, OWNER).ok
    assert store.memory_text_forgotten(FACT, owner_principal_id=OWNER)

    _remember(workspace, store)  # the owner's explicit restore

    assert not store.memory_text_forgotten(FACT, owner_principal_id=OWNER)


def test_one_owners_forget_does_not_suppress_another_owners_memory(workspace: Path) -> None:
    service = DashboardService(workspace)
    memory_id = _remember(workspace, service.store)
    assert service.forget_memory_controlled(memory_id, OWNER).ok
    assert not service.store.memory_text_forgotten(FACT, owner_principal_id="principal_other")


def test_the_same_words_waiting_for_a_decision_are_proposed_once(workspace: Path) -> None:
    """Found by the 2026-10-11 live round: a Retry proposed its sentence again."""
    store = SQLiteStore(workspace)
    first = _propose(store, "turn_1", "Alex prefers coffee")
    again = _propose(store, "turn_retry", "Alex prefers coffee")
    assert first.proposed == 1  # type: ignore[attr-defined]
    assert again.proposed == 0 and again.already_present == 1  # type: ignore[attr-defined]
    assert len(store.list_memory_candidates(decision="deferred", owner_principal_id=OWNER)) == 1
