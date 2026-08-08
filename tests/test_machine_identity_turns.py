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
    UserMetadata,
)
from raiker.gateway.agent_gateway import AgentGateway
from raiker.runtime.identity.lifecycle import (
    TrustedTurnIdentity,
    TurnMachineIdentityLifecycle,
)
from raiker.storage.sqlite import SQLiteStore


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
        prompt: PromptEnvelope, *, identity: TrustedTurnIdentity
    ) -> AgentResponse:
        captured.append(identity)
        return AgentResponse(
            request_id=prompt.request_id,
            session_id=prompt.session_id,
            turn_id=prompt.turn_id,
            status="completed",
            message="done",
        )

    gateway.runtime.ahandle = completed  # type: ignore[method-assign]

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
