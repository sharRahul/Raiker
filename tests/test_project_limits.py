"""A project's own permission limits (Quiet UI 06, QUI-F21).

Limits only narrow: a conversation filed in a project cannot reach a
repository, site or connection the project's limits leave out, even where the
owner's permissions would allow it, and a conversation outside the project is
unaffected. What cannot be checked is refused. Setting them is the owner's,
on the project.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id
from raiker.contracts.models import ClientMetadata, ToolAction
from raiker.events.writer import EventLogWriter
from raiker.policy import project_limits
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.storage.sqlite import SQLiteStore
from tests.machine_identity_helpers import IdentityBoundTestBroker as ToolBroker


def test_limits_are_cleaned_and_refused_when_unusable() -> None:
    cleaned = project_limits.clean({
        "repositories": ["https://github.com/Acme/Site.git", "acme/site"],
        "web_domains": ["https://Docs.Example.com/path", "*.example.org"],
        "connections": ["Gmail"],
    })
    assert cleaned == {
        "repositories": ["acme/site"],
        "web_domains": ["docs.example.com", "example.org"],
        "connections": ["gmail"],
    }
    for bad in ({"repositories": ["not a repo"]}, {"web_domains": ["localhost"]}, {"connections": ["no spaces"]}):
        with pytest.raises(project_limits.LimitError):
            project_limits.clean(bad)
    assert project_limits.describe(cleaned)[0] == "Pushes only to acme/site"


def _store_with_project(tmp_path: Path) -> SQLiteStore:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    store = SQLiteStore(tmp_path)
    store.create_project("proj_site", "Site", "site")
    store.create_session("sess_in", str(tmp_path), title="In the project")
    store._execute("UPDATE sessions SET project_id = ? WHERE session_id = ?", ("proj_site", "sess_in"))
    store.create_session("sess_out", str(tmp_path), title="Outside")
    project_limits.save(store, "proj_site", project_limits.clean({
        "repositories": ["acme/site"], "web_domains": ["example.com"], "connections": ["github"],
    }))
    return store


def _refusal(store: SQLiteStore, tmp_path: Path, session_id: str, tool: str, arguments: dict[str, object]) -> str | None:
    return project_limits.refusal(
        store, workspace_root=tmp_path, session_id=session_id, owner_principal_id=None,
        tool_name=tool, arguments=arguments,
    )


def test_each_kind_narrows_only_inside_the_project(tmp_path: Path) -> None:
    store = _store_with_project(tmp_path)
    assert _refusal(store, tmp_path, "sess_in", "web_fetch", {"url": "https://docs.example.com/a"}) is None
    assert _refusal(store, tmp_path, "sess_in", "web_fetch", {"url": "https://evil.test/"}) == "project_limit_web_domain"
    assert _refusal(store, tmp_path, "sess_in", "web_fetch", {"url": "not a url"}) == "project_limit_web_domain"
    assert _refusal(store, tmp_path, "sess_in", "github_write", {"repo": "acme/site"}) is None
    assert _refusal(store, tmp_path, "sess_in", "github_write", {"repo": "acme/other"}) == "project_limit_repository"
    assert _refusal(store, tmp_path, "sess_in", "gmail_read", {}) == "project_limit_connection"
    assert _refusal(store, tmp_path, "sess_in", "connector_write", {"connector_id": "slack"}) == "project_limit_connection"
    assert _refusal(store, tmp_path, "sess_in", "list_directory", {"path": "."}) is None
    # Outside the project nothing is limited.
    assert _refusal(store, tmp_path, "sess_out", "web_fetch", {"url": "https://evil.test/"}) is None
    assert _refusal(store, tmp_path, "sess_out", "github_write", {"repo": "acme/other"}) is None


def test_a_push_is_checked_against_the_remote_it_would_really_use(tmp_path: Path) -> None:
    store = _store_with_project(tmp_path)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "remote", "add", "origin", "https://github.com/acme/other.git"], check=True)
    assert _refusal(store, tmp_path, "sess_in", "git_push", {}) == "project_limit_repository"
    subprocess.run(["git", "-C", str(tmp_path), "remote", "set-url", "origin", "git@github.com:Acme/Site.git"], check=True)
    assert _refusal(store, tmp_path, "sess_in", "git_push", {}) is None
    assert _refusal(store, tmp_path, "sess_in", "git_push", {"remote": "nope"}) == "project_limit_repository"


def test_the_broker_refuses_what_the_project_leaves_out(tmp_path: Path) -> None:
    store = _store_with_project(tmp_path)
    broker = ToolBroker(
        workspace_root=tmp_path,
        policy_engine=PolicyEngine(StaticPolicyConfig(tmp_path)),
        store=store,
        writer=EventLogWriter(store),
        principal_id="principal_owner",
    )
    result, decision = broker.execute(
        ToolAction(new_id("act_"), "web_fetch", {"url": "https://evil.test/"}, "medium", False),
        session_id="sess_in",
        turn_id=new_id("turn_"),
        client=ClientMetadata(type="test_harness", name="tests", version="0.0.0"),
    )
    assert decision.decision == "deny"
    assert decision.reasons[0] == "denied_by_project_limit_web_domain"
    assert result.status == "denied"
    assert "project" in str((result.error or {}).get("message", ""))


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(tmp_path))


def test_the_owner_sets_limits_on_the_project(client: TestClient) -> None:
    response = client.post("/api/auth/register", json={"username": "owner", "password": "a-long-password-1"})
    h = {"Authorization": f"Bearer {response.json()['token']}"}
    project_id = client.post("/api/projects", json={"name": "Site"}, headers=h).json()["project_id"]
    assert client.get(f"/api/projects/{project_id}/limits", headers=h).json()["summary"] == []
    saved = client.put(
        f"/api/projects/{project_id}/limits", json={"repositories": ["acme/site"], "web_domains": [], "connections": []}, headers=h
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["summary"] == ["Pushes only to acme/site"]
    refused = client.put(f"/api/projects/{project_id}/limits", json={"web_domains": ["not a domain"]}, headers=h)
    assert refused.status_code == 422
    assert client.get("/api/projects/proj_nope/limits", headers=h).status_code == 404
