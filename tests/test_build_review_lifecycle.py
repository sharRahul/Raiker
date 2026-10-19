"""BR-09 / BR-D04 / BR-D05 / BR-D03 — truthful turn states, the review's own history, and task attempts.

* A Build turn the owner stopped reads ``stopped``; one whose changes only partly
  applied reads ``partially_completed``; one waiting on a write it has not been
  allowed yet reads ``blocked`` rather than ``no_change``.
* The exact-patch review parses changed files (an independent validator), says
  which findings are new and which the previous review raised that are gone, and
  a later patch's read says when the last review was of an earlier one.
* Each review is audited, counts only. The commit approval says the trailers it
  will record. A task's attempts carry the turn they ran.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control.build_outcome import classify_build_turn
from raiker.review.patch_review import review_patch, with_lifecycle
from raiker.storage.sqlite import SQLiteStore

WRITE_AT = "2026-10-19T10:00:05Z"
OWNER = "principal_owner"


def _write(status: str = "success", path: str = "a.py") -> dict[str, Any]:
    return {
        "tool_name": "write_file",
        "status": status,
        "completed_at": WRITE_AT,
        "arguments_json": json.dumps({"path": path, "text": "x\n"}),
    }


PASSING_RUN = {
    "run_id": "c", "safe_display": "pytest -q", "started_at": "2026-10-19T10:00:10Z",
    "state": "succeeded", "exit_code": 0,
}


# ── Turn states ──────────────────────────────────────────────────────────────


def test_a_stopped_turn_that_changed_files_reads_stopped() -> None:
    outcome = classify_build_turn(
        tool_actions=[_write()], command_runs=[PASSING_RUN], checks=["pytest -q"], turn_status="stopped"
    )
    assert outcome["outcome"] == "stopped"
    assert "You stopped this turn" in outcome["reason"]
    # A failed check is still a failure, stopped or not.
    failing = {**PASSING_RUN, "state": "failed", "exit_code": 1}
    assert classify_build_turn(
        tool_actions=[_write()], command_runs=[failing], checks=["pytest -q"], turn_status="stopped"
    )["outcome"] == "failed"


def test_a_stopped_turn_that_changed_nothing_claims_nothing() -> None:
    assert classify_build_turn(tool_actions=[], command_runs=[], checks=[], turn_status="stopped")["outcome"] == "no_change"


def test_a_change_that_only_partly_applied_is_partially_completed() -> None:
    outcome = classify_build_turn(
        tool_actions=[_write(), _write(status="failed", path="b.py"), _write(status="denied", path="c.py")],
        command_runs=[PASSING_RUN],
        checks=["pytest -q"],
    )
    assert outcome["outcome"] == "partially_completed"
    assert outcome["writes"] == 1 and outcome["unapplied_writes"] == 2


def test_a_write_waiting_for_approval_is_blocked_not_nothing() -> None:
    outcome = classify_build_turn(
        tool_actions=[_write(status="approval_required")], command_runs=[], checks=["pytest -q"]
    )
    assert outcome["outcome"] == "blocked" and outcome["pending_writes"] == 1
    assert "waiting for your approval" in outcome["reason"]


# ── The review's history ─────────────────────────────────────────────────────

_SECRET = "password = '" + "hunter2" * 2 + "'"


def _diff(path: str, *lines: str) -> str:
    body = "".join(f"+{line}\n" for line in lines)
    return f"--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(lines)} @@\n{body}"


def test_findings_are_new_still_present_or_resolved_against_the_previous_review() -> None:
    first = with_lifecycle(review_patch(_diff("app.py", _SECRET, "breakpoint()")), None)
    assert {item["since"] for item in first["findings"]} == {None}
    assert first["resolved"] == [] and first["previous_fingerprint"] is None
    # The credential moved down a line (still present), the breakpoint is gone
    # (resolved), and a conflict marker arrived (new).
    second = with_lifecycle(review_patch(_diff("app.py", "x = 1", _SECRET, "<<<<<<< HEAD")), first)
    by_rule = {item["rule"]: item["since"] for item in second["findings"]}
    assert by_rule["possible_credential"] == "still_present"
    assert by_rule["conflict_marker"] == "new"
    assert [item["rule"] for item in second["resolved"]] == ["debug_left_in"]
    assert second["previous_fingerprint"] == first["fingerprint"]


@pytest.fixture
def api(tmp_path: Path) -> tuple[TestClient, dict[str, str], Path]:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    client = TestClient(create_app(tmp_path))
    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    return client, {"Authorization": f"Bearer {token}"}, tmp_path


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=T", "-c", "user.email=t@example.invalid", *args],
        check=True, capture_output=True,
    )


def _connect(client: TestClient, headers: dict[str, str], ws: Path) -> str:
    root = ws / "app"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    (root / "service.py").write_text("def ping():\n    return 1\n")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "init")
    resp = client.post("/api/code/repos", json={"kind": "local", "path": "app"}, headers=headers)
    assert resp.status_code == 201, resp.text
    return str(resp.json()["repo_id"])


def _set_gate(client: TestClient, headers: dict[str, str], capability: str, state: str) -> None:
    resp = client.post(
        f"/api/capability-gates/{capability}/set",
        json={"target_state": state, "reason": "owner changed this"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text


def test_the_review_parses_changed_files_and_says_when_it_is_stale(
    api: tuple[TestClient, dict[str, str], Path],
) -> None:
    client, headers, ws = api
    repo_id = _connect(client, headers, ws)
    _set_gate(client, headers, "language_intelligence", "enabled_runtime")
    (ws / "app" / "service.py").write_text("def ping(:\n    return 1\n")

    # The validator parses the changed file: the syntax error is a finding at its line.
    first = client.post(f"/api/code/repos/{repo_id}/review", headers=headers).json()["review"]
    parse = [item for item in first["findings"] if item["rule"] == "does_not_parse"]
    assert parse and parse[0]["path"] == "service.py" and parse[0]["severity"] == "high"
    assert parse[0]["since"] is None

    # A later patch: the read says the last review was of an earlier version.
    _set_gate(client, headers, "language_intelligence", "disabled")
    (ws / "app" / "service.py").write_text("x = 1\ndef ping(:\n    return 1\n")
    stale = client.get(f"/api/code/repos/{repo_id}/review", headers=headers).json()
    assert stale["review"] is None and stale["previous"]["fingerprint"] == first["fingerprint"]

    # With the capability off, the review says the parse check did not run —
    # and the parse finding is listed as gone, not silently dropped.
    second = client.post(f"/api/code/repos/{repo_id}/review", headers=headers).json()["review"]
    not_run = [item for item in second["findings"] if item["rule"] == "parse_check_not_run"]
    assert not_run and not_run[0]["since"] == "new"
    assert "does_not_parse" in {item["rule"] for item in second["resolved"]}

    # Every review is audited — counts and the fingerprint, never content.
    store = SQLiteStore(ws)
    with store.connect() as connection:
        paths = {
            str(row[0])
            for row in connection.execute(
                "SELECT jsonl_path FROM events_index WHERE event_type = 'patch_review_completed'"
            ).fetchall()
        }
    lines = [
        json.loads(line)
        for path in paths
        for line in Path(path if Path(path).is_absolute() else ws / path).read_text(encoding="utf-8").splitlines()
        if "patch_review_completed" in line
    ]
    payloads = [line["payload"] for line in lines]
    assert {payload["fingerprint"] for payload in payloads} == {first["fingerprint"], second["fingerprint"]}
    assert all("def ping" not in json.dumps(payload) for payload in payloads)


def test_the_commit_approval_names_the_trailers_it_will_record(tmp_path: Path) -> None:
    from raiker.control.dashboard import DashboardService

    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    root = tmp_path
    _git(root, "init", "-q", "-b", "main")
    (root / "a.py").write_text("x = 1\n")
    _git(root, "add", "a.py")
    _git(root, "commit", "-q", "-m", "init")
    (root / "a.py").write_text("x = 2\n")
    service = DashboardService(tmp_path)
    text, _label, kind = service._build_preview(
        "git_commit", {"message": "Raise x"}, principal_id=OWNER
    )
    assert kind == "git_change"
    assert "Raiker-Session and Raiker-Turn" in str(text)


def test_a_task_attempt_names_the_turn_it_ran() -> None:
    from raiker.tasks.history import derive_attempts

    attempts = derive_attempts(
        [
            {"event_id": "e1", "event_type": "task_started", "timestamp": "2026-10-19T10:00:00Z", "actor": "s",
             "payload": {}, "session_id": "sess_run", "turn_id": None},
            {"event_id": "e2", "event_type": "task_completed", "timestamp": "2026-10-19T10:01:00Z", "actor": "s",
             "payload": {}, "session_id": "sess_run", "turn_id": "turn_run"},
        ]
    )
    assert attempts[0].session_id == "sess_run" and attempts[0].turn_id == "turn_run"
