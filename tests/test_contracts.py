from __future__ import annotations

import pytest

from raiker.cli.commands import build_prompt_envelope
from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import (
    AgentEvent,
    ClientMetadata,
    ContractValidationError,
    PromptOptions,
)


def test_valid_terminal_prompt_envelope() -> None:
    envelope = build_prompt_envelope("Hello")
    assert envelope.schema_version == "1.0"
    assert envelope.client.version == "0.0.0"
    assert envelope.client.interface_status == "equal_primary_when_enabled"


def test_phase_scheduled_client_types_are_valid() -> None:
    for client_type in ["desktop", "web_ui", "apple_mobile", "android_mobile", "rest", "slack"]:
        client = ClientMetadata(type=client_type, name=f"raiker-{client_type}", version="0.0.0")
        assert client.type == client_type


def test_invalid_client_type_rejected() -> None:
    with pytest.raises(ContractValidationError):
        ClientMetadata(type="terminal_only", name="bad", version="0.0.0")


def test_invalid_planning_mode_rejected() -> None:
    with pytest.raises(ContractValidationError):
        PromptOptions(planning_mode="guess")


@pytest.mark.parametrize("approval_mode", ["manual", "auto", "skip"])
def test_canonical_approval_modes_are_retained(approval_mode: str) -> None:
    assert PromptOptions(approval_mode=approval_mode).approval_mode == approval_mode


@pytest.mark.parametrize(
    ("legacy_mode", "canonical_mode"),
    [("interactive", "manual"), ("allow_safe_only", "auto"), ("deny_risky", "manual")],
)
def test_legacy_approval_modes_are_normalized(legacy_mode: str, canonical_mode: str) -> None:
    assert PromptOptions(approval_mode=legacy_mode).approval_mode == canonical_mode


def test_unknown_approval_mode_rejected() -> None:
    with pytest.raises(ContractValidationError, match="invalid_approval_mode:unbounded"):
        PromptOptions(approval_mode="unbounded")


def test_agent_event_requires_timestamp() -> None:
    with pytest.raises(ContractValidationError):
        AgentEvent(
            event_id=new_id("evt_"),
            timestamp="",
            session_id=new_id("sess_"),
            turn_id=new_id("turn_"),
            event_type="prompt_received",
            actor="test",
            payload={},
        )


def test_ids_and_timestamps() -> None:
    assert new_id("req_").startswith("req_")
    assert new_id("sess_").startswith("sess_")
    assert new_id("turn_").startswith("turn_")
    assert new_id("evt_").startswith("evt_")
    assert utc_now().endswith("Z")
