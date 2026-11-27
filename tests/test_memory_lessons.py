"""RU-12 — Raiker remembers its own work.

A lesson comes from the task's own command records, is proposed for review
like any memory, and once kept is recalled on the next task in the same
project only.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control.dashboard import DashboardService
from raiker.memory.brief import build_memory_brief
from raiker.memory.lessons import LESSON_ROLE, lessons_from_runs, propose_turn_lessons

OWNER = "principal_owner"


@pytest.fixture
def service(tmp_path: Path) -> DashboardService:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return DashboardService(ws)


def _run(command: str, exit_code: int | None, at: str) -> dict[str, object]:
    return {"command": command, "exit_code": exit_code, "created_at": at}


TRIAL_AND_ERROR = [
    _run("npm test", 1, "2026-11-27T10:00:00Z"),
    _run("npm test -- --runInBand", 0, "2026-11-27T10:01:00Z"),
]


def test_a_failure_then_a_passing_variant_is_a_lesson() -> None:
    assert lessons_from_runs(TRIAL_AND_ERROR) == [
        "In this project, run `npm test -- --runInBand` instead of `npm test`."
    ]


@pytest.mark.parametrize(
    "runs",
    [
        # Nothing failed.
        [_run("npm test", 0, "1"), _run("npm test -- --runInBand", 0, "2")],
        # The pass came first: no trial and error.
        [_run("npm test -- --runInBand", 0, "1"), _run("npm test", 1, "2")],
        # A different program is another task, not a fix.
        [_run("npm test", 1, "1"), _run("yarn test", 0, "2")],
        # Same program, different subcommand.
        [_run("npm test", 1, "1"), _run("npm install", 0, "2")],
        # Rerunning the same command that then passed is flakiness, not a lesson.
        [_run("pytest", 1, "1"), _run("pytest", 0, "2")],
        # A command still running or stopped has no exit to learn from.
        [_run("pytest", None, "1"), _run("pytest -x", 0, "2")],
    ],
)
def test_no_lesson_without_a_fix_for_the_same_command(runs: list[dict[str, object]]) -> None:
    assert lessons_from_runs(runs) == []


def test_one_lesson_per_task() -> None:
    runs = [
        *TRIAL_AND_ERROR,
        _run("pytest", 2, "2026-11-27T10:02:00Z"),
        _run("pytest -p no:cacheprovider", 0, "2026-11-27T10:03:00Z"),
    ]
    assert len(lessons_from_runs(runs)) == 1


def _propose(service: DashboardService, project: str, turn: str) -> None:
    propose_turn_lessons(
        service.store,
        owner_principal_id=OWNER,
        project_id=project,
        session_id="sess_1",
        turn_id=turn,
        source_event_id="evt_1",
        runs=TRIAL_AND_ERROR,
    )


def test_a_kept_lesson_is_recalled_in_its_project_only(service: DashboardService) -> None:
    _propose(service, "alpha", "turn_1")
    [proposal] = service.list_memory_proposals(OWNER)
    assert proposal["source_role"] == LESSON_ROLE
    assert proposal["scope"] == "project:alpha"
    assert proposal["memory_type"] == "lesson"
    # Nothing is recalled before the owner keeps it.
    assert build_memory_brief(service.store, owner_principal_id=OWNER, project_id="alpha").items == ()

    kept = service.decide_memory_proposal(
        str(proposal["candidate_id"]),
        decision="approved",
        edited_text=None,
        reason=None,
        expected_decision="deferred",
        acting_principal_id=OWNER,
    )
    assert kept.ok

    next_task = build_memory_brief(service.store, owner_principal_id=OWNER, project_id="alpha")
    assert ["--runInBand" in item.text for item in next_task.items] == [True]
    other_project = build_memory_brief(service.store, owner_principal_id=OWNER, project_id="beta")
    assert other_project.items == ()


def test_the_same_lesson_is_not_proposed_twice(service: DashboardService) -> None:
    _propose(service, "alpha", "turn_1")
    _propose(service, "alpha", "turn_2")
    assert len(service.list_memory_proposals(OWNER)) == 1


def test_a_finished_project_turn_files_its_lesson(
    service: DashboardService, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from raiker.execution.commands.store import CommandStore
    from raiker.gateway.agent_gateway import AgentGateway

    runs = [
        SimpleNamespace(turn_id="turn_9", safe_display=str(r["command"]),
                        exit_code=r["exit_code"], created_at=str(r["created_at"]))
        for r in TRIAL_AND_ERROR
    ]
    monkeypatch.setattr(CommandStore, "list_runs", lambda self, owner, **_: runs)
    events: list[object] = []
    gateway = SimpleNamespace(
        store=service.store,
        owner_principal_id=OWNER,
        writer=SimpleNamespace(last_event_id="evt_9", append=events.append),
    )
    service.store.load_session = lambda _sid: {"project_id": "alpha"}  # type: ignore[method-assign,assignment]
    envelope = SimpleNamespace(
        session_id="sess_9", turn_id="turn_9", client=None,
        prompt=SimpleNamespace(metadata={}),
    )
    AgentGateway._propose_turn_lesson(gateway, envelope)  # type: ignore[arg-type]

    [proposal] = service.list_memory_proposals(OWNER)
    assert (proposal["source_turn_id"], proposal["scope"]) == ("turn_9", "project:alpha")
    assert len(events) == 1


def test_a_file_change_between_the_runs_is_no_lesson() -> None:
    # The fix may be what made the second run pass, not the flag.
    runs = [_run("pytest a.py", 1, "2026-11-27T10:00:00Z"), _run("pytest a.py -x", 0, "2026-11-27T10:02:00Z")]
    assert lessons_from_runs(runs, changes=["2026-11-27T10:01:00Z"]) == []
    assert lessons_from_runs(runs, changes=["2026-11-27T09:00:00Z"]) != []


def _gateway(service: DashboardService, monkeypatch: pytest.MonkeyPatch, session: dict[str, object]) -> object:
    from types import SimpleNamespace

    from raiker.execution.commands.store import CommandStore

    runs = [
        SimpleNamespace(turn_id="turn_9", safe_display=str(r["command"]),
                        exit_code=r["exit_code"], created_at=str(r["created_at"]))
        for r in TRIAL_AND_ERROR
    ]
    monkeypatch.setattr(CommandStore, "list_runs", lambda self, owner, **_: runs)
    service.store.load_session = lambda _sid: session  # type: ignore[method-assign,assignment]
    return SimpleNamespace(
        store=service.store, owner_principal_id=OWNER,
        writer=SimpleNamespace(last_event_id="evt_9", append=lambda _e: None),
    )



def _envelope() -> object:
    from types import SimpleNamespace

    return SimpleNamespace(session_id="sess_9", turn_id="turn_9", client=None,
                           prompt=SimpleNamespace(metadata={}))


def test_incognito_files_no_proposal_or_lesson(
    service: DashboardService, monkeypatch: pytest.MonkeyPatch
) -> None:
    from raiker.gateway.agent_gateway import AgentGateway

    gateway = _gateway(service, monkeypatch, {"project_id": "alpha"})
    assert AgentGateway._memory_proposals_withheld(gateway, _envelope()) is False  # type: ignore[arg-type]
    monkeypatch.setattr(type(service.store), "is_memory_incognito", lambda self, owner=None: True)
    assert AgentGateway._memory_proposals_withheld(gateway, _envelope()) is True  # type: ignore[arg-type]


def test_a_conversation_kept_incognito_files_nothing(
    service: DashboardService, monkeypatch: pytest.MonkeyPatch
) -> None:
    import raiker.goals.store as goals_store
    from raiker.gateway.agent_gateway import AgentGateway

    gateway = _gateway(service, monkeypatch, {"project_id": "alpha"})
    monkeypatch.setattr(goals_store, "session_memory_withheld", lambda _s, _sid: "incognito")
    assert AgentGateway._memory_proposals_withheld(gateway, _envelope()) is True  # type: ignore[arg-type]


def test_a_project_with_memory_off_keeps_no_lesson(
    service: DashboardService, monkeypatch: pytest.MonkeyPatch
) -> None:
    from raiker.gateway.agent_gateway import AgentGateway

    gateway = _gateway(service, monkeypatch, {"project_id": "alpha"})
    monkeypatch.setattr(
        type(service.store), "load_project",
        lambda self, pid, user_id=None: {"project_id": pid, "memory_enabled": 0},
    )
    AgentGateway._propose_turn_lesson(gateway, _envelope())  # type: ignore[arg-type]
    assert service.list_memory_proposals(OWNER) == []
