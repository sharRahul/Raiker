"""BUG-334, BUG-335 and BUG-336 — the push path, held to what the owner decided.

Three defects found reviewing the code for DEC-21b's amendment:

- **BUG-334.** The proposal read only ``RAIKER_GITHUB_TOKEN``, so with the token
  stored where Settings puts it every proposed push was refused as
  ``push_credential_unset``.
- **BUG-335.** A *for this session* grant made in Settings named no session, and
  the push asked with none, so it lent to every chat and routine for its hour.
- **BUG-336.** The approval showed a head and its commits; the push sent
  whatever the branch held when it ran.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id
from raiker.contracts.models import ToolAction
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.runtime.authority.models import RiskLevelValue
from raiker.runtime.executors.tier1_git import GitPushExecutor
from raiker.runtime.git_credential import GitCredentialBroker
from raiker.storage.sqlite import SQLiteStore
from raiker.tools import git as git_tools
from tests.factories import governed_action, human
from tests.machine_identity_helpers import IdentityBoundTestBroker as ToolBroker

TOKEN = "ghp_vaultOnlyToken0123456789abcdefghij"
OWNER = "principal_owner"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for key in [name for name in os.environ if name.startswith("GIT_CONFIG")]:
        monkeypatch.delenv(key, raising=False)
    # The token is in the vault only: nothing in the environment.
    monkeypatch.delenv("RAIKER_GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", "github.com")
    ws = tmp_path / "repo"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    _git(ws, "init", "--initial-branch=main", ".")
    _git(ws, "config", "user.name", "Raiker Test")
    _git(ws, "config", "user.email", "raiker-test@example.com")
    _git(ws, "config", "commit.gpgsign", "false")
    (ws / "app.py").write_text("print('one')\n", encoding="utf-8")
    _git(ws, "add", "app.py")
    _git(ws, "commit", "-m", "initial")
    _git(ws, "remote", "add", "origin", "https://github.com/acme/demo.git")
    GitCredentialBroker(SQLiteStore(ws), OWNER).store_token(TOKEN)
    return ws


@pytest.fixture
def pushes(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Every `git push` the code runs, captured instead of sent."""
    seen: list[dict[str, Any]] = []
    real_run = subprocess.run

    def fake(command: Any, *args: Any, **kwargs: Any) -> Any:
        if "push" in command:
            seen.append({"command": list(command), "env": dict(kwargs.get("env") or {})})
            return subprocess.CompletedProcess(command, 0, "", "")
        if "ls-remote" in command:  # the receipt's read-back: nothing to say
            return subprocess.CompletedProcess(command, 0, "", "")
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(git_tools.subprocess, "run", fake)
    return seen


def _propose(repo: Path, session_id: str) -> Any:
    broker = ToolBroker(
        workspace_root=repo,
        policy_engine=PolicyEngine(StaticPolicyConfig(repo)),
        store=SQLiteStore(repo),
        principal_id=OWNER,
    )
    result, _decision = broker.execute(
        ToolAction(new_id("act_"), "git_push", {}, "high", True),
        session_id=session_id,
        turn_id=new_id("turn_"),
    )
    return result


def _approval_id(repo: Path) -> str:
    with SQLiteStore(repo).connect() as connection:
        row = connection.execute(
            "SELECT approval_id FROM git_push_bindings ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    assert row is not None
    return str(row[0])


def _approved_push(approval_id: str, session_id: str) -> Any:
    """The target action the approval relay routes after the owner approves."""
    return governed_action(
        "git_push",
        principal_id=OWNER,
        risk_level=RiskLevelValue.HIGH,
        arguments={},
        session_id="sess_inbox",
        origin_session_id=session_id,
        authority_kind="approval",
        authority_id=approval_id,
    )


def test_a_token_stored_in_settings_carries_a_proposed_push(repo: Path) -> None:
    """BUG-334 — the proposal asks the broker, so the vault's token counts."""
    result = _propose(repo, "sess_a")
    assert result.status == "approval_required", result.error
    assert result.output["proposal_preview"]["remote"] == "origin"


def test_with_no_credential_the_refusal_names_settings(repo: Path) -> None:
    GitCredentialBroker(SQLiteStore(repo), OWNER).forget_token()
    result = _propose(repo, "sess_a")
    assert result.status == "failed"
    assert result.error == {"type": "push_credential_unset", "credential": "Settings → GitHub"}


def test_the_approval_records_the_commit_it_showed(repo: Path) -> None:
    """BUG-336 — the binding is written when the owner is asked."""
    _propose(repo, "sess_a")
    binding = SQLiteStore(repo).load_git_push_binding(_approval_id(repo))
    assert binding is not None
    assert binding["head_sha"] == _git(repo, "rev-parse", "main")
    assert binding["remote"] == "origin" and binding["branch"] == "main"
    assert binding["remote_url"] == "https://github.com/acme/demo.git"


def test_a_commit_made_after_the_approval_is_not_pushed(
    repo: Path, pushes: list[dict[str, Any]]
) -> None:
    _propose(repo, "sess_a")
    approval_id = _approval_id(repo)
    store = SQLiteStore(repo)
    GitCredentialBroker(store, OWNER).grant("session", session_id="sess_a")
    (repo / "app.py").write_text("print('later')\n", encoding="utf-8")
    _git(repo, "commit", "-am", "Made after the approval")

    result = GitPushExecutor(repo, store).execute(_approved_push(approval_id, "sess_a"), human(OWNER, role_ids=()))

    assert result.ok is False
    assert result.reason_code == "push_failed:push_target_changed"
    assert result.artifacts["error"]["changed"] == ["head_sha"]
    assert pushes == []


def test_the_push_sends_exactly_the_approved_commit(
    repo: Path, pushes: list[dict[str, Any]]
) -> None:
    _propose(repo, "sess_a")
    approval_id = _approval_id(repo)
    approved = _git(repo, "rev-parse", "main")
    store = SQLiteStore(repo)
    GitCredentialBroker(store, OWNER).grant("session", session_id="sess_a")

    result = GitPushExecutor(repo, store).execute(_approved_push(approval_id, "sess_a"), human(OWNER, role_ids=()))

    assert result.ok is True, result.reason_code
    (push,) = pushes
    assert push["command"][-1] == f"{approved}:refs/heads/main"
    assert push["env"]["RAIKER_GIT_PUSH_TOKEN"] == TOKEN
    assert TOKEN not in " ".join(push["command"])


def test_a_grant_for_one_conversation_does_not_lend_to_another(
    repo: Path, pushes: list[dict[str, Any]]
) -> None:
    """BUG-335 — through the executor, with the session the approval carries."""
    _propose(repo, "sess_b")
    approval_id = _approval_id(repo)
    store = SQLiteStore(repo)
    GitCredentialBroker(store, OWNER).grant("session", session_id="sess_a")

    result = GitPushExecutor(repo, store).execute(_approved_push(approval_id, "sess_b"), human(OWNER, role_ids=()))

    assert result.ok is False
    assert result.reason_code == "git_grant_other_session"
    assert pushes == []


def test_a_grant_for_another_repository_does_not_lend(
    repo: Path, pushes: list[dict[str, Any]]
) -> None:
    _propose(repo, "sess_a")
    approval_id = _approval_id(repo)
    store = SQLiteStore(repo)
    GitCredentialBroker(store, OWNER).grant(
        "once", operation="push", repository="github.com/acme/other"
    )
    result = GitPushExecutor(repo, store).execute(_approved_push(approval_id, "sess_a"), human(OWNER, role_ids=()))
    assert result.reason_code == "git_grant_other_repository"
    assert pushes == []


def test_the_environment_token_no_longer_skips_the_grant(
    repo: Path, pushes: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """GH-13 — a host exporting the legacy variable pushed with no grant at all."""
    store = SQLiteStore(repo)
    GitCredentialBroker(store, OWNER).forget_token()
    monkeypatch.setenv("RAIKER_GITHUB_TOKEN", TOKEN)
    _propose(repo, "sess_a")
    result = GitPushExecutor(repo, store).execute(
        _approved_push(_approval_id(repo), "sess_a"), human(OWNER, role_ids=())
    )
    assert result.reason_code == "git_grant_required"
    assert pushes == []


def test_an_approval_that_recorded_nothing_is_refused(
    repo: Path, pushes: list[dict[str, Any]]
) -> None:
    """One raised before RAIKER-2106 has no binding, and is not run unbound."""
    store = SQLiteStore(repo)
    GitCredentialBroker(store, OWNER).grant("once")
    result = GitPushExecutor(repo, store).execute(_approved_push("apr_old", "sess_a"), human(OWNER, role_ids=()))
    assert result.reason_code == "push_failed:push_binding_missing"
    assert pushes == []


def test_an_ssh_push_uses_the_selected_key_and_pinned_hosts(
    repo: Path, pushes: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """GH-22 end to end through the executor: the lend's SSH command reaches git."""
    from raiker.github.local_methods import SshKeys

    def programs(argv: Any, stdin: Any, env: Any, timeout: float) -> tuple[int, str, str]:
        if argv[:2] == ["ssh-keygen", "-lf"]:
            return 0, "256 SHA256:keyFingerprint000000000000000000000000000000 x (ED25519)\n", ""
        return 1, "", "Hi octo! You've successfully authenticated, but GitHub does not provide shell access.\n"

    _git(repo, "remote", "set-url", "origin", "git@github.com:acme/demo.git")
    key = repo.parent / "id_ed25519"
    key.write_text("KEY", encoding="utf-8")
    store = SQLiteStore(repo)
    broker = GitCredentialBroker(store, OWNER, ssh=SshKeys(programs, home=repo.parent))
    broker.methods.add_ssh(str(key))
    _propose(repo, "sess_a")
    broker.grant("session", session_id="sess_a")
    executor = GitPushExecutor(repo, store)
    monkeypatch.setattr(
        "raiker.runtime.git_credential.GitCredentialBroker",
        lambda store_, principal: GitCredentialBroker(store_, principal, ssh=SshKeys(programs, home=repo.parent)),
    )
    result = executor.execute(_approved_push(_approval_id(repo), "sess_a"), human(OWNER, role_ids=()))
    assert result.ok is True, result.reason_code
    (push,) = pushes
    command = push["env"]["GIT_SSH_COMMAND"]
    assert "IdentitiesOnly=yes" in command and str(key) in command
    assert "github_known_hosts" in command
    assert push["env"].get("RAIKER_GIT_PUSH_TOKEN", "") == ""


def test_a_push_adding_a_credential_is_refused_before_the_owner_is_asked(repo: Path) -> None:
    """TOOL-30 — outgoing commits are scanned with the shapes CI fails on."""
    fake_key = "AKIA" + "Q" * 16  # built at run time so the source holds no key shape
    (repo / "config.py").write_text(f"KEY = '{fake_key}'\n", encoding="utf-8")
    _git(repo, "add", "config.py")
    _git(repo, "commit", "-m", "add config")
    # A later commit removing it does not help: the remote keeps history.
    (repo / "config.py").write_text("KEY = None\n", encoding="utf-8")
    _git(repo, "commit", "-am", "remove key")
    snapshot = git_tools.proposed_push_snapshot(repo, credential_configured=True)
    assert snapshot["status"] == "failed"
    error = snapshot["error"]
    assert error["type"] == "outgoing_commits_contain_credentials"
    assert error["findings"][0]["path"] == "config.py"
    assert error["findings"][0]["line"] == 1
    assert error["findings"][0]["rule"] == "aws_access_key"
    assert fake_key not in str(snapshot)
    # The repository's own dated exception excuses a deliberate fixture.
    (repo / ".github").mkdir()
    exception = {
        "path": "config.py", "fingerprint": error["findings"][0]["fingerprint"],
        "owner": "me", "reason": "fixture", "expires": "2999-01-01",
    }
    (repo / ".github" / "secret-scan-exceptions.json").write_text(
        json.dumps({"exceptions": [exception]}), encoding="utf-8"
    )
    assert git_tools.proposed_push_snapshot(repo, credential_configured=True)["status"] == "success"
