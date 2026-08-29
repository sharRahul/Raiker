"""B11 — the governed git write path.

Build could read a repository (``git_status`` / ``git_diff`` / ``git_log``) and
describe a change it could neither commit nor propose. This suite pins what
closes that gap:

- ``git_branch`` and ``git_commit`` are advertised to the model, take the
  approval path, and are never answered ``unknown_or_denied_tool``;
- each computes its proposal without touching the repository, and fails closed
  with a named reason for every case a later execution could not honour;
- the ``git_write_execution`` capability has a real executor, a gate the owner
  can see, and an activation requirement entry — the trio a capability needs to
  be turnable-on at all;
- approving really performs the change, and the sentence shown before the
  decision says so;
- an approved commit never runs the repository's own hooks, so a governed write
  cannot become an un-governed code-execution path;
- ``github_write`` proposes the work outward under the connector's own gate,
  credential and egress allowlist.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from raiker.approvals.execution import EXECUTABLE_ON_APPROVAL, executable_capability
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id
from raiker.contracts.models import ToolAction
from raiker.models.contracts import ToolCallProposal
from raiker.models.tool_call_validation import (
    ToolCallRejected,
    default_tool_specs,
    validate_tool_call,
)
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
from raiker.runtime.executors.tier1_git import GitWriteExecutor
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.git import (
    create_branch,
    create_commit,
    proposed_branch_snapshot,
    proposed_commit_snapshot,
)
from tests.machine_identity_helpers import IdentityBoundTestBroker as ToolBroker

_CAP = "git_write_execution"


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A workspace that is a git repository with one commit on ``main``."""
    ws = tmp_path / "repo"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    _git(ws, "init", "--initial-branch=main", ".")
    _git(ws, "config", "user.name", "Raiker Test")
    _git(ws, "config", "user.email", "raiker-test@example.com")
    (ws / "app.py").write_text("print('one')\n", encoding="utf-8")
    _git(ws, "add", "app.py")
    _git(ws, "commit", "-m", "initial")
    return ws


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
    def test_write_tools_are_advertised(self) -> None:
        names = {spec.name for spec in default_tool_specs()}
        assert {"git_branch", "git_commit", "github_write"} <= names

    def test_commit_paths_are_advertised_as_a_list(self) -> None:
        # Without a schema fragment a model has no way to learn `paths` is a
        # list, and would send a stringified one the tool must then refuse.
        spec = next(s for s in default_tool_specs() if s.name == "git_commit")
        assert spec.parameters["properties"]["paths"]["type"] == "array"

    def test_validation_requires_the_arguments_the_tool_needs(self) -> None:
        for tool, args in (
            ("git_branch", {}),
            ("git_commit", {}),
            ("github_write", {"operation": "create_pull_request"}),
        ):
            with pytest.raises(ToolCallRejected):
                validate_tool_call(
                    ToolCallProposal(call_id="call_1", tool_name=tool, arguments=args)
                )

    def test_a_valid_call_is_medium_risk_and_still_approval_bound(self) -> None:
        """The two facts this test used to run together, separated.

        A local commit changes state on this machine, nobody outside it can see
        it, and it is reversible — `medium` by the definitions in
        `raiker.policy.risk`. It parks anyway, because parking is decided by
        `approval_required_actions` and not by the band. Asserting both here is
        the point: "high" used to mean "this parks", which left no word for
        "this is dangerous".
        """
        action = validate_tool_call(
            ToolCallProposal(
                call_id="call_1",
                tool_name="git_commit",
                arguments={"message": "Fix the thing"},
            )
        )
        assert action.risk_level == "medium"
        assert action.requires_approval is True


class TestPolicy:
    def test_the_write_tools_take_the_approval_path(self, tmp_path: Path) -> None:
        engine = PolicyEngine(StaticPolicyConfig(tmp_path))
        for tool in ("git_branch", "git_commit", "github_write"):
            decision = engine.review(ToolAction(new_id("act_"), tool, {}, "high", True))
            assert decision.decision == "needs_approval", tool
            assert "unknown_or_denied_tool" not in decision.reasons, tool


class TestGovernanceWiring:
    def test_the_capability_is_real_registered_and_enableable(self, tmp_path: Path) -> None:
        store = SQLiteStore(tmp_path)
        registry = build_default_executor_registry(tmp_path, store)
        assert _CAP in REAL_EXECUTOR_CAPABILITIES
        assert registry.has(_CAP)
        # A capability with an executor and no requirement entry cannot be turned
        # on at all — the exact shape of BUG-62.
        assert get_activation_requirement(_CAP) is not None
        assert _CAP in default_capability_gates()

    def test_both_tools_answer_to_one_owner_switch(self) -> None:
        assert CAPABILITY_GATE_MAP["git_branch"] == _CAP
        assert CAPABILITY_GATE_MAP["git_commit"] == _CAP
        # A GitHub write is the same credential reaching the same host as the
        # read, so it answers to the connector's gate rather than a second one.
        assert CAPABILITY_GATE_MAP["github_write"] == "connector_github_runtime"

    def test_approving_executes_rather_than_records(self) -> None:
        assert _CAP in EXECUTABLE_ON_APPROVAL
        assert executable_capability("git_branch") == _CAP
        assert executable_capability("git_commit") == _CAP
        assert executable_capability("github_write") == "connector_github_runtime"


class TestBranchProposal:
    def test_a_non_repository_fails_closed(self, tmp_path: Path) -> None:
        result = proposed_branch_snapshot(tmp_path, "feature/x")
        assert result["error"]["type"] == "not_a_git_repository"

    @pytest.mark.parametrize("name", ["", "  ", "-x", "refs/heads/x", "bad name", "a..b"])
    def test_a_name_git_would_reject_fails_closed(self, repo: Path, name: str) -> None:
        result = proposed_branch_snapshot(repo, name)
        assert result["error"]["type"] == "invalid_branch_name", name

    def test_an_existing_branch_fails_closed(self, repo: Path) -> None:
        _git(repo, "branch", "feature/x")
        assert proposed_branch_snapshot(repo, "feature/x")["error"]["type"] == "branch_exists"

    def test_an_unknown_base_fails_closed(self, repo: Path) -> None:
        result = proposed_branch_snapshot(repo, "feature/x", "nope")
        assert result["error"]["type"] == "unknown_base_ref"

    def test_a_base_switch_refuses_to_move_uncommitted_work(self, repo: Path) -> None:
        _git(repo, "branch", "other")
        (repo / "app.py").write_text("print('two')\n", encoding="utf-8")
        result = proposed_branch_snapshot(repo, "feature/x", "other")
        assert result["error"]["type"] == "working_tree_dirty"
        # Without a base there is nothing to move to, so the same tree is fine.
        assert proposed_branch_snapshot(repo, "feature/x")["status"] == "success"

    def test_a_proposal_changes_nothing(self, repo: Path) -> None:
        snapshot = proposed_branch_snapshot(repo, "feature/x")
        assert snapshot["status"] == "success"
        assert snapshot["current_branch"] == "main"
        heads = subprocess.run(
            ["git", "-C", str(repo), "branch", "--list"],
            check=True, capture_output=True, text=True,
        ).stdout
        assert "feature/x" not in heads


class TestCommitProposal:
    def test_an_empty_message_fails_closed(self, repo: Path) -> None:
        assert proposed_commit_snapshot(repo, "  ")["error"]["type"] == "empty_commit_message"

    def test_nothing_to_commit_fails_closed(self, repo: Path) -> None:
        assert proposed_commit_snapshot(repo, "noop")["error"]["type"] == "nothing_to_commit"

    def test_a_path_outside_the_repository_fails_closed(self, repo: Path) -> None:
        result = proposed_commit_snapshot(repo, "msg", ["../escape.txt"])
        assert result["error"]["type"] == "path_outside_repository"

    def test_the_proposal_names_every_file_and_shows_the_whole_diff(self, repo: Path) -> None:
        (repo / "app.py").write_text("print('two')\n", encoding="utf-8")
        (repo / "new.py").write_text("print('new')\n", encoding="utf-8")
        snapshot = proposed_commit_snapshot(repo, "Change one, add one")
        assert snapshot["status"] == "success"
        states = {entry["path"]: entry["state"] for entry in snapshot["files"]}
        assert states == {"app.py": "modified", "new.py": "untracked"}
        # An untracked file has no `git diff` of its own; the owner still has to
        # be able to read what a commit would record.
        assert "+print('two')" in snapshot["diff"]
        assert "+print('new')" in snapshot["diff"]
        assert snapshot["branch"] == "main"

    def test_a_proposal_leaves_the_index_alone(self, repo: Path) -> None:
        (repo / "new.py").write_text("print('new')\n", encoding="utf-8")
        proposed_commit_snapshot(repo, "Add one")
        staged = subprocess.run(
            ["git", "-C", str(repo), "diff", "--cached", "--name-only"],
            check=True, capture_output=True, text=True,
        ).stdout
        assert staged.strip() == ""

    def test_the_workspace_state_directory_is_never_proposed(self, repo: Path) -> None:
        # `.raiker/` holds the vault key, the encrypted store and the audit log.
        # A commit that swept the working tree would write the owner's own key
        # material into git history, which is the opposite of what approving a
        # commit was for.
        (repo / ".raiker").mkdir(exist_ok=True)
        (repo / ".raiker" / "app.key").write_text("secret\n", encoding="utf-8")
        (repo / "new.py").write_text("print('new')\n", encoding="utf-8")
        snapshot = proposed_commit_snapshot(repo, "Add one")
        assert [entry["path"] for entry in snapshot["files"]] == ["new.py"]
        assert create_commit(repo, "Add one")["status"] == "success"
        tracked = subprocess.run(
            ["git", "-C", str(repo), "ls-files"],
            check=True, capture_output=True, text=True,
        ).stdout
        assert ".raiker" not in tracked

    def test_a_rename_is_committed_at_both_ends(self, repo: Path) -> None:
        # Staging only the new path records the addition and leaves the old
        # file's deletion behind — a half-recorded rename the owner was told was
        # one change. The source half is already staged by `git mv`, so it needs
        # no `git add` of its own; asking for one fails, because it matches
        # neither the working tree nor the index any more.
        _git(repo, "mv", "app.py", "renamed.py")
        (repo / "added.py").write_text("print('added')\n", encoding="utf-8")
        snapshot = proposed_commit_snapshot(repo, "Rename and add")
        assert snapshot["commit_paths"] == ["app.py", "renamed.py", "added.py"]
        assert create_commit(repo, "Rename and add")["status"] == "success"
        # Nothing of the change set is left behind. `.raiker/` still shows as
        # untracked, which is the point: it is never swept into a commit.
        remaining = [
            line
            for line in subprocess.run(
                ["git", "-C", str(repo), "status", "--porcelain"],
                check=True, capture_output=True, text=True,
            ).stdout.splitlines()
            if ".raiker" not in line
        ]
        assert remaining == []
        tracked = subprocess.run(
            ["git", "-C", str(repo), "ls-files"],
            check=True, capture_output=True, text=True,
        ).stdout.split()
        assert tracked == ["added.py", "renamed.py"]

    def test_a_deletion_is_committed(self, repo: Path) -> None:
        (repo / "app.py").unlink()
        assert create_commit(repo, "Drop app.py")["status"] == "success"
        assert (
            subprocess.run(
                ["git", "-C", str(repo), "ls-files"],
                check=True, capture_output=True, text=True,
            ).stdout.strip()
            == ""
        )

    def test_a_protected_path_is_refused_by_name(self, repo: Path) -> None:
        result = proposed_commit_snapshot(repo, "msg", [".raiker/app.key"])
        assert result["error"]["type"] == "protected_workspace_path"

    def test_paths_limit_the_proposal(self, repo: Path) -> None:
        (repo / "app.py").write_text("print('two')\n", encoding="utf-8")
        (repo / "other.py").write_text("print('other')\n", encoding="utf-8")
        snapshot = proposed_commit_snapshot(repo, "Only app", ["app.py"])
        assert [entry["path"] for entry in snapshot["files"]] == ["app.py"]


class TestExecution:
    def test_a_branch_is_created_and_checked_out(self, repo: Path) -> None:
        result = create_branch(repo, "feature/x")
        assert result["status"] == "success"
        assert result["previous_branch"] == "main"
        current = subprocess.run(
            ["git", "-C", str(repo), "symbolic-ref", "--short", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        assert current == "feature/x"

    def test_a_commit_is_recorded(self, repo: Path) -> None:
        (repo / "new.py").write_text("print('new')\n", encoding="utf-8")
        result = create_commit(repo, "Add new.py")
        assert result["status"] == "success"
        log = subprocess.run(
            ["git", "-C", str(repo), "log", "--oneline"],
            check=True, capture_output=True, text=True,
        ).stdout
        assert "Add new.py" in log
        assert proposed_commit_snapshot(repo, "again")["error"]["type"] == "nothing_to_commit"

    def test_a_path_limited_commit_records_only_those_paths(self, repo: Path) -> None:
        (repo / "app.py").write_text("print('two')\n", encoding="utf-8")
        (repo / "other.py").write_text("print('other')\n", encoding="utf-8")
        assert create_commit(repo, "Only app", ["app.py"])["status"] == "success"
        remaining = proposed_commit_snapshot(repo, "rest")
        assert [entry["path"] for entry in remaining["files"]] == ["other.py"]

    def test_repository_hooks_never_run(self, repo: Path) -> None:
        # A governed write must not become an un-governed code-execution path:
        # `.git/hooks` is workspace content the agent may itself have written.
        hooks = repo / ".git" / "hooks"
        hooks.mkdir(parents=True, exist_ok=True)
        hook = hooks / "pre-commit"
        hook.write_text(
            "#!/bin/sh\ntouch '" + str(repo / "HOOK_RAN") + "'\n", encoding="utf-8"
        )
        hook.chmod(0o755)
        (repo / "new.py").write_text("print('new')\n", encoding="utf-8")
        assert create_commit(repo, "Add new.py")["status"] == "success"
        assert not (repo / "HOOK_RAN").exists()

    def test_a_commit_during_a_merge_fails_closed(self, repo: Path) -> None:
        (repo / ".git" / "MERGE_HEAD").write_text("deadbeef\n", encoding="utf-8")
        (repo / "new.py").write_text("print('new')\n", encoding="utf-8")
        result = create_commit(repo, "mid-merge")
        assert result["error"]["type"] == "repository_busy"
        assert result["error"]["operation"] == "merge"


class TestExecutor:
    def test_the_executor_performs_each_operation(self, repo: Path) -> None:
        executor = GitWriteExecutor(repo)
        branch = executor.execute(_action("git_branch", {"name": "feature/x"}), _principal())
        assert branch.ok and branch.artifacts["branch"] == "feature/x"

        (repo / "new.py").write_text("print('new')\n", encoding="utf-8")
        commit = executor.execute(
            _action("git_commit", {"message": "Add new.py"}), _principal()
        )
        assert commit.ok
        assert commit.artifacts["files"] == ["new.py"]
        assert commit.artifacts["branch"] == "feature/x"
        # The owner who just approved a repository change is told which commit
        # now exists, not only that something ran.
        assert commit.artifacts["summary"].startswith("Committed 1 file(s) as ")
        assert branch.artifacts["summary"] == (
            "Created and checked out feature/x (from main)."
        )

    def test_a_rejected_operation_names_its_reason(self, repo: Path) -> None:
        result = GitWriteExecutor(repo).execute(
            _action("git_branch", {"name": "bad name"}), _principal()
        )
        assert not result.ok
        assert result.reason_code == "branch_failed:invalid_branch_name"

    def test_an_unknown_operation_fails_closed(self, repo: Path) -> None:
        result = GitWriteExecutor(repo).execute(_action("git_push", {}), _principal())
        assert not result.ok
        assert result.reason_code == "unknown_git_operation:git_push"


class TestBrokerSurface:
    def _broker(self, repo: Path) -> ToolBroker:
        store = SQLiteStore(repo)
        return ToolBroker(
            workspace_root=repo,
            policy_engine=PolicyEngine(StaticPolicyConfig(repo), store=store),
            store=store,
            principal_id="principal_owner",
        )

    def test_the_approval_carries_the_proposal_the_owner_reviews(self, repo: Path) -> None:
        (repo / "new.py").write_text("print('new')\n", encoding="utf-8")
        broker = self._broker(repo)
        result, decision = broker.execute(
            ToolAction(new_id("act_"), "git_commit", {"message": "Add new.py"}, "high", True),
            session_id="sess_1",
            turn_id="turn_1",
        )
        assert result.status == "approval_required"
        assert decision.decision == "needs_approval"
        assert result.output is not None
        preview = result.output["proposal_preview"]
        assert preview["status"] == "success"
        assert [entry["path"] for entry in preview["files"]] == ["new.py"]
        # Nothing ran: the approval is the pause, not the commit.
        log = subprocess.run(
            ["git", "-C", str(repo), "log", "--oneline"],
            check=True, capture_output=True, text=True,
        ).stdout
        assert "Add new.py" not in log

    def test_the_sentence_says_what_approving_does(self, repo: Path) -> None:
        broker = self._broker(repo)
        branch = ToolAction(new_id("act_"), "git_branch", {"name": "feature/x"}, "high", True)
        commit = ToolAction(new_id("act_"), "git_commit", {"message": "m"}, "high", True)
        write = ToolAction(
            new_id("act_"),
            "github_write",
            {"operation": "create_pull_request", "repo": "octo/repo"},
            "high",
            True,
        )
        # With the gates off the honest answer is that nothing is executed; the
        # relay-on wording is asserted where the gates are on (the live spec).
        for action in (branch, commit, write):
            sentence = broker._expected_effect(action, False)
            assert isinstance(sentence, str) and sentence


class TestApprovalDetailPreview:
    def test_a_commit_is_reviewed_as_a_repository_change(self, repo: Path) -> None:
        from raiker.control.dashboard import DashboardService

        (repo / "new.py").write_text("print('new')\n", encoding="utf-8")
        diff, path, kind = DashboardService(repo)._build_preview(
            "git_commit", {"message": "Add new.py"}
        )
        assert kind == "git_change"
        assert path == "main"
        assert diff is not None and "new.py" in diff

    def test_a_branch_is_reviewed_as_the_refs_it_moves_between(self, repo: Path) -> None:
        from raiker.control.dashboard import DashboardService

        diff, path, kind = DashboardService(repo)._build_preview(
            "git_branch", {"name": "feature/x"}
        )
        assert kind == "git_change"
        assert path == "feature/x"
        assert diff is not None and "main → feature/x" in diff

    def test_an_impossible_proposal_falls_back_to_arguments(self, repo: Path) -> None:
        from raiker.control.dashboard import DashboardService

        diff, _path, kind = DashboardService(repo)._build_preview("git_commit", {"message": "m"})
        assert kind == "arguments"
        assert diff is None


class TestGithubPullRequest:
    """The outward half of B11 — proposing the branch to the repository."""

    def _service(self, workspace: Path, store: SQLiteStore):  # type: ignore[no-untyped-def]
        from raiker.runtime.connectors import GithubConnectorService

        return GithubConnectorService(workspace, store)

    @pytest.mark.parametrize(
        ("kwargs", "reason"),
        [
            ({"repo": "not-a-repo"}, "invalid_repo"),
            ({"title": ""}, "empty_title"),
            ({"head": ""}, "empty_head"),
            ({"base": ""}, "empty_base"),
            ({"head": "a b"}, "invalid_head"),
            ({"head": "main"}, "head_equals_base"),
        ],
    )
    def test_argument_validation_fails_closed(
        self, tmp_path: Path, kwargs: dict[str, str], reason: str
    ) -> None:
        ws = tmp_path / "gh"
        ws.mkdir()
        bootstrap_owner("owner", "Owner", workspace_root=ws)
        call = {
            "repo": "octo/repo",
            "title": "Fix the thing",
            "head": "feature/x",
            "base": "main",
            "body": "why",
            **kwargs,
        }
        outcome = self._service(ws, SQLiteStore(ws)).create_pull_request(**call)
        assert outcome["status"] == "failed"
        assert outcome["error"]["type"] == reason

    def test_the_gate_fails_closed_before_the_network(self, tmp_path: Path) -> None:
        ws = tmp_path / "gh"
        ws.mkdir()
        bootstrap_owner("owner", "Owner", workspace_root=ws)
        outcome = self._service(ws, SQLiteStore(ws)).create_pull_request(
            "octo/repo", "Fix", "feature/x", "main"
        )
        assert outcome["status"] == "denied"
        assert outcome["error"]["type"] == "connector_gate_disabled"

    def test_a_governed_call_returns_the_pull_request_as_untrusted_data(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ws = tmp_path / "gh"
        ws.mkdir()
        bootstrap_owner("owner", "Owner", workspace_root=ws)
        monkeypatch.setenv("RAIKER_GITHUB_TOKEN", "ghp_secrettoken")
        monkeypatch.setenv("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", "api.github.com")

        def _post(url: str, payload: dict[str, object], **_: object) -> dict[str, object]:
            assert url == "https://api.github.com/repos/octo/repo/pulls"
            assert payload == {
                "title": "Fix the thing",
                "head": "feature/x",
                "base": "main",
                "body": "why",
            }
            body = json.dumps({"number": 7, "html_url": "https://github.com/octo/repo/pull/7"})
            return {"status": 201, "body_bytes": len(body), "body_text": body, "truncated": False}

        monkeypatch.setattr("raiker.runtime.connectors.post_json_url", _post)
        outcome = self._service(ws, SQLiteStore(ws)).create_pull_request(
            "octo/repo", "Fix the thing", "feature/x", "main", "why", enforce_modes=False
        )
        assert outcome["status"] == "success"
        assert outcome["number"] == 7
        assert outcome["untrusted"] is True
        assert "untrusted data" in outcome["content"]

    def test_the_executor_routes_the_pull_request_operation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from raiker.runtime.executors.connectors import GithubConnectorExecutor

        ws = tmp_path / "gh"
        ws.mkdir()
        bootstrap_owner("owner", "Owner", workspace_root=ws)
        monkeypatch.setenv("RAIKER_GITHUB_TOKEN", "ghp_secrettoken")
        monkeypatch.setenv("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", "api.github.com")
        body = json.dumps({"number": 7, "html_url": "https://github.com/octo/repo/pull/7"})
        monkeypatch.setattr(
            "raiker.runtime.connectors.post_json_url",
            lambda *a, **k: {"status": 201, "body_bytes": len(body), "body_text": body, "truncated": False},
        )
        result = GithubConnectorExecutor(ws, SQLiteStore(ws)).execute(
            _action(
                "github_write",
                {
                    "operation": "create_pull_request",
                    "repo": "octo/repo",
                    "title": "Fix the thing",
                    "head": "feature/x",
                    "base": "main",
                    "body": "why",
                },
            ),
            _principal(),
        )
        assert result.ok
        assert result.artifacts["number"] == 7
        # The proposed text is the owner's material, not audit metadata.
        assert result.artifacts["content_redacted"] is True
