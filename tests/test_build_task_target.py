"""BR-02 / BR-D03 — a scheduled Build task runs in the repository it was scheduled for, or not at all.

A Build task records the repository Build was pointed at when the owner
scheduled it. Each cycle is checked against it before it starts: Build pointed
at another repository, or none, refuses the cycle with a sentence that names
both — so an issue's change is never carried into a checkout nobody scheduled
it for.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control.build_target import (
    describe_target,
    load_task_target,
    record_task_target,
    task_target_mismatch,
)
from raiker.control.dashboard import DashboardService
from raiker.storage.sqlite import SQLiteStore

OWNER = "principal_owner"


def _git_repo(root: Path) -> None:
    root.mkdir(parents=True)
    run = ["git", "-C", str(root), "-c", "user.name=T", "-c", "user.email=t@example.invalid"]
    subprocess.run([*run, "init", "-q", "-b", "main"], check=True, capture_output=True)
    (root / "a.txt").write_text("a\n")
    subprocess.run([*run, "add", "."], check=True, capture_output=True)
    subprocess.run([*run, "commit", "-q", "-m", "init"], check=True, capture_output=True)


def _two_repos(ws: Path) -> SQLiteStore:
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    store = SQLiteStore(ws)
    for name in ("one", "two"):
        _git_repo(ws / name)
        store.insert_code_repo(repo_id=f"repo_{name}", owner_principal_id=OWNER, kind="local", label=name, local_subpath=name)
    store.select_code_repo(OWNER, "repo_one")
    return store


def _envelope(task_id: str) -> Any:
    from raiker.contracts.models import (
        ClientMetadata,
        PromptEnvelope,
        PromptOptions,
        PromptPayload,
        UserMetadata,
    )

    return PromptEnvelope(
        request_id="req_1",
        session_id="sess_task",
        turn_id="turn_task",
        client=ClientMetadata(type="dashboard", name="raiker-scheduler", version="1"),
        user=UserMetadata(id="user_owner", display_name="Owner"),
        prompt=PromptPayload(text="Work the issue.", metadata={"surface": "build", "task_id": task_id}),
        options=PromptOptions(),
    )


def test_a_build_task_records_the_repository_it_was_scheduled_for(tmp_path: Path) -> None:
    store = _two_repos(tmp_path)
    user_id = store.principal_user_id(OWNER)
    store.create_project("proj_issues", "Issues", "issues", owner_user_id=user_id)
    view = DashboardService(tmp_path).create_task(
        title="Issue #1", objective="Fix it.", user_id=user_id, principal_id=OWNER,
        project_id="proj_issues", surface="build", start_immediately=False,
    )
    recorded = load_task_target(store, owner_principal_id=OWNER, task_id=view.task_id)
    assert recorded is not None and recorded["repo_id"] == "repo_one" and recorded["folder"] == "one"


def test_a_cycle_on_another_repository_is_refused_and_names_both(tmp_path: Path) -> None:
    from raiker.gateway.agent_gateway import AgentGateway

    store = _two_repos(tmp_path)
    one = describe_target(store, tmp_path, OWNER, store.load_code_repo(OWNER, "repo_one"))
    assert record_task_target(store, owner_principal_id=OWNER, task_id="task_x", target=one)
    gateway = AgentGateway(tmp_path, principal_id=OWNER)

    # Pointed where it was scheduled: the cycle may run.
    assert gateway._build_target_refusal(_envelope("task_x")) is None

    # The owner points Build at another repository: the cycle does not start.
    store.select_code_repo(OWNER, "repo_two")
    refused = gateway._build_target_refusal(_envelope("task_x"))
    assert refused is not None and refused.status == "failed"
    assert "set up for one (one)" in refused.message and "pointed at two" in refused.message
    assert "nothing was changed" in refused.message

    # Nothing selected at all is a mismatch too, never a fall-back to the workspace.
    store.select_code_repo(OWNER, None)
    assert gateway._build_target_refusal(_envelope("task_x")) is not None

    # A turn that is not a scheduled task's is not held to any task's repository.
    plain = _envelope("")
    assert gateway._build_target_refusal(plain) is None


def test_the_same_reference_on_a_different_folder_is_a_mismatch() -> None:
    scheduled = {"repo_id": "r", "identity": "folder:app", "folder": "app"}
    assert task_target_mismatch(scheduled, {"repo_id": "r", "identity": "folder:app", "folder": "app"}) == []
    assert task_target_mismatch(scheduled, {"repo_id": "r", "identity": "folder:web", "folder": "web"}) == [
        "identity", "folder",
    ]
    assert task_target_mismatch(scheduled, {"repo_id": "other"}) == ["repository"]
    assert task_target_mismatch(None, {"repo_id": "other"}) == []
