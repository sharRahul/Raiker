from __future__ import annotations

import pytest

from raiker.phase_gates import (
    CapabilityGate,
    CapabilityState,
    get_capability_gate,
    transition_capability,
)


def test_phase_3_runtime_capabilities_disabled_by_default() -> None:
    assert get_capability_gate("plugin_execution").state == CapabilityState.DISABLED
    assert get_capability_gate("semantic_memory_writes").state == CapabilityState.DISABLED
    assert get_capability_gate("graph_codemap_indexing").state == CapabilityState.DISABLED


def test_workspace_clients_can_only_be_read_only_through_shared_contracts() -> None:
    for capability in ("desktop_ui", "web_ui", "dashboard"):
        gate = get_capability_gate(capability)
        assert (
            transition_capability(gate, CapabilityState.ENABLED_READ_ONLY).state
            == CapabilityState.ENABLED_READ_ONLY
        )
        unsafe = CapabilityGate(capability, 3, CapabilityState.CONTRACT_READY)
        with pytest.raises(PermissionError):
            transition_capability(unsafe, CapabilityState.ENABLED_READ_ONLY)


def test_cannot_jump_to_enabled_runtime_without_all_readiness_gates() -> None:
    with pytest.raises(PermissionError):
        transition_capability(
            get_capability_gate("plugin_execution"), CapabilityState.ENABLED_RUNTIME
        )


def test_unknown_capabilities_are_denied_and_phase_4_unaffected() -> None:
    with pytest.raises(PermissionError):
        get_capability_gate("mystery")
    assert get_capability_gate("remote_execution").phase == 4
    assert get_capability_gate("remote_execution").state == CapabilityState.DISABLED
