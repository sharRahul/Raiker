from __future__ import annotations

from pathlib import Path

import pytest

from raiker.cli.commands import build_prompt_envelope
from raiker.contracts.models import AgentResponse
from raiker.gateway.agent_gateway import AgentGateway


@pytest.mark.parametrize("status", ["failed", "stopped", "needs_approval"])
def test_non_completed_turns_never_create_memory_proposals(
    tmp_path: Path, status: str
) -> None:
    gateway = AgentGateway(tmp_path)
    envelope = build_prompt_envelope("Rahul uses Python.")
    gateway._prepare_turn(envelope)  # noqa: SLF001 - exact production boundary regression

    gateway._finalize_turn(  # noqa: SLF001
        envelope,
        AgentResponse(
            request_id=envelope.request_id,
            session_id=envelope.session_id,
            turn_id=envelope.turn_id,
            status=status,
            message="Raiker is part of the project.",
            client=envelope.client,
        ),
    )

    assert gateway.store.list_memory_candidates(
        decision="deferred", owner_principal_id=gateway.owner_principal_id
    ) == []


def test_completed_turn_creates_role_provenanced_idempotent_proposals(tmp_path: Path) -> None:
    gateway = AgentGateway(tmp_path)
    envelope = build_prompt_envelope("Rahul uses Python.")
    gateway._prepare_turn(envelope)  # noqa: SLF001
    response = AgentResponse(
        request_id=envelope.request_id,
        session_id=envelope.session_id,
        turn_id=envelope.turn_id,
        status="completed",
        message="Raiker is part of the project.",
        client=envelope.client,
    )

    gateway._finalize_turn(envelope, response)  # noqa: SLF001
    gateway._finalize_turn(envelope, response)  # noqa: SLF001 - replay must be idempotent

    rows = gateway.store.list_memory_candidates(
        decision="deferred", owner_principal_id=gateway.owner_principal_id
    )
    assert len(rows) == 2
    assert {row["source_role"] for row in rows} == {"user", "assistant"}
    assert {row["source_turn_id"] for row in rows} == {envelope.turn_id}
    assert all(row["extractor_version"] for row in rows)
    assert gateway.store.list_memory_candidates(
        decision="deferred", owner_principal_id="principal_other"
    ) == []


def test_secret_like_completed_text_creates_no_proposal(tmp_path: Path) -> None:
    gateway = AgentGateway(tmp_path)
    envelope = build_prompt_envelope(
        "Rahul uses sk-proj-abcdefghijklmnopqrstuvwxyz."
    )
    gateway._prepare_turn(envelope)  # noqa: SLF001

    gateway._finalize_turn(  # noqa: SLF001
        envelope,
        AgentResponse(
            request_id=envelope.request_id,
            session_id=envelope.session_id,
            turn_id=envelope.turn_id,
            status="completed",
            message="No durable relationship.",
            client=envelope.client,
        ),
    )

    assert gateway.store.list_memory_candidates(
        decision="deferred", owner_principal_id=gateway.owner_principal_id
    ) == []
