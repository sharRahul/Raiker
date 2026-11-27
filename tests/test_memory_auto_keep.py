"""Almost no approvals: Raiker keeps what it can trust and shows Undo.

Kept without asking: the owner's own words and evidence-backed lessons. Still
asked: the model's sentences, personal identifiers, a lesson that would change a
declared check, and everything when the owner turned on Ask before remembering.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import utc_now
from raiker.control.dashboard import DashboardService
from raiker.memory.auto_keep import auto_keep_decision, auto_keep_turn, remembered_in_session
from raiker.memory.brief import build_memory_brief
from raiker.memory.candidates import MemoryCandidate
from raiker.memory.lessons import (
    evidence_holds,
    lesson_for_command,
    propose_turn_lessons,
)

OWNER = "principal_owner"


@pytest.fixture
def service(tmp_path: Path) -> DashboardService:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return DashboardService(ws)


def _file(service: DashboardService, text: str, role: str, turn: str = "turn_1") -> None:
    service.store.insert_memory_candidate(
        MemoryCandidate(
            candidate_id=f"memcand_{role}_{turn}_{abs(hash(text)) % 10_000}",
            source_event_id="evt_1", memory_type="preference", scope="user", text=text,
            sensitivity="unknown", confidence=0.9, decision="deferred", created_at=utc_now(),
            source_session_id="sess_1", source_turn_id=turn, source_role=role,
            extractor_version=f"test-{role}",
        ),
        owner_principal_id=OWNER,
    )


def _keep(service: DashboardService, turn: str = "turn_1") -> object:
    return auto_keep_turn(
        service.store, workspace_root=service.workspace_root, owner_principal_id=OWNER,
        session_id="sess_1", turn_id=turn,
    )


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        ({"text": "I prefer green tea", "source_role": "user"}, "keep"),
        ({"text": "Run x instead", "source_role": "raiker_lesson", "memory_type": "lesson"}, "keep"),
        ({"text": "Dr. Okafor is meticulous", "source_role": "assistant"}, "ask"),
        ({"text": "My email is a@b.co", "source_role": "user"}, "ask"),
        ({"text": "x", "source_role": "raiker_lesson", "memory_type": "check_fix"}, "ask"),
        ({"text": "password: hunter2hunter2", "source_role": "user"}, "never"),
    ],
)
def test_what_is_kept_without_asking(candidate: dict[str, object], expected: str) -> None:
    assert auto_keep_decision(candidate, asks_first=False) == expected


def test_ask_before_remembering_asks_for_everything() -> None:
    assert auto_keep_decision({"text": "I prefer tea", "source_role": "user"}, asks_first=True) == "ask"


def test_the_owners_words_are_kept_and_offered_for_undo(service: DashboardService) -> None:
    _file(service, "I prefer green tea", "user")
    _file(service, "Green tea is calming", "assistant")
    summary = _keep(service)

    assert len(summary.kept) == 1 and summary.asked == 1  # type: ignore[attr-defined]
    # The model's sentence still waits for Keep.
    assert [row["source_role"] for row in service.list_memory_proposals(OWNER)] == ["assistant"]
    remembered = remembered_in_session(
        service.store, workspace_root=service.workspace_root, owner_principal_id=OWNER, session_id="sess_1"
    )
    assert [(item["text"], item["source_turn_id"]) for item in remembered] == [("I prefer green tea", "turn_1")]
    brief = build_memory_brief(service.store, owner_principal_id=OWNER, project_id=None)
    assert [item.text for item in brief.items] == ["I prefer green tea"]

    # Undo is Forget: it leaves the conversation's remembered list.
    assert service.forget_memory_controlled(remembered[0]["memory_id"], OWNER).ok
    assert remembered_in_session(
        service.store, workspace_root=service.workspace_root, owner_principal_id=OWNER, session_id="sess_1"
    ) == []


def test_a_repeat_is_closed_not_kept_twice(service: DashboardService) -> None:
    _file(service, "I prefer green tea", "user", "turn_1")
    _keep(service, "turn_1")
    _file(service, "I prefer green tea", "user", "turn_2")
    summary = _keep(service, "turn_2")
    assert summary.kept == () and summary.duplicates == 1  # type: ignore[attr-defined]
    assert service.list_memory_proposals(OWNER) == []


def test_the_setting_turns_asking_back_on(service: DashboardService) -> None:
    assert service.get_memory_settings(OWNER).ask_before_remembering is False
    assert service.set_ask_before_remembering(True, OWNER).ok
    assert service.get_memory_settings(OWNER).ask_before_remembering is True
    _file(service, "I prefer green tea", "user")
    assert _keep(service).kept == ()  # type: ignore[attr-defined]
    assert len(service.list_memory_proposals(OWNER)) == 1


def _run(command: str, exit_code: int | None, at: str) -> dict[str, object]:
    return {"command": command, "exit_code": exit_code, "created_at": at}


def test_evidence_allows_a_different_program() -> None:
    # `pnpm` fixing `npm` is the lesson the same-program rule could never see.
    runs = [_run("npm install", 1, "1"), _run("pnpm install", 0, "2")]
    assert evidence_holds(runs, [], failed="npm install", passed="pnpm install")
    assert not evidence_holds(runs, [], failed="pnpm install", passed="npm install")
    assert not evidence_holds(runs, ["1"], failed="npm install", passed="pnpm install")
    assert not evidence_holds(runs, [], failed="npm ci", passed="pnpm install")


def _project(service: DashboardService, checks: list[str]) -> None:
    service.store.create_project("alpha", "Alpha", "alpha")
    service.store.save_project_context(
        "alpha", instructions="", attachment_ids=[], memory_mode="enabled", checks=checks
    )


def test_a_lesson_about_a_declared_check_fixes_the_check_on_keep(service: DashboardService) -> None:
    _project(service, ["npm test", "npm run lint"])
    propose_turn_lessons(
        service.store, owner_principal_id=OWNER, project_id="alpha", session_id="sess_1",
        turn_id="turn_1", source_event_id="evt_1",
        runs=[_run("npm test", 1, "1"), _run("npm test -- --runInBand", 0, "2")],
    )
    assert _keep(service).kept == ()  # type: ignore[attr-defined]
    [proposal] = service.list_memory_proposals(OWNER)
    assert proposal["memory_type"] == "check_fix"
    assert service.decide_memory_proposal(
        str(proposal["candidate_id"]), decision="approved", edited_text=None, reason=None,
        expected_decision="deferred", acting_principal_id=OWNER,
    ).ok
    assert service.store.load_project_context("alpha")["checks"] == ["npm test -- --runInBand", "npm run lint"]


def test_a_kept_lesson_comes_back_when_its_command_fails_and_retires_when_stale(
    service: DashboardService,
) -> None:
    propose_turn_lessons(
        service.store, owner_principal_id=OWNER, project_id="beta", session_id="sess_1",
        turn_id="turn_1", source_event_id="evt_1",
        runs=[_run("make test", 2, "1"), _run("make test JOBS=1", 0, "2")],
    )
    assert len(_keep(service).kept) == 1  # type: ignore[attr-defined]

    def note(command: str, exit_code: int) -> str | None:
        return lesson_for_command(
            service.store, workspace_root=service.workspace_root, owner_principal_id=OWNER,
            project_id="beta", command=command, exit_code=exit_code,
        )

    assert note("make test", 0) is None
    assert "make test JOBS=1" in (note("make test", 2) or "")
    assert note("make test", 2) is not None  # still kept
    # The recommended command failed: the lesson is out of date and archived.
    assert "archived" in (note("make test JOBS=1", 1) or "")
    assert note("make test", 2) is None
    assert build_memory_brief(service.store, owner_principal_id=OWNER, project_id="beta").items == ()


def test_the_models_lesson_is_filed_only_on_this_tasks_evidence(
    service: DashboardService, monkeypatch: pytest.MonkeyPatch
) -> None:
    import raiker.memory.lessons as lessons

    runs = [_run("npm install", 1, "1"), _run("pnpm install", 0, "2")]
    monkeypatch.setattr(lessons, "turn_runs_and_changes", lambda *_a, **_k: (runs, []))

    def record(failed: str, passed: str, text: str = "This repo uses pnpm.") -> str:
        return lessons.record_lesson(
            service.store, owner_principal_id=OWNER, project_id="alpha", session_id="sess_1",
            turn_id="turn_1", source_event_id="evt_1", text=text,
            failed_command=failed, passed_command=passed,
        )

    assert record("npm ci", "pnpm install") == "lesson_not_backed_by_this_task"
    assert record("npm install", "pnpm install", text="token: " + "x" * 30) == "lesson_secret_like"
    assert record("npm install", "pnpm install") == "recorded"
    [proposal] = service.list_memory_proposals(OWNER)
    assert proposal["text"] == "This repo uses pnpm. Run `pnpm install` instead of `npm install`."
    assert len(_keep(service).kept) == 1  # type: ignore[attr-defined]
