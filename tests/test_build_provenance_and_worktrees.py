"""BR-D05 / BR-03 / BR-07 / BR-D04 / BR-D06 — provenance, task worktrees, revalidation, and faults.

* A commit Raiker records carries ``Raiker-Session`` / ``Raiker-Turn`` trailers
  built only from runtime identifiers, and read-back says whether this account
  recorded the turn they name.
* A task worktree is a separate folder on a new ``raiker/`` branch, connected as
  its own repository; collisions are refused, and removal keeps the branch and
  refuses uncommitted work.
* A Build turn is refused while another conversation's Build turn is running in
  the same folder, and a parked turn whose target moved is closed, not resumed.
* A high-severity finding on the stored review of the current patch keeps a
  passing turn short of verified.
* Faults injected through the real command store and the real gateway never
  read as verified.
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
from raiker.contracts.ids import utc_now
from raiker.control.build_outcome import classify_build_turn
from raiker.control.build_provenance import provenance_trailers, read_provenance, with_trailers
from raiker.control.build_target import describe_target, record_turn_target
from raiker.storage.sqlite import SQLiteStore

OWNER = "principal_owner"
SESSION = "sess_" + "a1" * 16
TURN = "turn_" + "b2" * 16
WRITE_AT = "2026-10-19T10:00:05Z"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=T", "-c", "user.email=t@example.invalid", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", "-b", "main")
    (root / "app.py").write_text("x = 1\n")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "init")


@pytest.fixture
def api(tmp_path: Path) -> tuple[TestClient, dict[str, str], Path]:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    client = TestClient(create_app(tmp_path))
    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    return client, {"Authorization": f"Bearer {token}"}, tmp_path


def _connect(client: TestClient, headers: dict[str, str], ws: Path, folder: str = "app") -> str:
    _repo(ws / folder)
    resp = client.post("/api/code/repos", json={"kind": "local", "path": folder}, headers=headers)
    assert resp.status_code == 201, resp.text
    return str(resp.json()["repo_id"])


# ── Provenance ───────────────────────────────────────────────────────────────


def test_trailers_are_only_ever_well_formed_runtime_ids() -> None:
    assert provenance_trailers(SESSION, TURN) == [("Raiker-Session", SESSION), ("Raiker-Turn", TURN)]
    assert provenance_trailers(SESSION, None) == [("Raiker-Session", SESSION)]
    # A newline cannot smuggle a second trailer; a path or a token is not an id.
    assert provenance_trailers(SESSION + "\nRaiker-Turn: forged", TURN) == []
    assert provenance_trailers("/home/owner/secret", TURN) == []
    assert provenance_trailers("sess_" + "x" * 200, TURN) == []
    assert provenance_trailers(SESSION, "turn_../../etc") == [("Raiker-Session", SESSION)]
    assert with_trailers("Fix it\n", [("Raiker-Session", SESSION)]) == f"Fix it\n\nRaiker-Session: {SESSION}\n"
    assert with_trailers("Fix it", []) == "Fix it"


def test_a_raiker_commit_carries_its_trailers_and_reads_back_recorded(tmp_path: Path) -> None:
    from raiker.tools.git import create_commit

    store = SQLiteStore(tmp_path)
    _repo(tmp_path / "app")
    store.create_session(SESSION, str(tmp_path), user_id=None, origin="build")
    store.insert_turn(SESSION, TURN, "Fix it")
    (tmp_path / "app" / "app.py").write_text("x = 2\n")
    made = create_commit(tmp_path / "app", "Raise x", trailers=provenance_trailers(SESSION, TURN))
    assert made["status"] == "success"
    assert made["trailers"] == [f"Raiker-Session: {SESSION}", f"Raiker-Turn: {TURN}"]
    assert f"Raiker-Turn: {TURN}" in _git(tmp_path / "app", "log", "-1", "--format=%B")

    # A hand-typed trailer naming a turn nobody recorded here.
    (tmp_path / "app" / "b.py").write_text("y = 1\n")
    _git(tmp_path / "app", "add", ".")
    _git(tmp_path / "app", "commit", "-q", "-m", "Hand made\n\nRaiker-Session: sess_" + "c3" * 16)
    rows = read_provenance(store, tmp_path / "app", user_id=None)
    assert [row["provenance"] for row in rows] == ["unrecorded", "recorded", "none"]
    assert rows[1]["turn_id"] == TURN and rows[1]["subject"] == "Raise x"


def test_the_executor_never_pairs_a_session_with_another_sessions_turn(tmp_path: Path) -> None:
    from raiker.runtime.authority.router import GovernedAction
    from raiker.runtime.executors.tier1_git import GitWriteExecutor

    store = SQLiteStore(tmp_path)
    store.create_session(SESSION, str(tmp_path), user_id=None, origin="build")
    store.insert_turn(SESSION, TURN, "Fix it")
    executor = GitWriteExecutor(tmp_path, store)

    def action(**extra: Any) -> GovernedAction:
        return GovernedAction(
            action_id="act_1", principal_id=OWNER, action_type="git_commit",
            tool_or_service_name="git_commit", arguments={}, **extra,
        )

    assert executor._proposing_turn(action(session_id=SESSION, turn_id=TURN)) == (SESSION, TURN)
    # Resolved from the inbox: the proposing chat is the origin; the inbox's turn is dropped.
    inbox = action(session_id="sess_inbox_x", origin_session_id=SESSION, turn_id="turn_" + "d4" * 16)
    assert executor._proposing_turn(inbox) == (SESSION, None)


def test_the_provenance_route_reads_recent_commits(api: tuple[TestClient, dict[str, str], Path]) -> None:
    client, headers, ws = api
    repo_id = _connect(client, headers, ws)
    body = client.get(f"/api/code/repos/{repo_id}/provenance", headers=headers).json()
    assert body["reason_code"] is None
    assert [row["subject"] for row in body["commits"]] == ["init"]
    assert body["commits"][0]["provenance"] == "none"


# ── Task worktrees ───────────────────────────────────────────────────────────


def test_a_task_worktree_is_its_own_folder_branch_and_repository(
    api: tuple[TestClient, dict[str, str], Path],
) -> None:
    client, headers, ws = api
    repo_id = _connect(client, headers, ws)
    made = client.post(f"/api/code/repos/{repo_id}/worktrees", json={"name": "fix-login"}, headers=headers)
    assert made.status_code == 201, made.text
    body = made.json()
    assert body["branch"] == "raiker/fix-login" and body["local_subpath"] == "app.worktrees/fix-login"
    assert (ws / "app.worktrees" / "fix-login" / "app.py").exists()
    # The main checkout did not move.
    assert _git(ws / "app", "branch", "--show-current") == "main"
    target = client.get(f"/api/code/repos/{body['repo_id']}/target", headers=headers).json()
    main_target = client.get(f"/api/code/repos/{repo_id}/target", headers=headers).json()
    assert target["branch"] == "raiker/fix-login" and target["fingerprint"] != main_target["fingerprint"]

    again = client.post(f"/api/code/repos/{repo_id}/worktrees", json={"name": "fix-login"}, headers=headers)
    assert again.status_code == 409 and again.json()["detail"]["reason_code"] == "branch_exists"
    bad = client.post(f"/api/code/repos/{repo_id}/worktrees", json={"name": "../escape"}, headers=headers)
    assert bad.status_code == 422 and bad.json()["detail"]["reason_code"] == "invalid_worktree_name"

    # Uncommitted work in the worktree is the owner's, and is never removed.
    (ws / "app.worktrees" / "fix-login" / "wip.py").write_text("todo = 1\n")
    dirty = client.delete(f"/api/code/repos/{body['repo_id']}/worktree", headers=headers)
    assert dirty.status_code == 409 and dirty.json()["detail"]["reason_code"] == "worktree_has_uncommitted_changes"
    assert (ws / "app.worktrees" / "fix-login" / "wip.py").exists()

    # Committed on its branch, then removed: the branch and the commit stay.
    _git(ws / "app.worktrees" / "fix-login", "add", ".")
    _git(ws / "app.worktrees" / "fix-login", "commit", "-q", "-m", "wip")
    removed = client.delete(f"/api/code/repos/{body['repo_id']}/worktree", headers=headers)
    assert removed.status_code == 200, removed.text
    assert removed.json()["branch"] == "raiker/fix-login"
    assert not (ws / "app.worktrees" / "fix-login").exists()
    assert _git(ws / "app", "log", "-1", "--format=%s", "raiker/fix-login") == "wip"
    listed = client.get("/api/code/repos", headers=headers).json()
    assert [row["repo_id"] for row in listed["repos"]] == [repo_id]

    # The main checkout is not a task worktree and is never removed this way.
    main = client.delete(f"/api/code/repos/{repo_id}/worktree", headers=headers)
    assert main.status_code == 422 and main.json()["detail"]["reason_code"] == "not_a_task_worktree"


def test_a_worktree_of_the_workspace_itself_is_refused(api: tuple[TestClient, dict[str, str], Path]) -> None:
    client, headers, ws = api
    _git(ws, "init", "-q", "-b", "main")
    (ws / "README.md").write_text("ws\n")
    _git(ws, "add", "README.md")
    _git(ws, "commit", "-q", "-m", "init")
    resp = client.post("/api/code/repos", json={"kind": "local", "path": "."}, headers=headers)
    assert resp.status_code == 201, resp.text
    refused = client.post(
        f"/api/code/repos/{resp.json()['repo_id']}/worktrees", json={"name": "x"}, headers=headers
    )
    assert refused.status_code == 422
    assert refused.json()["detail"]["reason_code"] == "worktree_needs_subfolder_repository"


# ── The gateway: one Build turn per folder, and revalidation on resume ──────


def _envelope(session_id: str, turn_id: str) -> Any:
    from raiker.contracts.models import (
        ClientMetadata,
        PromptEnvelope,
        PromptOptions,
        PromptPayload,
        UserMetadata,
    )

    return PromptEnvelope(
        request_id="req_1",
        session_id=session_id,
        turn_id=turn_id,
        client=ClientMetadata(type="test_harness", name="tests", version="0.0.0"),
        user=UserMetadata(),
        prompt=PromptPayload(text="fix it", metadata={"surface": "build"}),
        options=PromptOptions(),
    )


def _selected(ws: Path) -> tuple[SQLiteStore, dict[str, Any]]:
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    store = SQLiteStore(ws)
    _repo(ws / "app")
    store.insert_code_repo(repo_id="repo_app", owner_principal_id=OWNER, kind="local", label="app", local_subpath="app")
    store.select_code_repo(OWNER, "repo_app")
    repo = store.load_code_repo(OWNER, "repo_app")
    assert repo is not None
    return store, repo


def test_a_second_conversation_cannot_write_the_same_checkout(tmp_path: Path) -> None:
    from raiker.gateway.agent_gateway import AgentGateway

    store, repo = _selected(tmp_path)
    store.create_session("sess_running", str(tmp_path), user_id=None, origin="build")
    store.insert_turn("sess_running", "turn_running", "Long job")
    record_turn_target(
        store, owner_principal_id=OWNER, session_id="sess_running", turn_id="turn_running",
        target=describe_target(store, tmp_path, OWNER, repo),
    )
    gateway = AgentGateway(tmp_path, principal_id=OWNER)
    refused = gateway._concurrent_build_refusal(_envelope("sess_other", "turn_other"))
    assert refused is not None and "Another Build conversation is still working in app" in refused.message
    # The same conversation is not blocked by itself.
    assert gateway._concurrent_build_refusal(_envelope("sess_running", "turn_next")) is None
    # A finished turn holds nothing.
    store.complete_turn("turn_running", "completed", "done")
    assert gateway._concurrent_build_refusal(_envelope("sess_other", "turn_other")) is None


def test_an_abandoned_running_turn_does_not_hold_the_folder(tmp_path: Path) -> None:
    from raiker.gateway.agent_gateway import AgentGateway

    store, repo = _selected(tmp_path)
    store.create_session("sess_dead", str(tmp_path), user_id=None, origin="build")
    store.insert_turn("sess_dead", "turn_dead", "Host died")
    with store.connect() as connection:
        connection.execute("UPDATE turns SET created_at = '2026-01-01T00:00:00Z' WHERE turn_id = 'turn_dead'")
    record_turn_target(
        store, owner_principal_id=OWNER, session_id="sess_dead", turn_id="turn_dead",
        target=describe_target(store, tmp_path, OWNER, repo),
    )
    assert AgentGateway(tmp_path, principal_id=OWNER)._concurrent_build_refusal(_envelope("sess_new", "turn_new")) is None


def test_a_parked_turn_whose_branch_moved_is_closed_not_resumed(tmp_path: Path) -> None:
    from raiker.gateway.agent_gateway import AgentGateway, TurnSuspensionError

    store, repo = _selected(tmp_path)
    store.create_session("sess_p", str(tmp_path), user_id=None, origin="build")
    store.insert_turn("sess_p", "turn_p", "Change it")
    record_turn_target(
        store, owner_principal_id=OWNER, session_id="sess_p", turn_id="turn_p",
        target=describe_target(store, tmp_path, OWNER, repo),
    )
    with store.connect() as connection:
        connection.execute(
            """INSERT INTO suspended_turns (approval_id, session_id, turn_id, request_id, principal_id,
               action_id, tool_name, call_id, prompt_text, messages_json, options_json, client_json, created_at)
               VALUES ('appr_p', 'sess_p', 'turn_p', 'req_p', ?, 'act_p', 'write_file', 'call_p', 'x', '[]', '{}', '{}', ?)""",
            (OWNER, utc_now()),
        )
    gateway = AgentGateway(tmp_path, principal_id=OWNER)
    envelope = _envelope("sess_p", "turn_p")
    assert gateway._resume_target_refusal(envelope) is None
    gateway._refuse_resume_on_drift("appr_p", envelope)  # nothing moved: no-op

    _git(tmp_path / "app", "checkout", "-q", "-b", "elsewhere")
    assert gateway._resume_target_refusal(envelope) == "branch"
    with pytest.raises(TurnSuspensionError, match="build_target_changed"):
        gateway._refuse_resume_on_drift("appr_p", envelope)
    with store.connect() as connection:
        status = connection.execute("SELECT status FROM suspended_turns WHERE approval_id = 'appr_p'").fetchone()[0]
    assert status == "target_changed"
    closed = store.load_turn("turn_p")
    assert closed is not None and closed["status"] == "failed"


# ── The outcome reads the stored patch review ───────────────────────────────


def test_a_high_finding_on_the_current_patch_keeps_the_turn_unverified() -> None:
    passing: dict[str, Any] = {
        "tool_actions": [{"tool_name": "apply_patch", "status": "success", "completed_at": WRITE_AT, "arguments_json": "{}"}],
        "command_runs": [{"run_id": "c", "safe_display": "pytest -q", "started_at": "2026-10-19T10:00:10Z", "state": "succeeded", "exit_code": 0}],
        "checks": ["pytest -q"],
    }
    assert classify_build_turn(**passing)["outcome"] == "completed_verified"
    clean = {"fingerprint": "f", "counts": {"high": 0, "medium": 2}, "findings": [{}, {}]}
    assert classify_build_turn(**passing, review=clean)["outcome"] == "completed_verified"
    risky = {"fingerprint": "f", "counts": {"high": 1}, "findings": [{}]}
    outcome = classify_build_turn(**passing, review=risky)
    assert outcome["outcome"] == "completed_unverified"
    assert outcome["review"] == {"fingerprint": "f", "high": 1, "findings": 1}
    assert "high-severity finding" in outcome["reason"]


def test_the_outcome_route_reads_the_stored_review_of_the_patch_now(
    api: tuple[TestClient, dict[str, str], Path],
) -> None:
    client, headers, ws = api
    repo_id = _connect(client, headers, ws)
    store = SQLiteStore(ws)
    user_id = store.principal_user_id(OWNER)
    store.create_session("sess_r", str(ws), user_id=user_id, origin="build")
    store.insert_turn("sess_r", "turn_r", "Fix it")
    record_turn_target(
        store, owner_principal_id=OWNER, session_id="sess_r", turn_id="turn_r",
        target=describe_target(store, ws, OWNER, store.load_code_repo(OWNER, repo_id)),
    )
    with store.connect() as connection:
        connection.execute(
            """INSERT INTO tool_actions (action_id, session_id, turn_id, tool_name, arguments_json,
               risk_level, status, proposed_at, completed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("act_r", "sess_r", "turn_r", "write_file",
             json.dumps({"path": "app/app.py", "text": "x = 1\npassword = '" + "hunter2" * 2 + "'\n"}),
             "medium", "success", WRITE_AT, WRITE_AT),
        )
    (ws / "app" / "app.py").write_text("x = 1\npassword = '" + "hunter2" * 2 + "'\n")
    before = client.get("/api/sessions/sess_r/turns/turn_r/outcome", headers=headers).json()
    assert before["review"] is None
    client.post(f"/api/code/repos/{repo_id}/review", headers=headers)
    after = client.get("/api/sessions/sess_r/turns/turn_r/outcome", headers=headers).json()
    assert after["review"]["high"] == 1


# ── Faults through the real stores ───────────────────────────────────────────


def test_a_check_lost_to_a_restart_reads_unknown_through_the_api(
    api: tuple[TestClient, dict[str, str], Path],
) -> None:
    from raiker.execution.commands.models import CommandRequest, CommandState
    from raiker.execution.commands.store import CommandStore

    client, headers, ws = api
    store = SQLiteStore(ws)
    user_id = store.principal_user_id(OWNER)
    pid = client.post("/api/projects", json={"name": "Faults"}, headers=headers).json()["project_id"]
    client.put(f"/api/projects/{pid}/context", json={"checks": ["pytest -q"]}, headers=headers)
    store.create_session("sess_f", str(ws), user_id=user_id, origin="build")
    store.set_session_project("sess_f", pid, user_id=user_id)
    store.insert_turn("sess_f", "turn_f", "Fix it")
    with store.connect() as connection:
        connection.execute(
            """INSERT INTO tool_actions (action_id, session_id, turn_id, tool_name, arguments_json,
               risk_level, status, proposed_at, completed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("act_f", "sess_f", "turn_f", "apply_patch", "{}", "medium", "success", WRITE_AT, WRITE_AT),
        )
    commands = CommandStore(store)
    request = CommandRequest(
        run_id="cmd_f", owner_principal_id=OWNER, acting_principal_id=OWNER, session_id="sess_f",
        turn_id="turn_f", action_id="act_c", repository_id=None, workspace_root=ws, cwd=".",
        executable_template="", argv_template=("pytest", "-q"), safe_display="pytest -q",
        credential_bindings=(), shell=False, interactive=False, background=True, timeout_seconds=60,
        max_output_bytes=100, environment_profile_id="local_native", network_policy_id=None,
        authority_kind="session_command_grant", authority_id="e" * 64,
    )
    commands.create(request)
    commands.transition(OWNER, "cmd_f", CommandState.QUEUED, CommandState.STARTING)
    commands.transition(OWNER, "cmd_f", CommandState.STARTING, CommandState.RUNNING)
    # The host went away mid-check: the run is still `running` with no exit code.
    body = client.get("/api/sessions/sess_f/turns/turn_f/outcome", headers=headers).json()
    assert body["outcome"] == "outcome_unknown" and body["checks"][0]["result"] == "unknown"


def test_a_provider_that_fails_after_a_write_never_verifies(tmp_path: Path) -> None:
    # The write landed; the model died before any check ran. Whatever the turn's
    # transcript says, the runtime's records support only "not verified".
    outcome = classify_build_turn(
        tool_actions=[
            {"tool_name": "write_file", "status": "success", "completed_at": WRITE_AT,
             "arguments_json": json.dumps({"path": "a.py", "text": "x\n"})},
        ],
        command_runs=[],
        checks=["pytest -q"],
        readback=[{"path": "a.py", "state": "matches"}],
    )
    assert outcome["outcome"] == "completed_unverified"
    assert outcome["checks"][0]["result"] == "not_run"


def _parked(store: Any, tmp_path: Path, repo: dict[str, Any], suffix: str) -> None:
    from raiker.control.build_target import authority_snapshot

    store.create_session(f"sess_{suffix}", str(tmp_path), user_id=None, origin="build")
    store.insert_turn(f"sess_{suffix}", f"turn_{suffix}", "Change it")
    target = describe_target(store, tmp_path, OWNER, repo)
    record_turn_target(
        store, owner_principal_id=OWNER, session_id=f"sess_{suffix}", turn_id=f"turn_{suffix}",
        target={**target, "authority": authority_snapshot(store, OWNER, target)},
    )
    with store.connect() as connection:
        connection.execute(
            """INSERT INTO suspended_turns (approval_id, session_id, turn_id, request_id, principal_id,
               action_id, tool_name, call_id, prompt_text, messages_json, options_json, client_json, created_at)
               VALUES (?, ?, ?, 'req', ?, 'act', 'git_push', 'call', 'x', '[]', '{}', '{}', ?)""",
            (f"appr_{suffix}", f"sess_{suffix}", f"turn_{suffix}", OWNER, utc_now()),
        )


def test_a_parked_turn_whose_delegation_was_revoked_is_closed_not_resumed(tmp_path: Path) -> None:
    from raiker.gateway.agent_gateway import AgentGateway, TurnSuspensionError

    store, repo = _selected(tmp_path)
    _git(tmp_path / "app", "remote", "add", "origin", "https://github.com/acme/widgets.git")
    delegation = store.create_repository_delegation(
        principal_id=OWNER, repository="github.com/acme/widgets", operations=["push"], branch_pattern="raiker/*",
        expires_at="2999-01-01T00:00:00Z", created_by=OWNER,
    )
    _parked(store, tmp_path, repo, "d")
    gateway = AgentGateway(tmp_path, principal_id=OWNER)
    envelope = _envelope("sess_d", "turn_d")
    assert gateway._resume_authority_refusal(envelope) is None

    store.revoke_repository_delegation(str(delegation["delegation_id"]), OWNER)
    assert gateway._resume_authority_refusal(envelope) == "delegation_revoked"
    with pytest.raises(TurnSuspensionError, match="build_authority_changed"):
        gateway._refuse_resume_on_drift("appr_d", envelope)
    with store.connect() as connection:
        status = connection.execute("SELECT status FROM suspended_turns WHERE approval_id = 'appr_d'").fetchone()[0]
    assert status == "authority_changed"
    closed = store.load_turn("turn_d")
    assert closed is not None and closed["status"] == "failed"


def test_a_parked_turn_whose_git_credential_was_replaced_is_closed(tmp_path: Path) -> None:
    from raiker.gateway.agent_gateway import AgentGateway

    store, repo = _selected(tmp_path)
    first = store.create_git_credential(principal_id=OWNER, method="token", status="valid", label="one")
    store.select_git_credential(OWNER, str(first["credential_id"]))
    _parked(store, tmp_path, repo, "c")
    gateway = AgentGateway(tmp_path, principal_id=OWNER)
    envelope = _envelope("sess_c", "turn_c")
    assert gateway._resume_authority_refusal(envelope) is None

    second = store.create_git_credential(principal_id=OWNER, method="token", status="valid", label="two")
    store.select_git_credential(OWNER, str(second["credential_id"]))
    assert gateway._resume_authority_refusal(envelope) == "credential_changed"


def test_a_turn_that_started_with_no_delegation_or_credential_never_drifts_on_authority(tmp_path: Path) -> None:
    from raiker.control.build_target import authority_drift, authority_snapshot

    store, repo = _selected(tmp_path)
    target = describe_target(store, tmp_path, OWNER, repo)
    snapshot = authority_snapshot(store, OWNER, target)
    assert snapshot == {"repository": "", "delegations": [], "credential": None}
    assert authority_drift(store, OWNER, {"authority": snapshot}) == []
    # A target recorded before authority was recorded has nothing to compare.
    assert authority_drift(store, OWNER, target) == []
