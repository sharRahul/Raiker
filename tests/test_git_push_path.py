"""BUG-67 — the governed push, and BUG-66 — the repository it runs in.

B11 let the agent create a branch and record a commit on it, and stopped there:
the branch existed only on this machine, so ``github_write`` could not open a
pull request for a head GitHub had never seen. "Make the change, commit it, open
the PR" broke in the middle. This suite pins what closes that gap:

- ``git_push`` is advertised, takes the approval path, and is never answered
  ``unknown_or_denied_tool``;
- it answers to its **own** capability, ``git_push_execution``, rather than to
  ``git_write_execution`` — an owner who let the agent commit has not thereby
  let it publish;
- the proposal is computed without touching the network, and fails closed with a
  named reason for an unknown remote, a remote this process holds no credential
  for, a host the owner has not allowlisted, a missing credential, and a branch
  with nothing the remote does not already have;
- the execution never forces and never deletes, runs no repository hook, and
  keeps the credential out of the command line;
- and the git tools run in the repository the owner *selected* in Build rather
  than always in the workspace root (BUG-66).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from machine_identity_helpers import IdentityBoundTestBroker as ToolBroker

from raiker.approvals.execution import EXECUTABLE_ON_APPROVAL, executable_capability
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id
from raiker.contracts.models import ToolAction
from raiker.models.contracts import ToolCallProposal
from raiker.models.tool_call_validation import default_tool_specs, validate_tool_call
from raiker.phase_gates import default_capability_gates
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.runtime.authority.activation import get_activation_requirement
from raiker.runtime.authority.models import Principal, PrincipalType, RiskLevelValue
from raiker.runtime.authority.router import CAPABILITY_GATE_MAP, GovernedAction
from raiker.runtime.executors import (
    REAL_EXECUTOR_CAPABILITIES,
    build_default_executor_registry,
)
from raiker.runtime.executors.tier1_git import GitPushExecutor
from raiker.storage.sqlite import SQLiteStore
from raiker.tools import git as git_tools
from raiker.tools.git import (
    proposed_push_snapshot,
    push_branch,
    repository_label,
    resolve_repository_root,
    selected_repository_subpath,
)

_CAP = "git_push_execution"
_REMOTE = "https://github.com/owner/repo.git"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A workspace that is a git repository with one commit and a GitHub remote.

    Ambient `GIT_CONFIG_*` entries are cleared: a host that configures a global
    `url.<base>.insteadOf` would otherwise rewrite the remotes these tests set,
    and the refusals below would be asserting the host's config rather than the
    product's rules.
    """
    for key in [name for name in os.environ if name.startswith("GIT_CONFIG")]:
        monkeypatch.delenv(key, raising=False)
    ws = tmp_path / "repo"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    _git(ws, "init", "--initial-branch=main", ".")
    _git(ws, "config", "user.name", "Raiker Test")
    _git(ws, "config", "user.email", "raiker-test@example.com")
    (ws / "app.py").write_text("print('one')\n", encoding="utf-8")
    _git(ws, "add", "app.py")
    _git(ws, "commit", "-m", "initial")
    _git(ws, "remote", "add", "origin", _REMOTE)
    return ws


@pytest.fixture
def allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The owner's two boundaries, both satisfied."""
    monkeypatch.setenv("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", "github.com")
    monkeypatch.setenv("RAIKER_GITHUB_TOKEN", "ghp_test_token_value")


def _principal() -> Principal:
    return Principal(
        principal_id="principal_owner",
        principal_type=PrincipalType.HUMAN,
        display_name="Owner",
    )


def _action(tool: str, args: dict[str, object]) -> GovernedAction:
    return GovernedAction(
        action_id=new_id("act_"),
        principal_id="principal_owner",
        action_type=tool,
        tool_or_service_name=tool,
        arguments=args,
        risk_level=RiskLevelValue.HIGH,
    )


class TestToolSurface:
    def test_push_is_advertised(self) -> None:
        assert "git_push" in {spec.name for spec in default_tool_specs()}

    def test_both_arguments_are_optional(self) -> None:
        # The checked-out branch and the remote it already tracks are the answer
        # when the model names neither, so requiring either would make the
        # ordinary case a guess the model has to get right.
        spec = next(s for s in default_tool_specs() if s.name == "git_push")
        assert spec.parameters["required"] == []
        assert set(spec.parameters["properties"]) == {"remote", "branch"}

    def test_a_valid_call_is_high_risk_and_approval_bound(self) -> None:
        action = validate_tool_call(
            ToolCallProposal(call_id="call_1", tool_name="git_push", arguments={})
        )
        assert action.risk_level == "high"
        assert action.requires_approval is True


class TestPolicy:
    def test_push_takes_the_approval_path(self, tmp_path: Path) -> None:
        engine = PolicyEngine(StaticPolicyConfig(tmp_path))
        decision = engine.review(ToolAction(new_id("act_"), "git_push", {}, "high", True))
        assert decision.decision == "needs_approval"

    def test_the_capability_is_never_hard_denied(self, tmp_path: Path) -> None:
        # FIXED-98's invariant: a capability the runtime authority routes on but
        # which is in neither policy set is answered `unknown_or_denied_tool` on
        # its way to the executor that was built to carry it out.
        engine = PolicyEngine(StaticPolicyConfig(tmp_path))
        decision = engine.review(ToolAction(new_id("act_"), _CAP, {}, "high", True))
        assert decision.decision == "needs_approval"

    def test_push_is_its_own_capability(self) -> None:
        # The whole point of BUG-67: letting the agent commit is not letting it
        # publish, so the two cannot share one switch.
        assert CAPABILITY_GATE_MAP["git_push"] == _CAP
        assert CAPABILITY_GATE_MAP["git_branch"] == "git_write_execution"
        assert _CAP != "git_write_execution"


class TestCapabilityTrio:
    """A real executor, a gate the owner can see, and an activation requirement."""

    def test_the_capability_has_a_real_executor(self, tmp_path: Path) -> None:
        assert _CAP in REAL_EXECUTOR_CAPABILITIES
        registry = build_default_executor_registry(tmp_path, SQLiteStore(tmp_path))
        assert registry.get(_CAP) is not None

    def test_the_capability_has_a_gate_and_is_egress_tiered(self) -> None:
        gate = default_capability_gates()[_CAP]
        # Tier 2 rather than Tier 1: the branch and the commit stay on the
        # machine, this one does not.
        assert gate.phase == 2

    def test_the_capability_can_be_activated(self) -> None:
        requirement = get_activation_requirement(_CAP)
        assert requirement is not None

    def test_approving_really_pushes(self) -> None:
        assert _CAP in EXECUTABLE_ON_APPROVAL
        assert executable_capability("git_push") == _CAP


class TestProposalFailsClosed:
    def test_not_a_repository(self, tmp_path: Path) -> None:
        result = proposed_push_snapshot(tmp_path)
        assert result["error"]["type"] == "not_a_git_repository"

    def test_no_remote(self, repo: Path, allowed: None) -> None:
        _git(repo, "remote", "remove", "origin")
        assert proposed_push_snapshot(repo)["error"]["type"] == "no_remote_configured"

    def test_unknown_remote(self, repo: Path, allowed: None) -> None:
        result = proposed_push_snapshot(repo, "upstream")
        assert result["error"]["type"] == "unknown_remote"
        assert result["error"]["remote"] == "upstream"

    def test_unknown_branch(self, repo: Path, allowed: None) -> None:
        result = proposed_push_snapshot(repo, None, "nope")
        assert result["error"]["type"] == "unknown_branch"

    def test_an_ssh_remote_is_refused(self, repo: Path, allowed: None) -> None:
        # An SSH remote authenticates with a key this process does not govern and
        # carries no host the egress allowlist can be checked against.
        _git(repo, "remote", "set-url", "origin", "git@github.com:owner/repo.git")
        assert proposed_push_snapshot(repo)["error"]["type"] == "unsupported_remote_url"

    def test_a_plaintext_remote_is_refused(self, repo: Path, allowed: None) -> None:
        _git(repo, "remote", "set-url", "origin", "http://github.com/owner/repo.git")
        assert proposed_push_snapshot(repo)["error"]["type"] == "insecure_remote_url"

    def test_a_remote_carrying_its_own_credential_is_refused(
        self, repo: Path, allowed: None
    ) -> None:
        # A credential baked into the remote URL would be used instead of the
        # owner's governed one, and would be pushed past every check below it.
        _git(repo, "remote", "set-url", "origin", "https://user:pw@github.com/owner/repo.git")
        assert proposed_push_snapshot(repo)["error"]["type"] == "remote_url_has_credentials"

    def test_a_host_the_credential_does_not_belong_to_is_refused(
        self, repo: Path, allowed: None
    ) -> None:
        # `RAIKER_GITHUB_TOKEN` is a GitHub credential. Sending it to another
        # forge because a remote happens to be HTTPS is a credential leak.
        _git(repo, "remote", "set-url", "origin", "https://gitlab.com/owner/repo.git")
        result = proposed_push_snapshot(repo)
        assert result["error"]["type"] == "unsupported_remote_host"
        assert result["error"]["host"] == "gitlab.com"

    def test_a_host_the_owner_has_not_allowlisted_is_refused(
        self, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", "")
        monkeypatch.setenv("RAIKER_GITHUB_TOKEN", "ghp_test_token_value")
        result = proposed_push_snapshot(repo)
        assert result["error"]["type"] == "push_egress_denied"
        assert result["error"]["host"] == "github.com"

    def test_a_missing_credential_is_refused(
        self, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", "github.com")
        monkeypatch.delenv("RAIKER_GITHUB_TOKEN", raising=False)
        result = proposed_push_snapshot(repo)
        assert result["error"]["type"] == "push_credential_unset"

    def test_nothing_to_push(self, repo: Path, allowed: None) -> None:
        # A tracking ref that already holds this branch's head means the remote
        # has everything; approving a no-op is noise the owner should not be
        # asked for.
        _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        assert proposed_push_snapshot(repo)["error"]["type"] == "nothing_to_push"


class TestProposal:
    def test_it_names_the_remote_the_branch_and_the_commits(
        self, repo: Path, allowed: None
    ) -> None:
        (repo / "app.py").write_text("print('two')\n", encoding="utf-8")
        _git(repo, "commit", "-am", "Change the print")
        snapshot = proposed_push_snapshot(repo)
        assert snapshot["status"] == "success"
        assert snapshot["remote"] == "origin"
        assert snapshot["host"] == "github.com"
        assert snapshot["branch"] == "main"
        # No tracking ref: the remote has never seen this branch, and the
        # preview says so rather than implying an update.
        assert snapshot["creates_remote_branch"] is True
        assert snapshot["commit_count"] == 2
        assert any("Change the print" in line for line in snapshot["commits"])

    def test_it_counts_only_what_the_remote_lacks(self, repo: Path, allowed: None) -> None:
        _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        (repo / "app.py").write_text("print('two')\n", encoding="utf-8")
        _git(repo, "commit", "-am", "Change the print")
        snapshot = proposed_push_snapshot(repo)
        assert snapshot["commit_count"] == 1
        assert snapshot["creates_remote_branch"] is False

    def test_it_touches_neither_the_network_nor_the_repository(
        self, repo: Path, allowed: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Reading the remote's refs would be egress performed *before* the owner
        # approved any. The preview says what this machine last knew.
        forbidden = ("ls-remote", "fetch", "push")
        real_run = subprocess.run

        def guard(command: Any, *args: Any, **kwargs: Any) -> Any:
            assert not set(command) & set(forbidden), command
            return real_run(command, *args, **kwargs)

        monkeypatch.setattr(git_tools.subprocess, "run", guard)
        before = _git(repo, "rev-parse", "HEAD")
        assert proposed_push_snapshot(repo)["status"] == "success"
        assert _git(repo, "rev-parse", "HEAD") == before


class TestExecution:
    def _capture(self, monkeypatch: pytest.MonkeyPatch, returncode: int = 0,
                 stderr: str = "") -> dict[str, Any]:
        seen: dict[str, Any] = {}
        real_run = subprocess.run

        def fake(command: Any, *args: Any, **kwargs: Any) -> Any:
            if "push" in command:
                seen["command"] = list(command)
                seen["env"] = dict(kwargs.get("env") or {})
                seen["timeout"] = kwargs.get("timeout")
                return subprocess.CompletedProcess(command, returncode, "", stderr)
            return real_run(command, *args, **kwargs)

        monkeypatch.setattr(git_tools.subprocess, "run", fake)
        return seen

    def test_it_never_forces_and_never_deletes(
        self, repo: Path, allowed: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen = self._capture(monkeypatch)
        result = push_branch(repo)
        assert result["status"] == "success"
        command = seen["command"]
        assert "--force" not in command and "-f" not in command
        assert "--delete" not in command and "--mirror" not in command
        # The refspec is written out in full, so a branch name can neither be
        # read as an option nor move a ref it does not name.
        assert command[-1] == "refs/heads/main:refs/heads/main"

    def test_repository_hooks_never_run(
        self, repo: Path, allowed: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # `.git/hooks/pre-push` is workspace content the agent may itself have
        # written; running it would make a governed push an un-governed
        # code-execution path.
        seen = self._capture(monkeypatch)
        push_branch(repo)
        assert "core.hooksPath=raiker-no-such-hooks" in seen["command"]

    def test_the_credential_stays_out_of_the_command_line(
        self, repo: Path, allowed: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen = self._capture(monkeypatch)
        push_branch(repo)
        assert not any("ghp_test_token_value" in part for part in seen["command"])
        assert seen["env"]["RAIKER_GIT_PUSH_TOKEN"] == "ghp_test_token_value"
        # An empty helper first, so a system keychain cannot quietly supply a
        # different account's credential than the one the owner governed.
        assert seen["command"].index("credential.helper=") < len(seen["command"])
        assert seen["env"]["GIT_TERMINAL_PROMPT"] == "0"

    def test_a_rejected_push_is_named(
        self, repo: Path, allowed: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._capture(monkeypatch, returncode=1, stderr="! [rejected] main -> main (non-fast-forward)")
        result = push_branch(repo)
        assert result["error"]["type"] == "push_rejected_non_fast_forward"

    def test_a_refused_credential_is_named(
        self, repo: Path, allowed: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._capture(monkeypatch, returncode=1, stderr="fatal: Authentication failed for 'https://github.com/'")
        result = push_branch(repo)
        assert result["error"]["type"] == "push_authentication_failed"

    def test_the_credential_is_redacted_out_of_git_output(
        self, repo: Path, allowed: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._capture(monkeypatch, returncode=128, stderr="fatal: bad url ghp_test_token_value")
        result = push_branch(repo)
        assert "ghp_test_token_value" not in str(result)

    def test_the_executor_refuses_before_the_owner_allows_egress(
        self, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The gate being on is not the last word: the executor re-checks the
        # owner's allowlist and credential against the machine as it is now.
        monkeypatch.setenv("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", "")
        monkeypatch.setenv("RAIKER_GITHUB_TOKEN", "ghp_test_token_value")
        executor = GitPushExecutor(repo, SQLiteStore(repo))
        result = executor.execute(_action("git_push", {}), _principal())
        assert result.ok is False
        assert result.reason_code == "push_failed:push_egress_denied"
        assert result.summary == "Push refused; nothing left this machine."

    def test_the_executor_reports_what_it_sent(
        self, repo: Path, allowed: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._capture(monkeypatch)
        executor = GitPushExecutor(repo, SQLiteStore(repo))
        result = executor.execute(_action("git_push", {}), _principal())
        assert result.ok is True
        assert result.artifacts["remote"] == "origin"
        assert result.artifacts["branch"] == "main"
        assert result.artifacts["created_remote_branch"] is True
        assert result.summary.startswith("Pushed 1 commit(s) on main to origin (github.com)")

    def test_an_unknown_operation_fails_closed(self, repo: Path) -> None:
        executor = GitPushExecutor(repo, SQLiteStore(repo))
        result = executor.execute(_action("git_commit", {}), _principal())
        assert result.ok is False
        assert result.reason_code == "unknown_git_operation:git_commit"


class TestUnperformableProposal:
    """A proposal the runtime already refused is a refusal, not a decision."""

    def test_a_push_with_nothing_to_send_never_reaches_the_owner(
        self, repo: Path, allowed: None
    ) -> None:
        # Asking someone to approve a push that cannot happen wastes the one
        # thing the approval queue is for, and only tells them after they
        # decided. The model gets the named reason instead, which is what lets it
        # correct the call rather than wait on a person.
        _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        broker = ToolBroker(
            workspace_root=repo,
            policy_engine=PolicyEngine(StaticPolicyConfig(repo)),
            store=SQLiteStore(repo),
            principal_id="principal_owner",
        )
        result, decision = broker.execute(
            ToolAction(new_id("act_"), "git_push", {}, "high", True),
            session_id=new_id("sess_"),
            turn_id=new_id("turn_"),
        )
        assert decision.decision == "needs_approval"
        assert result.status == "failed"
        assert result.error == {
            "type": "nothing_to_push",
            "remote": "origin",
            "branch": "main",
        }

    def test_a_push_it_can_perform_still_asks(self, repo: Path, allowed: None) -> None:
        broker = ToolBroker(
            workspace_root=repo,
            policy_engine=PolicyEngine(StaticPolicyConfig(repo)),
            store=SQLiteStore(repo),
            principal_id="principal_owner",
        )
        result, _decision = broker.execute(
            ToolAction(new_id("act_"), "git_push", {}, "high", True),
            session_id=new_id("sess_"),
            turn_id=new_id("turn_"),
        )
        assert result.status == "approval_required"
        assert result.output is not None
        assert result.output["proposal_preview"]["remote"] == "origin"
        assert result.output["proposal_preview"]["repository"] == "."


class TestSelectedRepository:
    """BUG-66 — the git tools run in the repository the owner picked."""

    @pytest.fixture
    def workspace(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        """A workspace that is *not* a repository, holding one that is."""
        for key in [name for name in os.environ if name.startswith("GIT_CONFIG")]:
            monkeypatch.delenv(key, raising=False)
        ws = tmp_path / "ws"
        (ws / "service").mkdir(parents=True)
        bootstrap_owner("owner", "Owner", workspace_root=ws)
        inner = ws / "service"
        _git(inner, "init", "--initial-branch=main", ".")
        _git(inner, "config", "user.name", "Raiker Test")
        _git(inner, "config", "user.email", "raiker-test@example.com")
        (inner / "main.py").write_text("print('service')\n", encoding="utf-8")
        _git(inner, "add", "main.py")
        _git(inner, "commit", "-m", "initial")
        return ws

    def _select(self, workspace: Path) -> tuple[SQLiteStore, str]:
        store = SQLiteStore(workspace)
        owner = store.account_scope("principal_owner") or "principal_owner"
        store.insert_code_repo(
            repo_id=new_id("repo_"),
            owner_principal_id=owner,
            kind="local",
            label="service",
            local_subpath="service",
        )
        repo_id = str(store.list_code_repos(owner)[0]["repo_id"])
        store.select_code_repo(owner, repo_id)
        return store, owner

    def test_nothing_selected_is_the_workspace(self, workspace: Path) -> None:
        store = SQLiteStore(workspace)
        assert selected_repository_subpath(store, "principal_owner") is None
        assert resolve_repository_root(workspace, None) == workspace.resolve()

    def test_the_selected_sub_folder_is_the_repository(self, workspace: Path) -> None:
        store, owner = self._select(workspace)
        assert selected_repository_subpath(store, owner) == "service"
        assert resolve_repository_root(workspace, "service") == (workspace / "service").resolve()

    def test_a_sub_path_that_escapes_the_workspace_is_ignored(self, workspace: Path) -> None:
        # Containment is the same check every other path read uses, and failing
        # it falls back to the workspace rather than widening the tools' reach.
        assert resolve_repository_root(workspace, "../elsewhere") == workspace.resolve()
        assert resolve_repository_root(workspace, "service/missing") == workspace.resolve()

    def test_the_label_is_workspace_relative(self, workspace: Path) -> None:
        assert repository_label(workspace, workspace) == "."
        assert repository_label(workspace, workspace / "service") == "service"

    def test_the_broker_reads_the_selected_repository(self, workspace: Path) -> None:
        # Before this, `git_status` reported the workspace's own repository — or
        # `not_a_git_repository` when, as here, the workspace is not one — while
        # the connection surface promised the agent was in the one the owner
        # picked.
        store, owner = self._select(workspace)
        broker = ToolBroker(
            workspace_root=workspace,
            policy_engine=PolicyEngine(StaticPolicyConfig(workspace)),
            store=store,
            principal_id="principal_owner",
        )
        assert broker.git_root() == (workspace / "service").resolve()
        (workspace / "service" / "extra.py").write_text("x = 1\n", encoding="utf-8")
        status = broker.executors["git_status"]({})
        assert status["status"] == "success"
        assert "extra.py" in status["output"]

    def test_the_executor_commits_in_the_selected_repository(self, workspace: Path) -> None:
        from raiker.runtime.executors.tier1_git import GitWriteExecutor

        store, _ = self._select(workspace)
        (workspace / "service" / "extra.py").write_text("x = 1\n", encoding="utf-8")
        executor = GitWriteExecutor(workspace, store)
        result = executor.execute(
            _action("git_commit", {"message": "Add extra"}), _principal()
        )
        assert result.ok is True
        assert result.artifacts["repository"] == "service"
        assert result.artifacts["files"] == ["extra.py"]
        assert "in service." in result.summary
        assert _git(workspace / "service", "log", "-1", "--pretty=%s") == "Add extra"
