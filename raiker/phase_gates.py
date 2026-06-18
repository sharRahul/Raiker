from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CapabilityState(StrEnum):
    DISABLED = "disabled"
    PLANNED = "planned"
    POLICY_READY = "policy_ready"
    CONTRACT_READY = "contract_ready"
    STORAGE_READY = "storage_ready"
    EVENT_READY = "event_ready"
    TEST_READY = "test_ready"
    ENABLED_READ_ONLY = "enabled_read_only"
    ENABLED_POLICY_GATED = "enabled_policy_gated"
    ENABLED_RUNTIME = "enabled_runtime"


PHASE_3_CAPABILITIES = {
    "desktop_ui",
    "web_ui",
    "dashboard",
    "plugin_execution",
    "graph_codemap_indexing",
    "semantic_memory_writes",
    "graph_codemap_planning",
    "semantic_memory_review_queue",
}
PHASE_4_DISABLED_CAPABILITIES = {
    "external_channels",
    "subagents",
    "multi_agent_teams",
    "remote_execution",
    "container_execution",
}
PHASE_3_DISABLED_CAPABILITIES = {
    "plugin_execution",
    "graph_codemap_indexing",
    "semantic_memory_writes",
    "graph_codemap_planning",
    "semantic_memory_review_queue",
}

READ_ONLY_CONTRACT_CAPABILITIES = {"desktop_ui", "web_ui", "dashboard"}
PHASE_3_POLICY_READY_CAPABILITIES = {"graph_codemap_planning", "semantic_memory_review_queue"}


@dataclass(frozen=True)
class CapabilityGate:
    capability: str
    phase: int
    state: CapabilityState
    routed_through_shared_contracts: bool = False
    policy_ready: bool = False
    contract_ready: bool = False
    storage_ready: bool = False
    event_ready: bool = False
    test_ready: bool = False

    @property
    def runtime_enabled(self) -> bool:
        return self.state == CapabilityState.ENABLED_RUNTIME

    @property
    def disabled(self) -> bool:
        return self.state in {CapabilityState.DISABLED, CapabilityState.PLANNED}


def default_capability_gates() -> dict[str, CapabilityGate]:
    gates: dict[str, CapabilityGate] = {
        name: CapabilityGate(name, 3, CapabilityState.DISABLED) for name in PHASE_3_DISABLED_CAPABILITIES
    }
    for name in READ_ONLY_CONTRACT_CAPABILITIES:
        gates[name] = CapabilityGate(name, 3, CapabilityState.CONTRACT_READY, routed_through_shared_contracts=True, contract_ready=True)
    for name in PHASE_3_POLICY_READY_CAPABILITIES:
        gates[name] = CapabilityGate(name, 3, CapabilityState.POLICY_READY, policy_ready=True, contract_ready=True, event_ready=True, test_ready=True)
    for name in PHASE_4_DISABLED_CAPABILITIES:
        gates[name] = CapabilityGate(name, 4, CapabilityState.DISABLED)
    return gates


def transition_capability(gate: CapabilityGate, target: CapabilityState) -> CapabilityGate:
    if gate.capability not in PHASE_3_CAPABILITIES | PHASE_4_DISABLED_CAPABILITIES:
        raise PermissionError(f"unknown_capability:{gate.capability}")
    if target == CapabilityState.ENABLED_READ_ONLY:
        if gate.capability not in READ_ONLY_CONTRACT_CAPABILITIES or not gate.routed_through_shared_contracts:
            raise PermissionError(f"read_only_requires_shared_contract:{gate.capability}")
        return CapabilityGate(**{**gate.__dict__, "state": target})
    if target == CapabilityState.ENABLED_POLICY_GATED:
        if not (gate.policy_ready and gate.contract_ready and gate.event_ready and gate.test_ready):
            raise PermissionError(f"policy_gated_requires_readiness:{gate.capability}")
        return CapabilityGate(**{**gate.__dict__, "state": target})
    if target == CapabilityState.ENABLED_RUNTIME:
        if not (gate.policy_ready and gate.contract_ready and gate.storage_ready and gate.event_ready and gate.test_ready and gate.state == CapabilityState.ENABLED_POLICY_GATED):
            raise PermissionError(f"runtime_requires_all_readiness_gates:{gate.capability}")
        return CapabilityGate(**{**gate.__dict__, "state": target})
    return CapabilityGate(**{**gate.__dict__, "state": target})


def get_capability_gate(capability: str) -> CapabilityGate:
    gates = default_capability_gates()
    if capability not in gates:
        raise PermissionError(f"unknown_capability:{capability}")
    return gates[capability]


def list_disabled_capabilities() -> dict[str, list[str]]:
    gates = default_capability_gates()
    return {
        "phase_3": sorted(k for k, v in gates.items() if v.phase == 3 and not v.runtime_enabled),
        "phase_4": sorted(k for k, v in gates.items() if v.phase == 4 and not v.runtime_enabled),
    }


def list_capability_states() -> dict[str, dict[str, str | bool | int]]:
    return {
        name: {
            "phase": gate.phase,
            "state": gate.state.value,
            "runtime_enabled": gate.runtime_enabled,
            "routed_through_shared_contracts": gate.routed_through_shared_contracts,
        }
        for name, gate in sorted(default_capability_gates().items())
    }


def assert_capability_disabled(capability: str) -> None:
    gate = get_capability_gate(capability)
    if not gate.runtime_enabled:
        raise PermissionError(f"phase_gated_disabled:{capability}")
