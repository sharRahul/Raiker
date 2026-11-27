"""One authorization rule across every surface; preparation never edits the source."""
from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id
from raiker.contracts.models import ToolAction
from raiker.execution.commands.backends.native import NativeSandboxDriver, NativeSandboxProof
from raiker.execution.task_tree import TaskTree, TaskTreeAuthority
from raiker.execution.workspaces import TaskWorkspaceRegistry
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.path_authority import PathAuthority
from tests.machine_identity_helpers import IdentityBoundTestBroker

SandboxBroker = tuple[IdentityBoundTestBroker, TaskWorkspaceRegistry, Path]


@pytest.fixture
def sandbox_broker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SandboxBroker:
    workspace = tmp_path / "workspace"
    project = workspace / "project"
    project.mkdir(parents=True)
    (project / "notes.txt").write_text("original", encoding="utf-8")
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    store = SQLiteStore(workspace)
    store.upsert_capability_gate_state({
        "capability": "file_write_execution", "state": "enabled_runtime",
        "reason": "Owner enabled files", "created_at": "2026-11-26T00:00:00Z",
        "updated_at": "2026-11-26T00:00:00Z",
    })
    store.upsert_capability_gate_state({
        "capability": "task_management_runtime", "state": "enabled_runtime",
        "reason": "Owner enabled task drafts", "created_at": "2026-11-26T00:00:00Z",
        "updated_at": "2026-11-26T00:00:00Z",
    })
    registry = TaskWorkspaceRegistry(tmp_path / "copies", records=tmp_path / "records")
    registry.bind("principal_owner", "session", project)
    broker = IdentityBoundTestBroker(
        workspace_root=workspace, policy_engine=PolicyEngine(StaticPolicyConfig(workspace)),
        store=store, principal_id="principal_owner",
    )
    broker.path_authority = TaskTreeAuthority(
        PathAuthority(workspace), TaskTree(registry, "principal_owner", "session"),
    )
    monkeypatch.setattr(
        NativeSandboxDriver, "probe",
        lambda self: NativeSandboxProof(True, None, "test_boundary", "2026-11-26T00:00:00Z"),
    )
    return broker, registry, workspace


@pytest.mark.parametrize("surface", ["chat", "build", "design", "goal", "schedule"])
def test_verified_copied_write_runs_without_approval_on_every_surface(
    sandbox_broker: SandboxBroker, surface: str,
) -> None:
    broker, registry, workspace = sandbox_broker
    result, decision = broker.execute(
        ToolAction(new_id("act_"), "write_file", {"path": "project/notes.txt", "text": "prepared"}, "medium", True),
        session_id="session", turn_id=f"turn_{surface}", approval_mode="sandbox",
    )
    assert result.status == "success", result.error
    assert decision.decision == "allow"
    assert (workspace / "project" / "notes.txt").read_text(encoding="utf-8") == "original"
    [(_, copy)] = registry.session_copies("principal_owner", "session")
    assert (copy.root / "notes.txt").read_text(encoding="utf-8") == "prepared"


def test_an_outside_write_still_asks(sandbox_broker: SandboxBroker) -> None:
    broker, _, workspace = sandbox_broker
    result, _ = broker.execute(
        ToolAction(new_id("act_"), "write_file", {"path": "outside.txt", "text": "no"}, "medium", True),
        session_id="session", turn_id="turn_outside", approval_mode="sandbox",
    )
    assert result.status == "approval_required"
    assert not (workspace / "outside.txt").exists()


def test_internal_task_drafting_does_not_require_a_per_step_decision(
    sandbox_broker: SandboxBroker, monkeypatch: pytest.MonkeyPatch,
) -> None:
    broker, _, _ = sandbox_broker
    monkeypatch.setattr(NativeSandboxDriver, "probe", lambda self: NativeSandboxProof(
        False, "no_command_boundary", "test_boundary", "2026-11-27T00:00:00Z",
    ))
    result, decision = broker.execute(
        ToolAction(new_id("act_"), "create_task", {"title": "Prepare a local draft"}, "medium", True),
        session_id="session", turn_id="turn_task_draft", approval_mode="sandbox",
    )
    assert result.status == "success", result.error
    assert decision.decision == "allow"
    assert broker.store is not None and result.output is not None
    task = broker.store.load_task(result.output["artifacts"]["task_id"])
    assert task is not None
    assert task.status != "running"


def test_scheduling_is_not_internal_task_bookkeeping(sandbox_broker: SandboxBroker) -> None:
    broker, _, _ = sandbox_broker
    result, _ = broker.execute(
        ToolAction(new_id("act_"), "create_task", {
            "title": "Future execution", "scheduled_at": "2027-01-01T10:00:00Z",
        }, "medium", True),
        session_id="session", turn_id="turn_schedule", approval_mode="sandbox",
    )
    assert result.status == "approval_required"


def test_an_authorized_failed_edit_is_not_a_policy_denial(sandbox_broker: SandboxBroker) -> None:
    broker, _, workspace = sandbox_broker
    result, decision = broker.execute(
        ToolAction(new_id("act_"), "edit_file", {
            "path": "project/notes.txt", "old_text": "absent", "new_text": "replacement",
        }, "medium", True),
        session_id="session", turn_id="turn_failed_edit", approval_mode="sandbox",
    )
    assert result.status == "failed"
    assert decision.decision == "allow"
    assert (workspace / "project" / "notes.txt").read_text(encoding="utf-8") == "original"


def test_losing_enforcement_after_review_does_not_execute(
    sandbox_broker: SandboxBroker, monkeypatch: pytest.MonkeyPatch,
) -> None:
    broker, _, workspace = sandbox_broker
    probes = 0

    def probe(self: NativeSandboxDriver) -> NativeSandboxProof:
        nonlocal probes
        probes += 1
        return NativeSandboxProof(
            probes < 3, None if probes < 3 else "boundary_lost",
            "test_boundary", "2026-11-27T00:00:00Z",
        )

    monkeypatch.setattr(NativeSandboxDriver, "probe", probe)
    result, _ = broker.execute(
        ToolAction(new_id("act_"), "write_file", {
            "path": "project/notes.txt", "text": "must not execute",
        }, "medium", True),
        session_id="session", turn_id="turn_boundary_lost", approval_mode="sandbox",
    )
    assert probes >= 3
    assert result.status == "approval_required"
    assert (workspace / "project" / "notes.txt").read_text(encoding="utf-8") == "original"


@pytest.mark.parametrize("inside", [False, True])
def test_unattended_work_prepares_but_refuses_consequences(
    sandbox_broker: SandboxBroker, inside: bool,
) -> None:
    broker, _, workspace = sandbox_broker
    result, _ = broker.execute(
        ToolAction(new_id("act_"), "write_file", {
            "path": "project/notes.txt" if inside else "outside.txt", "text": "prepared",
        }, "medium", True),
        session_id="session", turn_id="turn_unattended", approval_mode="dont_ask",
    )
    assert result.status == ("success" if inside else "denied")
    assert (workspace / "project" / "notes.txt").read_text(encoding="utf-8") == "original"


@pytest.mark.parametrize("mode", ["ask", "deny"])
def test_explicit_turn_restrictions_remain_stricter(
    sandbox_broker: SandboxBroker, mode: str,
) -> None:
    broker, _, workspace = sandbox_broker
    result, _ = broker.execute(
        ToolAction(new_id("act_"), "write_file", {"path": "project/notes.txt", "text": "no"}, "medium", True),
        session_id="session", turn_id=f"turn_{mode}", approval_mode="sandbox",
        turn_capability_modes={"file_write_execution": mode},
    )
    assert result.status == ("approval_required" if mode == "ask" else "denied")
    assert (workspace / "project" / "notes.txt").read_text(encoding="utf-8") == "original"


@pytest.mark.parametrize("mode", ["ask", "deny"])
def test_saved_owner_restrictions_remain_stricter(
    sandbox_broker: SandboxBroker, mode: str,
) -> None:
    broker, _, workspace = sandbox_broker
    assert broker.store is not None
    broker.store.upsert_capability_decision_mode({
        "capability": "file_write_execution", "decision_mode": mode,
        "set_by": "principal_owner", "set_at": "2026-11-26T00:00:00Z",
        "reason": "Owner restriction", "event_id": "",
        "created_at": "2026-11-26T00:00:00Z", "updated_at": "2026-11-26T00:00:00Z",
    })
    result, _ = broker.execute(
        ToolAction(new_id("act_"), "write_file", {"path": "project/notes.txt", "text": "no"}, "medium", True),
        session_id="session", turn_id="turn_saved", approval_mode="sandbox",
    )
    assert result.status == ("approval_required" if mode == "ask" else "denied")
    assert (workspace / "project" / "notes.txt").read_text(encoding="utf-8") == "original"


@pytest.mark.parametrize("failure", ["unavailable", "wrong_owner", "wrong_session", "no_tree"])
def test_unverified_preparation_never_writes(
    sandbox_broker: SandboxBroker, monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    broker, registry, workspace = sandbox_broker
    if failure == "unavailable":
        monkeypatch.setattr(
            NativeSandboxDriver, "probe",
            lambda self: NativeSandboxProof(False, "test_unavailable", "test_boundary", "2026-11-26T00:00:00Z"),
        )
    elif failure == "no_tree":
        broker.path_authority = PathAuthority(workspace)
    else:
        broker.path_authority = TaskTreeAuthority(
            PathAuthority(workspace),
            TaskTree(registry, "other" if failure == "wrong_owner" else "principal_owner",
                     "other" if failure == "wrong_session" else "session"),
        )
    result, _ = broker.execute(
        ToolAction(new_id("act_"), "write_file", {
            "path": "project/notes.txt", "text": "no", "sandbox": True, "verified": True,
        }, "medium", True),
        session_id="session", turn_id="turn_unverified", approval_mode="sandbox",
    )
    assert result.status == "approval_required"
    assert (workspace / "project" / "notes.txt").read_text(encoding="utf-8") == "original"
