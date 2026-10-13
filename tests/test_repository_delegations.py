"""ADD-27 GH-50…GH-53, GH-56 — repository delegations, risk classes, revalidation, the connector.

A delegation is the only thing that lets a push or a GitHub write run without a
per-step approval. These tests hold it to the specification's rules: a read
delegation never writes, a pull-request delegation never merges, a branch
pattern never reaches another branch, a child never gets more than its parent,
an agent never makes or widens one, and a delegation that no longer matches the
world (credential, account, installation, repository) stops covering anything.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import utc_now
from raiker.contracts.models import Role
from raiker.control.service import RuntimeControlService
from raiker.events.query import EventViewer
from raiker.events.writer import EventLogWriter
from raiker.github.credentials import reset_verification_cache
from raiker.github.delegations import (
    DELEGABLE_OPERATIONS,
    OPERATION_RISKS,
    DelegationError,
    DelegationService,
    risk_table,
)
from raiker.github.http import GitHubHttp
from raiker.models.tool_registry import DELEGABLE_TOOL_NAMES
from raiker.runtime.authority.models import Principal, PrincipalType
from raiker.runtime.authority.router import CAPABILITY_GATE_MAP, RuntimeAuthority
from raiker.runtime.executors import build_default_executor_registry
from raiker.runtime.executors.base import ExecutionResult
from raiker.runtime.git_credential import RUNTIME_TOKEN_VAR, GitCredentialBroker, GitCredentialError
from raiker.storage.deletion_journal import DELEGATION_REVOKE, journal_path
from raiker.storage.sqlite import SQLiteStore
from tests.factories import governed_action

OWNER = "principal_owner"
REPO = "github.com/acme/demo"
TOKEN = "ghp_delegationTestToken000000000000000000"


@pytest.fixture
def ws(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.delenv("RAIKER_GITHUB_TOKEN", raising=False)
    reset_verification_cache()
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    GitCredentialBroker(SQLiteStore(tmp_path), OWNER).store_token(TOKEN)
    return tmp_path


def _human(store: SQLiteStore) -> Principal:
    raw = store.get_principal(OWNER)
    assert raw is not None
    raw["principal_type"] = PrincipalType(raw["principal_type"])
    return Principal(**raw)


def _agent(store: SQLiteStore | None = None) -> Principal:
    if store is not None and store.get_principal("p_ai") is None:
        store.insert_role(Role(role_id="rl_ai", name="assistant", description="", is_system_role=True, created_at=utc_now()))
        store.insert_principal(
            principal_id="p_ai", principal_type=PrincipalType.AI_AGENT.value,
            display_name="AI", role_ids=("rl_ai",), is_active=True, delegated_by_user_id="owner",
        )
    return Principal(
        principal_id="p_ai", principal_type=PrincipalType.AI_AGENT, display_name="AI",
        role_ids=("rl_ai",), is_active=True,
    )


def _enable(ws: Path, capability: str, mode: str) -> None:
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    with SQLiteStore(ws).connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref) VALUES (?, ?, ?, ?)",
            (capability, OWNER, utc_now(), "docs/threat-models/test.md"),
        )
    enabled = svc.set_capability_state(capability, "enabled_runtime", None, "test", confirmation_token="confirm")
    assert enabled.ok, enabled.reason_code
    assert svc.set_capability_decision_mode(capability, mode, None, "test").ok


def _payloads(ws: Path, event_type: str) -> list[dict[str, Any]]:
    viewer = EventViewer(SQLiteStore(ws))
    rows = viewer.list_events(event_type=event_type, limit=20)
    return [(viewer.read_event_payload(str(row["event_id"])) or {}).get("payload", {}) for row in rows]


def _service(ws: Path) -> DelegationService:
    return DelegationService(SQLiteStore(ws), OWNER)


def _delegate(ws: Path, **overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "repository": REPO, "operations": ["push", "pull_request"], "branch_pattern": "raiker/*",
    }
    fields.update(overrides)
    store = SQLiteStore(ws)
    return DelegationService(store, OWNER).create(created_by=_human(store), **fields)


# ── GH-51: the risk classes ─────────────────────────────────────────────


def test_the_twelve_operations_and_which_may_be_delegated() -> None:
    table = {row["operation"]: row for row in risk_table()}
    assert len(OPERATION_RISKS) == 12 == len(table)
    assert {"read", "fetch", "branch", "commit", "push", "pull_request"} == DELEGABLE_OPERATIONS
    assert table["merge"]["risk"] == "critical" and table["merge"]["default"] == "ask_every_time"
    assert table["delete_branch"]["default"] == "ask_every_time"
    for never in ("protected_branch", "workflows", "repository_permissions", "delete_repository"):
        assert table[never]["default"] == "not_offered" and table[never]["capability"] is None
    # Every operation Raiker offers is governed by a capability the router knows.
    governed = set(CAPABILITY_GATE_MAP.values())
    for row in OPERATION_RISKS:
        assert row.capability is None or row.capability in governed, row


@pytest.mark.parametrize("operation", ["merge", "delete_branch", "workflows", "protected_branch", "delete_repository"])
def test_an_operation_the_matrix_never_delegates_is_refused(ws: Path, operation: str) -> None:
    with pytest.raises(DelegationError) as caught:
        _delegate(ws, operations=["push", operation])
    assert caught.value.reason == f"delegation_operation_not_delegable:{operation}"


# ── GH-50: what a delegation covers ─────────────────────────────────────


def test_only_a_human_may_delegate(ws: Path) -> None:
    store = SQLiteStore(ws)
    with pytest.raises(DelegationError) as caught:
        DelegationService(store, OWNER).create(
            created_by=_agent(), repository=REPO, operations=["fetch"],
        )
    assert caught.value.reason == "delegation_requires_human"


@pytest.mark.parametrize("pattern", [None, "*", "**", "m*", "*/main", "ma?n"])
def test_a_branch_pattern_is_required_and_never_reaches_the_default_branch(ws: Path, pattern: str | None) -> None:
    with pytest.raises(DelegationError) as caught:
        _delegate(ws, operations=["push"], branch_pattern=pattern)
    assert caught.value.reason in {"delegation_branch_pattern_required", "delegation_branch_pattern_too_broad"}


def test_a_read_delegation_never_writes(ws: Path) -> None:
    _delegate(ws, operations=["fetch"], branch_pattern=None)
    service = _service(ws)
    assert service.covering(REPO, "fetch") is not None
    assert service.covering(REPO, "push", "raiker/x") is None
    assert service.covering(REPO, "pull_request", "raiker/x") is None


def test_a_pull_request_delegation_never_merges(ws: Path) -> None:
    _delegate(ws)
    service = _service(ws)
    assert service.covering(REPO, "pull_request", "raiker/fix") is not None
    assert service.covering(REPO, "merge", "raiker/fix") is None
    assert service.covering(REPO, "delete_branch", "raiker/fix") is None


def test_a_branch_delegation_never_reaches_another_branch_or_repository(ws: Path) -> None:
    _delegate(ws)
    service = _service(ws)
    assert service.covering(REPO, "push", "raiker/fix-1") is not None
    assert service.covering(REPO, "push", "feature/fix-1") is None
    assert service.covering(REPO, "push", "main") is None
    assert service.covering(REPO, "push", None) is None
    assert service.covering("github.com/acme/other", "push", "raiker/fix-1") is None
    # A pull request proposes a branch, and it has to be a delegated one.
    assert service.covering(REPO, "pull_request", "feature/fix-1") is None


def test_a_budget_is_spent_once_per_action(ws: Path) -> None:
    row = _delegate(ws, max_actions=2)
    service = _service(ws)
    for action_id, spent in (("a1", True), ("a2", True), ("a3", False)):
        assert service.spend(row, operation="push", branch="raiker/x", action_id=action_id, session_id=None) is spent
    assert service.covering(REPO, "push", "raiker/x") is None
    used = _payloads(ws, "repository_delegation_used")
    assert len(used) == 2
    assert used[0]["allowed_operations"] == ["pull_request", "push"]


# ── GH-53: the child-agent ceiling ──────────────────────────────────────


def test_a_child_gets_at_most_its_parents_delegation(ws: Path) -> None:
    parent = _delegate(ws, max_actions=5)
    service = _service(ws)
    agent = _agent()
    child = service.narrow(parent["delegation_id"], created_by=agent, operations=["push"], branch_pattern="raiker/fix-1", max_actions=2)
    assert child["operations"] == ["push"] and child["max_actions"] == 2
    assert child["expires_at"] <= parent["expires_at"]
    for widening, reason in (
        ({"operations": ["push", "fetch"]}, "delegation_exceeds_parent:operations"),
        ({"branch_pattern": "*"}, "delegation_exceeds_parent:branch_pattern"),
        ({"branch_pattern": "feature/x"}, "delegation_exceeds_parent:branch_pattern"),
        ({"branch_pattern": "raiker/fix-*"}, "delegation_exceeds_parent:branch_pattern"),
        ({"expires_in_hours": 24 * 29}, "delegation_exceeds_parent:expires_at"),
        ({"max_actions": 6}, "delegation_exceeds_parent:max_actions"),
    ):
        with pytest.raises(DelegationError) as caught:
            service.narrow(parent["delegation_id"], created_by=agent, **widening)
        assert caught.value.reason == reason


def test_a_childs_action_spends_the_parents_budget_and_ends_with_it(ws: Path) -> None:
    parent = _delegate(ws, max_actions=2)
    service = _service(ws)
    child = service.narrow(parent["delegation_id"], created_by=_agent(), operations=["push"])
    assert service.spend(child, operation="push", branch="raiker/x", action_id="a1", session_id=None)
    assert service.get(parent["delegation_id"])["actions_used"] == 1
    grandchild = service.narrow(child["delegation_id"], created_by=_agent())
    service.revoke(parent["delegation_id"], revoked_by=_human(SQLiteStore(ws)))
    assert service.get(child["delegation_id"])["state"] == "revoked"
    assert service.get(grandchild["delegation_id"])["state"] == "revoked"
    assert not service.spend(grandchild, operation="push", branch="raiker/x", action_id="a2", session_id=None)


def test_git_and_github_writes_are_never_handed_to_a_subagent() -> None:
    for tool in ("git_push", "github_write", "git_fetch", "git_clone", "git_commit", "git_branch", "github_read"):
        assert tool not in DELEGABLE_TOOL_NAMES


def test_revocation_is_journaled_and_human_only(ws: Path) -> None:
    parent = _delegate(ws)
    service = _service(ws)
    child = service.narrow(parent["delegation_id"], created_by=_agent())
    with pytest.raises(DelegationError):
        service.revoke(parent["delegation_id"], revoked_by=_agent())
    revoked = service.revoke(parent["delegation_id"], revoked_by=_human(SQLiteStore(ws)))
    assert revoked == [parent["delegation_id"], child["delegation_id"]]
    lines = [json.loads(line) for line in journal_path(ws).read_text().splitlines() if line.strip()]
    journaled = {entry["id"] for entry in lines if entry["kind"] == DELEGATION_REVOKE}
    assert journaled == set(revoked)


# ── GH-52: revalidation before the next consequential step ─────────────


def _discovered(ws: Path, *, status: str = "available", repository_id: str = "900", installation_id: str | None = None) -> None:
    store = SQLiteStore(ws)
    credential = GitCredentialBroker(store, OWNER).methods.selected() or {}
    with store.connect() as connection:
        connection.execute("DELETE FROM github_repositories")
        connection.execute(
            """INSERT INTO github_repositories
               (principal_id, credential_id, repository_id, full_name, installation_id, private,
                permissions_json, status, selected, checked_at)
               VALUES (?, ?, ?, 'acme/demo', ?, 1, '{}', ?, 0, ?)""",
            (OWNER, credential.get("credential_id"), repository_id, installation_id, status, utc_now()),
        )


def test_a_delegation_that_still_holds_revalidates_clean(ws: Path) -> None:
    _discovered(ws)
    row = _delegate(ws)
    assert row["repository_id"] == "900"
    assert _service(ws).revalidate(row) == []


def test_revalidation_names_what_changed(ws: Path) -> None:
    _discovered(ws)
    row = _delegate(ws)
    service = _service(ws)
    _discovered(ws, status="removed")
    assert "repository_access_removed" in service.revalidate(row)
    _discovered(ws, repository_id="901")  # deleted and re-created under the same name
    assert "repository_identity_changed" in service.revalidate(row)
    _discovered(ws, installation_id="7")  # reached through an installation that is gone
    assert "installation_removed" in service.revalidate(row)


def test_removing_or_switching_the_credential_ends_the_delegation(ws: Path) -> None:
    row = _delegate(ws)
    store = SQLiteStore(ws)
    broker = GitCredentialBroker(store, OWNER)
    broker.methods.remove(str(row["credential_id"]))
    assert "credential_removed" in _service(ws).revalidate(row)


def test_revalidation_asks_github_whose_repository_it_is_now(ws: Path) -> None:
    _discovered(ws)
    row = _delegate(ws)
    answers = {"id": 900}

    def github(method: str, url: str, headers: Mapping[str, str], body: bytes | None) -> tuple[int, Mapping[str, str], bytes]:
        assert url == "https://api.github.com/repos/acme/demo"
        assert headers["Authorization"] == f"Bearer {TOKEN}"
        if answers.get("missing"):
            return 404, {}, b"{}"
        return 200, {}, json.dumps({"id": answers["id"]}).encode()

    service = _service(ws)
    assert service.revalidate(row, http=GitHubHttp(github)) == []
    answers["id"] = 901
    assert service.revalidate(row, http=GitHubHttp(github)) == ["repository_identity_changed"]
    answers["missing"] = 1
    assert service.revalidate(row, http=GitHubHttp(github)) == ["repository_access_removed"]


# ── GH-50: the router ───────────────────────────────────────────────────


class _StubPush:
    """Stands in for the push executor: says where it would push, records how it ran."""

    capability = "git_push_execution"

    def __init__(self) -> None:
        self.ran: list[tuple[str, str]] = []

    def repository_target(self, action: Any, principal: Principal) -> dict[str, Any]:
        return {"repository": REPO, "operation": "push", "branch": str(action.arguments.get("branch"))}

    def execute(self, action: Any, principal: Principal) -> ExecutionResult:
        self.ran.append((action.authority_kind, action.authority_id))
        return ExecutionResult(ok=True, capability=self.capability, action_id=action.action_id, summary="pushed", artifacts={})


def _authority(ws: Path, stub: _StubPush, mode: str = "always_allow") -> RuntimeAuthority:
    _enable(ws, "git_push_execution", mode)
    store = SQLiteStore(ws)
    registry = build_default_executor_registry(ws, store)
    registry.register("git_push_execution", stub)
    return RuntimeAuthority(store, EventLogWriter(store), executor_registry=registry)


def _push(branch: str) -> Any:
    return governed_action(
        "git_push", principal_id="p_ai", arguments={"remote": "origin", "branch": branch}, risk_level="high"
    )


def test_allow_mode_alone_no_longer_pushes_for_an_agent(ws: Path) -> None:
    stub = _StubPush()
    authority = _authority(ws, stub)
    result = authority.route_action(_push("raiker/x"), _agent(SQLiteStore(ws)))
    assert result.decision == "needs_approval"
    assert stub.ran == []
    refused = _payloads(ws, "repository_delegation_refused")
    assert refused and refused[0]["problems"] == ["delegation_required"]


def test_a_standing_grant_alone_does_not_cover_a_push(ws: Path) -> None:
    stub = _StubPush()
    authority = _authority(ws, stub, mode="ask")
    store = SQLiteStore(ws)
    created = authority.create_standing_grant(
        granted_by=_human(store), principal_id="p_ai", action_type="git_push", risk_ceiling="high",
    )
    assert isinstance(created, dict)
    result = authority.route_action(_push("raiker/x"), _agent(store))
    assert result.decision == "needs_approval" and stub.ran == []


def test_a_covering_delegation_runs_the_push_under_its_own_name(ws: Path) -> None:
    stub = _StubPush()
    authority = _authority(ws, stub, mode="ask")
    row = _delegate(ws, max_actions=1)
    store = SQLiteStore(ws)
    result = authority.route_action(_push("raiker/x"), _agent(store))
    assert result.decision == "allow", result.message
    assert stub.ran == [("delegation", row["delegation_id"])]
    # Its one action is spent; the next push asks.
    again = authority.route_action(_push("raiker/x"), _agent(store))
    assert again.decision == "needs_approval" and len(stub.ran) == 1


def test_a_delegation_for_another_branch_asks(ws: Path) -> None:
    stub = _StubPush()
    authority = _authority(ws, stub)
    _delegate(ws)
    result = authority.route_action(_push("main"), _agent(SQLiteStore(ws)))
    assert result.decision == "needs_approval" and stub.ran == []


def test_a_delegation_revoked_mid_task_parks_the_next_step(ws: Path) -> None:
    """RR-40's shape: the first step runs, the owner revokes, the next one waits for them."""
    stub = _StubPush()
    authority = _authority(ws, stub)
    row = _delegate(ws)
    store = SQLiteStore(ws)
    assert authority.route_action(_push("raiker/x"), _agent(store)).decision == "allow"
    DelegationService(store, OWNER).revoke(row["delegation_id"], revoked_by=_human(store))
    parked = authority.route_action(_push("raiker/x"), _agent(store))
    assert parked.decision == "needs_approval" and len(stub.ran) == 1


def test_an_approved_push_does_not_need_a_delegation(ws: Path) -> None:
    from dataclasses import replace

    stub = _StubPush()
    authority = _authority(ws, stub, mode="ask")
    store = SQLiteStore(ws)
    approved = replace(_push("raiker/x"), authority_kind="approval", authority_id="appr_x")
    result = authority.route_action(approved, _human(store))
    assert result.decision == "allow" and stub.ran == [("approval", "appr_x")]


# ── the lend under a delegation ─────────────────────────────────────────


def test_a_delegation_lends_the_credential_for_its_own_branch_only(ws: Path) -> None:
    row = _delegate(ws)
    broker = GitCredentialBroker(SQLiteStore(ws), OWNER)
    with broker.lend(operation="push", repository=REPO, branch="raiker/x", delegation_id=row["delegation_id"]) as env:
        assert env[RUNTIME_TOKEN_VAR] == TOKEN
    with pytest.raises(GitCredentialError) as caught, broker.lend(
        operation="push", repository=REPO, branch="main", delegation_id=row["delegation_id"]
    ):
        pass
    assert caught.value.reason == "git_delegation_does_not_cover"
    lent = _payloads(ws, "git_credential_lent")
    assert lent[0]["scope"] == "delegation"
    assert TOKEN not in json.dumps(lent)


# ── GH-56: the API connector borrows through the broker ────────────────


def _connector(ws: Path, seen: list[dict[str, str]]) -> Any:
    from raiker.runtime.connectors import GithubConnectorService

    def fetch(url: str, headers: dict[str, str]) -> dict[str, Any]:
        seen.append(headers)
        return {"body_text": json.dumps({"title": "T", "state": "open", "body": "b"}), "status": 200}

    store = SQLiteStore(ws)
    _agent(store)  # the turn's agent, acting for the owner
    return GithubConnectorService(ws, store, fetch_fn=fetch, principal_id="p_ai")


def _allow_connector(ws: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from raiker.runtime import connectors

    monkeypatch.setattr(connectors, "connector_egress_allowlist", lambda: ("api.github.com",))
    _enable(ws, "connector_github_runtime", "always_allow")


def test_the_connector_reads_with_the_selected_vault_credential(ws: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _allow_connector(ws, monkeypatch)
    seen: list[dict[str, str]] = []
    outcome = _connector(ws, seen).read("issue", "acme/demo", 1)
    assert outcome["status"] == "success", outcome
    assert seen[0]["Authorization"] == f"Bearer {TOKEN}"
    lent = _payloads(ws, "git_credential_lent")
    assert lent[0]["scope"] == "api" and lent[0]["operation"] == "read_issue"


def test_the_connector_still_reads_the_legacy_variable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    monkeypatch.setenv("RAIKER_GITHUB_TOKEN", "ghp_legacyEnvironmentToken00000000000000")
    _allow_connector(tmp_path, monkeypatch)
    seen: list[dict[str, str]] = []
    assert _connector(tmp_path, seen).read("pull_request", "acme/demo", 2)["status"] == "success"
    assert seen[0]["Authorization"] == "Bearer ghp_legacyEnvironmentToken00000000000000"


def test_the_connector_refuses_with_nothing_selected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RAIKER_GITHUB_TOKEN", raising=False)
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    _allow_connector(tmp_path, monkeypatch)
    seen: list[dict[str, str]] = []
    outcome = _connector(tmp_path, seen).read("issue", "acme/demo", 1)
    assert outcome["status"] != "success" and seen == []


# ── GH-55: the issue-to-PR routine template ─────────────────────────────


def test_the_issue_to_pr_routine_is_read_only_without_a_delegation(ws: Path) -> None:
    from raiker.github.routines import plan_issue_to_pr

    plan = plan_issue_to_pr(SQLiteStore(ws), OWNER, repository=REPO, work_branch="raiker/issue-7")
    decisions = {step["step"]: step["decision"] for step in plan["steps"]}
    assert decisions["read_issue"] == "runs" and decisions["fetch"] == "asks"
    assert {decisions[s] for s in ("branch", "commit", "push", "pull_request")} == {"asks"}
    assert "merge" in plan["never"]


def test_the_routine_writes_only_what_its_delegation_names(ws: Path) -> None:
    from raiker.github.routines import plan_issue_to_pr

    row = _delegate(ws, operations=["fetch", "branch", "commit", "push", "pull_request"])
    store = SQLiteStore(ws)
    plan = plan_issue_to_pr(store, OWNER, repository=REPO, work_branch="raiker/issue-7", delegation_id=row["delegation_id"])
    assert {s["decision"] for s in plan["steps"] if s["operation"] != "read"} == {"runs_under_delegation"}
    off_pattern = plan_issue_to_pr(store, OWNER, repository=REPO, work_branch="main", delegation_id=row["delegation_id"])
    assert {s["decision"] for s in off_pattern["steps"] if s["step"] in ("push", "branch")} == {"asks"}


def test_a_scheduled_run_creates_no_authority_and_parks_when_its_delegation_ends(ws: Path) -> None:
    from raiker.github.routines import plan_issue_to_pr

    row = _delegate(ws)
    store = SQLiteStore(ws)
    before = len(DelegationService(store, OWNER).delegations(include_ended=True))
    DelegationService(store, OWNER).revoke(row["delegation_id"], revoked_by=_human(store))
    plan = plan_issue_to_pr(store, OWNER, repository=REPO, work_branch="raiker/x", delegation_id=row["delegation_id"])
    assert plan["blocked_needs_owner"] is True and "delegation_revoked" in plan["delegation_problems"]
    assert {s["decision"] for s in plan["steps"] if s["operation"] != "read"} == {"asks"}
    assert len(DelegationService(store, OWNER).delegations(include_ended=True)) == before


# ── BUG-337: a local branch and commit answer to the same rule ──────────


def _git_repo(ws: Path, remote: str | None) -> None:
    import subprocess

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=ws, check=True, capture_output=True)

    git("init", "-q", "-b", "main")
    git("config", "user.email", "owner@example.invalid")
    git("config", "user.name", "Owner")
    (ws / "README.md").write_text("demo\n", encoding="utf-8")
    git("add", "README.md")
    git("commit", "-q", "-m", "first")
    if remote is not None:
        git("remote", "add", "origin", remote)


def _git_writes(ws: Path, mode: str = "always_allow") -> RuntimeAuthority:
    _enable(ws, "git_write_execution", mode)
    store = SQLiteStore(ws)
    return RuntimeAuthority(store, EventLogWriter(store), executor_registry=build_default_executor_registry(ws, store))


def _branch(name: str) -> Any:
    return governed_action("git_branch", principal_id="p_ai", arguments={"name": name}, risk_level="medium")


def test_a_branch_on_a_github_repository_needs_a_delegation_that_covers_it(ws: Path) -> None:
    _git_repo(ws, "https://github.com/acme/demo.git")
    authority = _git_writes(ws)
    store = SQLiteStore(ws)
    # Allow mode alone no longer creates a branch for an agent on a GitHub repository.
    assert authority.route_action(_branch("raiker/feature"), _agent(store)).decision == "needs_approval"
    _delegate(ws, operations=["branch", "commit"])
    assert authority.route_action(_branch("raiker/feature"), _agent(store)).decision == "allow"
    # The pattern limits where the agent branches.
    assert authority.route_action(_branch("hotfix"), _agent(store)).decision == "needs_approval"


def test_the_executor_names_the_repository_and_the_branch_a_commit_lands_on(ws: Path) -> None:
    from raiker.runtime.executors.tier1_git import GitWriteExecutor

    _git_repo(ws, "git@github.com:Acme/Demo.git")
    executor = GitWriteExecutor(ws, SQLiteStore(ws))
    commit = governed_action("git_commit", principal_id="p_ai", arguments={"message": "x"}, risk_level="medium")
    assert executor.repository_target(commit, _agent()) == {
        "repository": REPO, "operation": "commit", "branch": "main",
    }


def test_a_repository_with_no_github_remote_keeps_the_decision_mode(ws: Path) -> None:
    from raiker.runtime.executors.tier1_git import GitWriteExecutor

    _git_repo(ws, None)
    assert GitWriteExecutor(ws, SQLiteStore(ws)).repository_target(_branch("x"), _agent()) is None
    _git_repo_remote = "https://gitlab.example.com/acme/demo.git"
    import subprocess

    subprocess.run(["git", "remote", "add", "origin", _git_repo_remote], cwd=ws, check=True)
    assert GitWriteExecutor(ws, SQLiteStore(ws)).repository_target(_branch("x"), _agent()) is None
    authority = _git_writes(ws)
    assert authority.route_action(_branch("anything"), _agent(SQLiteStore(ws))).decision == "allow"


# ── BUG-338: the router asks GitHub before a delegated push ─────────────


def test_a_delegated_push_asks_github_once_per_burst_and_stops_when_it_moved(
    ws: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from raiker.github.delegations import reset_remote_checks

    _discovered(ws)
    stub = _StubPush()
    authority = _authority(ws, stub)
    _delegate(ws)
    asked: list[str] = []
    answer = {"id": 900}

    def github(method: str, url: str, headers: Mapping[str, str], body: bytes | None) -> tuple[int, Mapping[str, str], bytes]:
        asked.append(url)
        return 200, {}, json.dumps({"id": answer["id"]}).encode()

    monkeypatch.setattr(RuntimeAuthority, "_delegation_http", lambda _self: GitHubHttp(github))
    monkeypatch.setattr(
        "raiker.github.credentials.CredentialMethods.secret",
        lambda _self, _credential, **_kw: TOKEN,
    )
    store = SQLiteStore(ws)
    assert authority.route_action(_push("raiker/a"), _agent(store)).decision == "allow"
    assert authority.route_action(_push("raiker/b"), _agent(store)).decision == "allow"
    assert asked == ["https://api.github.com/repos/acme/demo"]  # one question for the burst

    reset_remote_checks()
    answer["id"] = 901  # transferred and re-created since discovery
    parked = authority.route_action(_push("raiker/c"), _agent(store))
    assert parked.decision == "needs_approval" and len(stub.ran) == 2
    refused = _payloads(ws, "repository_delegation_refused")
    assert refused and refused[0]["problems"] == ["repository_identity_changed"]


def test_github_out_of_reach_blocks_the_step_for_the_owner(ws: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from raiker.github.http import GitHubHttpError

    _discovered(ws)
    stub = _StubPush()
    authority = _authority(ws, stub)
    _delegate(ws)

    def offline(*_args: object) -> tuple[int, Mapping[str, str], bytes]:
        raise GitHubHttpError("github_unreachable:URLError")

    monkeypatch.setattr(RuntimeAuthority, "_delegation_http", lambda _self: GitHubHttp(offline))
    monkeypatch.setattr(
        "raiker.github.credentials.CredentialMethods.secret",
        lambda _self, _credential, **_kw: TOKEN,
    )
    result = authority.route_action(_push("raiker/a"), _agent(SQLiteStore(ws)))
    assert result.decision == "needs_approval" and stub.ran == []
    assert _payloads(ws, "repository_delegation_refused")[0]["problems"] == ["github_unreachable"]
