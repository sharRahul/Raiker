"""ADD-27 GH-23 — governed fetch and clone: nothing fetched runs, nothing is borrowed unasked."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from raiker.approvals.execution import EXECUTABLE_ON_APPROVAL
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.models.contracts import ToolCallProposal
from raiker.models.tool_call_validation import validate_tool_call
from raiker.runtime.authority.activation import get_activation_requirement
from raiker.runtime.authority.models import RiskLevelValue
from raiker.runtime.authority.router import CAPABILITY_GATE_MAP
from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES
from raiker.runtime.executors.tier1_git import GitFetchExecutor
from raiker.runtime.git_credential import GitCredentialBroker
from raiker.storage.sqlite import SQLiteStore
from raiker.tools import git as git_tools
from raiker.tools.git import proposed_clone_snapshot, proposed_fetch_snapshot
from tests.factories import governed_action, human

OWNER = "principal_owner"
TOKEN = "ghp_fetchToken00000000000000000000000000"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for key in [name for name in os.environ if name.startswith("GIT_CONFIG")]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("RAIKER_GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", "github.com")
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    _git(ws, "init", "--initial-branch=main", ".")
    _git(ws, "config", "user.name", "T")
    _git(ws, "config", "user.email", "t@example.com")
    _git(ws, "config", "commit.gpgsign", "false")
    (ws / "a.txt").write_text("a\n", encoding="utf-8")
    _git(ws, "add", "a.txt")
    _git(ws, "commit", "-m", "a")
    _git(ws, "remote", "add", "origin", "https://github.com/acme/demo.git")
    return ws


@pytest.fixture
def transfers(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    seen: list[dict[str, Any]] = []
    real_run = subprocess.run

    def fake(command: Any, *args: Any, **kwargs: Any) -> Any:
        if "fetch" in command or "clone" in command:
            seen.append({"command": list(command), "env": dict(kwargs.get("env") or {})})
            if "clone" in command:
                Path(command[-1]).mkdir(parents=True)
                real_run(["git", "-C", command[-1], "init", "-q"], check=True)
            return subprocess.CompletedProcess(command, 0, "", " * [new branch] main -> origin/main\n")
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(git_tools.subprocess, "run", fake)
    return seen


def _act(tool: str, args: dict[str, Any]) -> Any:
    return governed_action(
        tool, principal_id=OWNER, risk_level=RiskLevelValue.HIGH, arguments=args,
        session_id="sess_a",
    )


def test_fetch_and_clone_are_one_governed_capability() -> None:
    assert CAPABILITY_GATE_MAP["git_fetch"] == CAPABILITY_GATE_MAP["git_clone"] == "git_fetch_execution"
    assert "git_fetch_execution" in REAL_EXECUTOR_CAPABILITIES
    assert "git_fetch_execution" in EXECUTABLE_ON_APPROVAL
    requirement = get_activation_requirement("git_fetch_execution")
    assert requirement is not None and requirement.risk_tier == "2"
    assert requirement.requires_threat_model_ack and requirement.requires_human_confirmation_to_enable
    for tool, args in (("git_fetch", {}), ("git_clone", {"repository": "acme/demo"})):
        action = validate_tool_call(ToolCallProposal(call_id="c", tool_name=tool, arguments=args))
        assert action.risk_level == "high" and action.requires_approval is True


def test_a_clone_takes_owner_and_name_never_a_url(repo: Path) -> None:
    for bad in ("https://evil.example.com/x.git", "../escape", "acme/../../etc", "acme", "file:///etc"):
        assert proposed_clone_snapshot(repo, bad)["error"]["type"] == "invalid_repository"
    snapshot = proposed_clone_snapshot(repo, "Acme/Demo")
    assert snapshot["remote_url"] == "https://github.com/Acme/Demo.git"
    assert snapshot["repository_key"] == "github.com/acme/demo"


def test_a_clone_never_overwrites_and_stays_in_the_workspace(repo: Path) -> None:
    (repo / "demo").mkdir()
    assert proposed_clone_snapshot(repo, "acme/demo")["error"]["type"] == "clone_destination_exists"
    assert proposed_clone_snapshot(repo, "acme/demo", "../outside")["error"]["type"] == (
        "clone_destination_outside_workspace"
    )


def test_fetch_goes_only_where_a_push_could(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", "")
    assert proposed_fetch_snapshot(repo)["error"]["type"] == "fetch_egress_denied"
    monkeypatch.setenv("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", "github.com")
    _git(repo, "remote", "set-url", "origin", "https://gitlab.com/acme/demo.git")
    assert proposed_fetch_snapshot(repo)["error"]["type"] == "unsupported_remote_host"
    _git(repo, "remote", "set-url", "origin", "git@github.com:acme/demo.git")
    assert proposed_fetch_snapshot(repo)["error"]["type"] == "fetch_credential_wrong_method"


def test_nothing_fetched_can_run(repo: Path, transfers: list[dict[str, Any]]) -> None:
    result = GitFetchExecutor(repo, SQLiteStore(repo)).execute(_act("git_fetch", {}), human(OWNER, role_ids=()))
    assert result.ok is True, result.reason_code
    (call,) = transfers
    command = call["command"]
    for setting in (
        "core.hooksPath=raiker-no-such-hooks", "core.fsmonitor=false", "protocol.file.allow=never",
        "protocol.ext.allow=never", "submodule.recurse=false", "transfer.fsckObjects=true",
    ):
        assert setting in command
    assert "--no-recurse-submodules" in command
    # Constructed environment: the host's HOME and credentials are not there.
    assert call["env"]["HOME"] == str(repo.resolve())


def test_a_public_fetch_borrows_no_credential(repo: Path, transfers: list[dict[str, Any]]) -> None:
    store = SQLiteStore(repo)
    GitCredentialBroker(store, OWNER).store_token(TOKEN)
    GitFetchExecutor(repo, store).execute(_act("git_fetch", {}), human(OWNER, role_ids=()))
    assert transfers[0]["env"].get("RAIKER_GIT_PUSH_TOKEN", "") == ""


def test_a_fetch_grant_lends_and_a_push_grant_does_not(repo: Path, transfers: list[dict[str, Any]]) -> None:
    store = SQLiteStore(repo)
    broker = GitCredentialBroker(store, OWNER)
    broker.store_token(TOKEN)
    broker.grant("session", session_id="sess_a", operation="push")
    GitFetchExecutor(repo, store).execute(_act("git_fetch", {}), human(OWNER, role_ids=()))
    assert transfers[-1]["env"].get("RAIKER_GIT_PUSH_TOKEN", "") == ""
    broker.grant("session", session_id="sess_a", operation="fetch", repository="github.com/acme/demo")
    GitFetchExecutor(repo, store).execute(_act("git_fetch", {}), human(OWNER, role_ids=()))
    assert transfers[-1]["env"]["RAIKER_GIT_PUSH_TOKEN"] == TOKEN
    assert TOKEN not in " ".join(transfers[-1]["command"])


def test_a_clone_lands_in_the_workspace(repo: Path, transfers: list[dict[str, Any]]) -> None:
    result = GitFetchExecutor(repo, SQLiteStore(repo)).execute(
        _act("git_clone", {"repository": "acme/tools", "path": "vendor/tools"}), human(OWNER, role_ids=())
    )
    assert result.ok is True, result.reason_code
    command = transfers[0]["command"]
    assert command[-2:] == ["https://github.com/acme/tools.git", str((repo / "vendor" / "tools").resolve())]
    assert "--" in command and "--no-recurse-submodules" in command
