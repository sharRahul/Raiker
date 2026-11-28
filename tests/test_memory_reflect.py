"""Reflect and consolidate (Hindsight's ideas, with no extra model call)."""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control.dashboard import DashboardService
from raiker.memory.reflect import REFLECT_GUIDANCE, consolidate, reflect
from raiker.memory.store import MemoryGovernance, get_memory, write_memory

OWNER = "principal_owner"


@pytest.fixture
def service(tmp_path: Path) -> DashboardService:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return DashboardService(ws)


def _remember(service: DashboardService, text: str, scope: str = "user") -> str:
    return write_memory(
        text, workspace_root=service.workspace_root, scope=scope, store=service.store, owner_principal_id=OWNER,
        governance=MemoryGovernance("e", "s", None, "human_correction", 1.0, 1.0, "until_forget", "approved", OWNER),
    ).memory_id


def test_reflect_collapses_near_copies_and_says_how_to_answer(service: DashboardService) -> None:
    older = _remember(service, "My flight to Lisbon leaves on Friday")
    newer = _remember(service, "My flight to Lisbon leaves Friday")
    _remember(service, "I prefer green tea")
    result = reflect(service.workspace_root, "when is my Lisbon flight", owner_principal_id=OWNER)

    assert result["status"] == "success"
    lisbon = [fact for fact in result["facts"] if "Lisbon" in fact["text"]]
    assert len(lisbon) == 1
    assert {lisbon[0]["memory_id"], *lisbon[0]["also_remembered_as"]} == {older, newer}
    assert result["guidance"] == REFLECT_GUIDANCE
    assert result["trust_label"] == "untrusted_memory_data"


def test_reflect_respects_incognito(service: DashboardService) -> None:
    _remember(service, "I prefer green tea")
    service.store.set_memory_incognito(True, OWNER)
    assert reflect(service.workspace_root, "tea", owner_principal_id=OWNER)["status"] == "withheld"


def test_consolidate_keeps_the_newest_copy_and_supersedes_the_rest(service: DashboardService) -> None:
    first = _remember(service, "I prefer green tea in the morning")
    second = _remember(service, "I prefer green tea in the morning!")
    other_scope = _remember(service, "I prefer green tea in the morning", scope="project:alpha")
    distinct = _remember(service, "I live near the river")

    result = consolidate(service.store, owner_principal_id=OWNER)
    assert result.merged == 1
    [(keeper, (retired,))] = result.groups
    assert {keeper, retired} == {first, second}

    def alive(memory_id: str) -> bool:
        # Recalled: superseded copies keep their history but leave recall.
        return service.store.get_active_approved_memory(memory_id, owner_principal_id=OWNER) is not None

    assert alive(keeper) and not alive(retired)
    assert get_memory(retired, workspace_root=service.workspace_root, owner_principal_id=OWNER) is not None
    # Another scope is another fact; different words are another fact.
    assert alive(other_scope) and alive(distinct)
    assert consolidate(service.store, owner_principal_id=OWNER).merged == 0
    assert service.consolidate_memories(OWNER).data == {"merged": 0, "groups": 0}


def test_the_agent_reaches_reflect_through_the_broker(service: DashboardService) -> None:
    from raiker.tools.broker import _memory_reflect

    _remember(service, "I prefer green tea")
    result = _memory_reflect(service.workspace_root, "what tea do I like", owner_principal_id=OWNER, scope=None)
    assert [fact["text"] for fact in result["facts"]] == ["I prefer green tea"]
