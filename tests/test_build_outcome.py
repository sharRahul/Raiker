"""BR-D01 — a Build turn claims only what its own records and the owner's checks support."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.context.gatherer import ContextGatherer
from raiker.control.build_outcome import classify_build_turn
from raiker.storage.sqlite import SQLiteStore

WRITE_AT = "2026-10-18T10:00:05Z"


def _write(at: str = WRITE_AT, status: str = "success") -> dict[str, Any]:
    return {"tool_name": "apply_patch", "status": status, "completed_at": at, "arguments_json": "{}"}


def _run(display: str, *, at: str = "2026-10-18T10:00:10Z", state: str = "succeeded", exit_code: int | None = 0) -> dict[str, Any]:
    return {"run_id": "cmd_1", "safe_display": display, "started_at": at, "state": state, "exit_code": exit_code}


def test_a_turn_that_wrote_nothing_claims_nothing() -> None:
    outcome = classify_build_turn(tool_actions=[], command_runs=[_run("pytest -q")], checks=["pytest -q"])
    assert outcome["outcome"] == "no_change" and outcome["checks"] == []


def test_a_change_with_no_declared_checks_is_unverified() -> None:
    # The model running *a* command of its own choosing is not an independent check.
    outcome = classify_build_turn(tool_actions=[_write()], command_runs=[_run("pytest -q")], checks=[])
    assert outcome["outcome"] == "completed_unverified"
    assert "No checks are declared" in outcome["reason"]


def test_every_declared_check_passing_after_the_last_change_is_verified() -> None:
    outcome = classify_build_turn(
        tool_actions=[_write()],
        command_runs=[_run("pytest -q"), _run("ruff check .", at="2026-10-18T10:00:20Z")],
        checks=["pytest  -q", "ruff check ."],
    )
    assert outcome["outcome"] == "completed_verified"
    assert [row["result"] for row in outcome["checks"]] == ["passed", "passed"]


def test_a_hidden_failing_test_is_failed_whatever_the_model_says() -> None:
    outcome = classify_build_turn(
        tool_actions=[_write()], command_runs=[_run("pytest -q", state="failed", exit_code=1)], checks=["pytest -q"]
    )
    assert outcome["outcome"] == "failed" and outcome["checks"][0]["exit_code"] == 1


def test_a_check_that_passed_before_the_last_change_does_not_verify_it() -> None:
    outcome = classify_build_turn(
        tool_actions=[_write(), _write(at="2026-10-18T10:01:00Z")],
        command_runs=[_run("pytest -q", at="2026-10-18T10:00:30Z")],
        checks=["pytest -q"],
    )
    assert outcome["outcome"] == "completed_unverified"
    assert outcome["checks"][0]["result"] == "ran_before_change"


def test_a_lookalike_command_is_not_the_declared_check() -> None:
    outcome = classify_build_turn(
        tool_actions=[_write()], command_runs=[_run("pytest -q -k nothing")], checks=["pytest -q"]
    )
    assert outcome["checks"][0]["result"] == "not_run" and outcome["outcome"] == "completed_unverified"


def test_a_timed_out_check_leaves_the_outcome_unknown() -> None:
    outcome = classify_build_turn(
        tool_actions=[_write()], command_runs=[_run("pytest -q", state="timed_out", exit_code=None)], checks=["pytest -q"]
    )
    assert outcome["outcome"] == "outcome_unknown"


def test_a_check_waiting_for_approval_is_blocked() -> None:
    waiting = {"tool_name": "shell", "status": "approval_required", "arguments_json": json.dumps({"command": "pytest -q"})}
    outcome = classify_build_turn(tool_actions=[_write(), waiting], command_runs=[], checks=["pytest -q"])
    assert outcome["outcome"] == "blocked" and outcome["checks"][0]["result"] == "waiting"


def test_a_failed_write_is_not_a_change() -> None:
    outcome = classify_build_turn(tool_actions=[_write(status="failed")], command_runs=[], checks=["pytest -q"])
    assert outcome["outcome"] == "no_change"


@pytest.fixture
def api(tmp_path: Path) -> tuple[TestClient, dict[str, str], Path]:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    client = TestClient(create_app(tmp_path))
    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    return client, {"Authorization": f"Bearer {token}"}, tmp_path


def test_checks_are_saved_with_the_project_and_reach_the_turn(api: tuple[TestClient, dict[str, str], Path]) -> None:
    client, headers, ws = api
    pid = client.post("/api/projects", json={"name": "Alpha"}, headers=headers).json()["project_id"]
    saved = client.put(
        f"/api/projects/{pid}/context",
        json={"instructions": "Keep it small.", "attachment_ids": [], "checks": ["pytest  -q", "pytest -q", " "]},
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["checks"] == ["pytest -q"]
    # An editor that does not know about checks keeps them.
    kept = client.put(f"/api/projects/{pid}/context", json={"instructions": "Smaller."}, headers=headers)
    assert kept.json()["checks"] == ["pytest -q"]
    too_many = client.put(
        f"/api/projects/{pid}/context", json={"checks": [f"echo {n}" for n in range(11)]}, headers=headers
    )
    assert too_many.status_code == 422

    store = SQLiteStore(ws)
    user_id = store.principal_user_id("principal_owner")
    store.create_session("sess_b", str(ws), user_id=user_id, origin="build")
    store.set_session_project("sess_b", pid, user_id=user_id)
    store.insert_turn("sess_b", "turn_b", "Fix the bug")
    context = store.load_effective_project_context(pid, user_id=user_id)
    assert context["checks"] == ["pytest -q"]
    included = ContextGatherer().gather(
        workspace_root=ws, session_id="sess_b", turn_id="turn_b", prompt_text="Fix the bug"
    ).included_items
    project = [item for item in included if item.source.source_type == "project_context"]
    assert project and "- pytest -q" in project[0].content
    assert "run each one exactly as written" in project[0].content

    with store.connect() as connection:
        connection.execute(
            """INSERT INTO tool_actions (action_id, session_id, turn_id, tool_name, arguments_json,
               risk_level, status, proposed_at, completed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("act_w", "sess_b", "turn_b", "apply_patch", "{}", "medium", "success", WRITE_AT, WRITE_AT),
        )
    outcome = client.get("/api/sessions/sess_b/turns/turn_b/outcome", headers=headers)
    assert outcome.status_code == 200, outcome.text
    body = outcome.json()
    assert body["outcome"] == "completed_unverified" and body["writes"] == 1
    assert body["checks"] == [{"command": "pytest -q", "result": "not_run", "exit_code": None, "run_id": None}]
    assert client.get("/api/sessions/sess_b/turns/turn_x/outcome", headers=headers).status_code == 404
