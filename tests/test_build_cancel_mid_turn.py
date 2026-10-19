"""BR-D02 — a Build turn stopped mid-turn keeps its target binding and lets go of the folder.

Driven through the real routes with only the provider scripted: a Build turn on
a selected repository starts, the model proposes a read, and the owner presses
Stop while the model is answering. The stop is honoured at the safe boundary,
and then:

* the turn ends ``stopped``, not failed and not still running;
* the target it started on is still recorded, with its fingerprint, so its
  outcome is judged against where it actually ran;
* the outcome says ``no_change`` — a stopped turn that wrote nothing claims
  nothing — and names no drift;
* the folder is free: another conversation's Build turn in the same checkout
  is admitted instead of being refused as concurrent work.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from raiker.control.build_target import load_turn_target, running_turns_on_folder
from raiker.models.contracts import ModelResponse, ToolCallProposal
from raiker.storage.sqlite import SQLiteStore
from tests.test_bug_346_accepted_build_write import client, headers, workspace
from tests.test_turn_resume_after_approval import ScriptedRouter, scripted_model

__all__ = ["client", "headers", "scripted_model", "workspace"]


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=T", "-c", "user.email=t@example.invalid", *args],
        check=True, capture_output=True,
    )


def _repository(client: TestClient, headers: dict[str, str], ws: Path) -> str:
    root = ws / "app"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    (root / "README.md").write_text("hello\n")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "init")
    resp = client.post("/api/code/repos", json={"kind": "local", "path": "app"}, headers=headers)
    assert resp.status_code == 201, resp.text
    repo_id = str(resp.json()["repo_id"])
    selected = client.put("/api/code/repos/selection", json={"repo_id": repo_id}, headers=headers)
    assert selected.status_code == 200, selected.text
    return repo_id


def _running_turn(store: SQLiteStore) -> tuple[str, str]:
    """The running turn's conversation, and the owner's human principal — what Stop is filed under."""
    with store.connect() as connection:
        session = connection.execute(
            "SELECT session_id FROM turns WHERE status = 'running' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        human = connection.execute(
            "SELECT principal_id FROM principals WHERE principal_type = 'human' AND is_active = 1 LIMIT 1"
        ).fetchone()
    return str(session[0]), str(human[0])


def test_a_stopped_build_turn_keeps_its_target_and_frees_the_folder(
    workspace: Path,
    client: TestClient,
    headers: dict[str, str],
    scripted_model: ScriptedRouter,
    offline_default_model: None,
) -> None:
    _repository(client, headers, workspace)
    store = SQLiteStore(workspace)
    calls = {"n": 0}

    def chat(provider: str, model: str, messages: Any, tools: Any = None) -> ModelResponse:
        calls["n"] += 1
        if calls["n"] == 1:
            # The owner presses Stop while the model is answering the first time.
            session_id, user_id = _running_turn(store)
            store.request_turn_stop(session_id, user_id, reason="user stopped this turn (composer)")
            return ModelResponse(
                text="Reading the readme first.",
                tool_calls=[ToolCallProposal(call_id="call_r", tool_name="read_file", arguments={"path": "app/README.md"})],
            )
        return ModelResponse(text="This second answer must never be produced.")

    scripted_model.chat = chat  # type: ignore[method-assign]
    project = client.post("/api/projects", json={"name": "Stop"}, headers=headers).json()["project_id"]
    stopped = client.post(
        "/api/prompts",
        json={"text": "Tidy the readme.", "surface": "build", "project_id": project, "capability_modes": {}},
        headers=headers,
    )
    assert stopped.status_code == 200, stopped.text
    body = stopped.json()
    assert body["status"] == "stopped", body
    assert calls["n"] == 1

    turn = store.load_turn(body["turn_id"])
    assert turn is not None and turn["status"] == "stopped"

    # The binding survives the stop: the target it started on, fingerprinted.
    with store.connect() as connection:
        owner = str(
            connection.execute(
                "SELECT owner_principal_id FROM build_turn_targets WHERE turn_id = ?", (body["turn_id"],)
            ).fetchone()[0]
        )
    target = load_turn_target(store, owner_principal_id=owner, turn_id=body["turn_id"])
    assert target is not None and target["folder"] == "app" and target["fingerprint"]

    # A stopped turn that changed nothing claims nothing, and nothing moved under it.
    outcome = client.get(
        f"/api/sessions/{body['session_id']}/turns/{body['turn_id']}/outcome", headers=headers
    ).json()
    assert outcome["outcome"] == "no_change", outcome
    assert not outcome.get("target_drift")

    # The folder is no longer held: a second conversation may work in it.
    assert running_turns_on_folder(
        store, owner_principal_id=owner, folder="app", exclude_session_id="sess_other", window_seconds=900
    ) == []
    calls["n"] = 10
    second = client.post(
        "/api/prompts",
        json={"text": "Now read it.", "surface": "build", "project_id": project, "capability_modes": {}},
        headers=headers,
    ).json()
    assert second["status"] == "completed", second
    assert "Another Build conversation" not in str(second.get("message"))
