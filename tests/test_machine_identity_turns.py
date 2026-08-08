from __future__ import annotations

from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id
from raiker.contracts.models import (
    AgentResponse,
    ClientMetadata,
    PromptEnvelope,
    PromptOptions,
    PromptPayload,
    ToolAction,
    UserMetadata,
)
from raiker.control.dashboard import DashboardService
from raiker.events.writer import EventLogWriter
from raiker.gateway.agent_gateway import AgentGateway
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.runtime.identity.lifecycle import (
    TrustedTurnIdentity,
    TurnMachineIdentityLifecycle,
)
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.broker import ToolBroker, ToolExecutionContext


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    return workspace


def _envelope() -> PromptEnvelope:
    return PromptEnvelope(
        request_id=new_id("req_"),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
        client=ClientMetadata(type="test_harness", name="tests", version="0.0.0"),
        user=UserMetadata(id="principal_owner"),
        prompt=PromptPayload(text="hello"),
        options=PromptOptions(),
    )


@pytest.mark.anyio
async def test_gateway_passes_machine_identity_to_runtime_and_deactivates_terminal_turn(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    gateway = AgentGateway(workspace, principal_id="principal_owner")
    envelope = _envelope()
    captured: list[TrustedTurnIdentity] = []

    async def completed(
        prompt: PromptEnvelope, *, identity: TrustedTurnIdentity | None = None
    ) -> AgentResponse:
        assert identity is not None
        captured.append(identity)
        return AgentResponse(
            request_id=prompt.request_id,
            session_id=prompt.session_id,
            turn_id=prompt.turn_id,
            status="completed",
            message="done",
        )

    gateway.runtime.ahandle = completed  # type: ignore[assignment]

    response = await gateway.submit_prompt_async(envelope)

    assert response.status == "completed"
    assert len(captured) == 1
    identity = captured[0]
    assert identity.claims.owner_principal_id == "principal_owner"
    assert identity.claims.turn_id == envelope.turn_id
    row = SQLiteStore(workspace).get_turn_machine_identity(identity.claims.principal_id)
    assert row is not None and row["is_active"] is False
    principal = SQLiteStore(workspace).get_principal(identity.claims.principal_id)
    assert principal is not None and principal["is_active"] is False
    event_types = {
        event["event_type"]
        for event in SQLiteStore(workspace).list_event_index(
            session_id=envelope.session_id, limit=100
        )
    }
    assert {"machine_identity_issued", "machine_identity_deactivated"} <= event_types
    views = DashboardService(workspace).list_events(session_id=envelope.session_id)
    attributed = [view for view in views if view.machine_identity is not None]
    assert attributed
    assert attributed[0].machine_identity is not None
    assert attributed[0].machine_identity.principal_id == identity.claims.principal_id


def test_suspended_turn_rotates_token_without_changing_subject(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    lifecycle = TurnMachineIdentityLifecycle(workspace)
    first = lifecycle.start(
        owner_principal_id="principal_owner",
        session_id="sess_1",
        turn_id="turn_1",
        role_ids=("assistant",),
    )

    second = lifecycle.rotate(
        owner_principal_id="principal_owner",
        session_id="sess_1",
        turn_id="turn_1",
        principal_id=first.claims.principal_id,
        role_ids=("assistant",),
    )

    assert second.claims.subject == first.claims.subject
    assert second.claims.principal_id == first.claims.principal_id
    assert second.claims.token_id != first.claims.token_id
    assert second.token != first.token


def test_child_identity_records_parent_without_widening_roles(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    lifecycle = TurnMachineIdentityLifecycle(workspace)
    parent = lifecycle.start(
        owner_principal_id="principal_owner",
        session_id="sess_1",
        turn_id="turn_parent",
        role_ids=("developer",),
    )

    child = lifecycle.start(
        owner_principal_id="principal_owner",
        session_id="sess_1",
        turn_id="turn_child",
        role_ids=("assistant",),
        parent_principal_id=parent.claims.principal_id,
    )

    row = SQLiteStore(workspace).get_turn_machine_identity(child.claims.principal_id)
    assert row is not None
    assert row["parent_principal_id"] == parent.claims.principal_id
    assert child.claims.role_ids == ("assistant",)


def _broker(workspace: Path) -> ToolBroker:
    store = SQLiteStore(workspace)
    return ToolBroker(
        workspace_root=workspace,
        policy_engine=PolicyEngine(StaticPolicyConfig(workspace)),
        store=store,
        writer=EventLogWriter(store),
        principal_id="principal_owner",
    )


def test_broker_refuses_missing_identity_before_action_policy_hooks_or_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(tmp_path)
    broker = _broker(workspace)
    broker.executors["list_directory"] = lambda _args: pytest.fail("tool executed")
    monkeypatch.setattr(
        broker.policy_engine,
        "review",
        lambda _action: pytest.fail("policy reviewed an unauthenticated action"),
    )
    action = ToolAction(
        new_id("act_"), "list_directory", {"path": "."}, "medium", False
    )

    result, decision = broker.execute(
        action, session_id="sess_1", turn_id="turn_1", machine_identity=None
    )

    assert result.status == "denied"
    assert result.error == {"type": "machine_identity_missing"}
    assert decision.reasons == ["machine_identity_missing"]
    events = SQLiteStore(workspace).list_event_index(session_id="sess_1", limit=100)
    assert "action_proposed" not in {event["event_type"] for event in events}
    assert "machine_identity_refused" in {event["event_type"] for event in events}


def test_broker_binds_verified_actor_and_keeps_owner_as_resource_scope(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    broker = _broker(workspace)
    identity = TurnMachineIdentityLifecycle(workspace).start(
        owner_principal_id="principal_owner",
        session_id="sess_1",
        turn_id="turn_1",
        role_ids=("assistant",),
    )
    captured: list[ToolExecutionContext] = []

    def execute_with_context(
        _arguments: dict[str, object], context: ToolExecutionContext
    ) -> dict[str, object]:
        captured.append(context)
        return {"status": "success"}

    broker.context_executors["list_directory"] = execute_with_context
    action = ToolAction(
        new_id("act_"),
        "list_directory",
        {"path": ".", "principal_id": "principal_attacker"},
        "medium",
        False,
        proposed_by="principal_attacker",
    )

    result, _decision = broker.execute(
        action,
        session_id="sess_1",
        turn_id="turn_1",
        machine_identity=identity,
    )

    assert result.status == "success"
    assert captured == [
        ToolExecutionContext(
            session_id="sess_1",
            turn_id="turn_1",
            acting_principal_id=identity.claims.principal_id,
            owner_principal_id="principal_owner",
            verified_identity=identity,
        )
    ]
    with SQLiteStore(workspace).connect() as connection:
        stored = connection.execute(
            "SELECT proposed_by FROM tool_actions WHERE action_id = ?",
            (action.action_id,),
        ).fetchone()
    assert stored is not None and stored["proposed_by"] == identity.claims.principal_id


def test_broker_rejects_identity_bound_to_another_turn(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    broker = _broker(workspace)
    identity = TurnMachineIdentityLifecycle(workspace).start(
        owner_principal_id="principal_owner",
        session_id="sess_1",
        turn_id="turn_other",
        role_ids=("assistant",),
    )
    action = ToolAction(
        new_id("act_"), "list_directory", {"path": "."}, "medium", False
    )

    result, decision = broker.execute(
        action,
        session_id="sess_1",
        turn_id="turn_1",
        machine_identity=identity,
    )

    assert result.error == {"type": "machine_identity_turn_mismatch"}
    assert decision.reasons == ["machine_identity_turn_mismatch"]
