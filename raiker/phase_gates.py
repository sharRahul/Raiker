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

RUNTIME_DOMAIN_CAPABILITIES = {
    "shell_execution",
    "process_execution",
    "network_execution",
    "web_fetch",
    "file_write_execution",
    "patch_apply_execution",
    "memory_write_execution",
    "memory_forget_execution",
    "approval_execution_relay",
    "admin_mutation",
    "policy_mutation",
    "role_mutation",
    "model_provider_runtime",
    "hosted_model_runtime",
    "private_network_model_runtime",
    "email_runtime",
    "calendar_runtime",
    "reminder_runtime",
    "finance_runtime",
    "investment_runtime",
    "medical_runtime",
    "pregnancy_baby_runtime",
    "cctv_runtime",
    "home_security_runtime",
    "hardware_operator_runtime",
    "plugin_execution_cap",
    "plugin_install",
    "external_channel_runtime",
    "channel_approval_relay",
    "remote_execution_cap",
    "container_execution_cap",
    "cloud_execution_cap",
    "graph_indexing_runtime",
    "semantic_memory_runtime",
    "vector_embedding_runtime",
    "scheduled_routines",
    "audit_export",
}

ALL_CAPABILITIES = (
    PHASE_3_CAPABILITIES | PHASE_4_DISABLED_CAPABILITIES | RUNTIME_DOMAIN_CAPABILITIES
)


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
        name: CapabilityGate(name, 3, CapabilityState.DISABLED)
        for name in PHASE_3_DISABLED_CAPABILITIES
    }
    for name in READ_ONLY_CONTRACT_CAPABILITIES:
        gates[name] = CapabilityGate(
            name,
            3,
            CapabilityState.CONTRACT_READY,
            routed_through_shared_contracts=True,
            contract_ready=True,
        )
    for name in PHASE_3_POLICY_READY_CAPABILITIES:
        gates[name] = CapabilityGate(
            name,
            3,
            CapabilityState.POLICY_READY,
            policy_ready=True,
            contract_ready=True,
            event_ready=True,
            test_ready=True,
        )
    for name in PHASE_4_DISABLED_CAPABILITIES:
        if name in ("subagents", "multi_agent_teams"):
            # Real bounded/governed in-process executors exist (Phase 4 slice 1):
            # readiness is complete, but the gate still defaults DISABLED and is
            # owner/runtime_gate_manager-flippable only.
            gates[name] = CapabilityGate(
                name, 4, CapabilityState.DISABLED,
                policy_ready=True, contract_ready=True, storage_ready=True,
                event_ready=True, test_ready=True,
            )
        else:
            gates[name] = CapabilityGate(name, 4, CapabilityState.DISABLED)
    _TIER1_EXECUTED_CAPS = ("approval_execution_relay", "file_write_execution", "patch_apply_execution",
                             "memory_write_execution", "memory_forget_execution")
    for name in _TIER1_EXECUTED_CAPS:
        gates[name] = CapabilityGate(
            name, 1, CapabilityState.DISABLED,
            policy_ready=True, contract_ready=True, storage_ready=True,
            event_ready=True, test_ready=True,
        )
    _TIER2_EXECUTED_CAPS = ("shell_execution", "process_execution", "web_fetch", "network_execution")
    for name in _TIER2_EXECUTED_CAPS:
        gates[name] = CapabilityGate(
            name, 2, CapabilityState.DISABLED,
            policy_ready=True, contract_ready=True, storage_ready=True,
            event_ready=True, test_ready=True,
        )
    _EXECUTED_CAPS_ALL: list[str] = list(_TIER1_EXECUTED_CAPS + _TIER2_EXECUTED_CAPS)
    _TIER3_EXECUTED_CAPS = ("graph_indexing_runtime", "semantic_memory_runtime",
                             "vector_embedding_runtime", "model_provider_runtime")
    _TIER4_EXECUTED_CAPS = ("plugin_install", "plugin_execution_cap")
    _TIER5_EXECUTED_CAPS = ("external_channel_runtime", "channel_approval_relay",
                             "remote_execution_cap", "container_execution_cap",
                             "cloud_execution_cap", "hosted_model_runtime",
                             "private_network_model_runtime", "scheduled_routines")
    _TIER6_EXECUTED_CAPS = ("email_runtime", "calendar_runtime", "reminder_runtime",
                             "finance_runtime", "investment_runtime", "medical_runtime",
                             "pregnancy_baby_runtime", "cctv_runtime", "home_security_runtime",
                             "hardware_operator_runtime")
    for tier, caps in [(3, _TIER3_EXECUTED_CAPS), (4, _TIER4_EXECUTED_CAPS),
                       (5, _TIER5_EXECUTED_CAPS), (6, _TIER6_EXECUTED_CAPS)]:
        for name in caps:
            gates[name] = CapabilityGate(
                name, tier, CapabilityState.DISABLED,
                policy_ready=True, contract_ready=True, storage_ready=True,
                event_ready=True, test_ready=True,
            )
        _EXECUTED_CAPS_ALL.extend(caps)
    for name in RUNTIME_DOMAIN_CAPABILITIES:
        if name not in _EXECUTED_CAPS_ALL:
            gates[name] = CapabilityGate(name, 5, CapabilityState.DISABLED)
    return gates


def transition_capability(gate: CapabilityGate, target: CapabilityState) -> CapabilityGate:
    if gate.capability not in ALL_CAPABILITIES:
        raise PermissionError(f"unknown_capability:{gate.capability}")
    if target == CapabilityState.ENABLED_READ_ONLY:
        if (
            gate.capability not in READ_ONLY_CONTRACT_CAPABILITIES
            or not gate.routed_through_shared_contracts
        ):
            raise PermissionError(f"read_only_requires_shared_contract:{gate.capability}")
        return CapabilityGate(**{**gate.__dict__, "state": target})
    if target == CapabilityState.ENABLED_POLICY_GATED:
        if not (gate.policy_ready and gate.contract_ready and gate.event_ready and gate.test_ready):
            raise PermissionError(f"policy_gated_requires_readiness:{gate.capability}")
        return CapabilityGate(**{**gate.__dict__, "state": target})
    if target == CapabilityState.ENABLED_RUNTIME:
        if not (
            gate.policy_ready
            and gate.contract_ready
            and gate.storage_ready
            and gate.event_ready
            and gate.test_ready
            and gate.state == CapabilityState.ENABLED_POLICY_GATED
        ):
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
        "phase_5_runtime_domains": sorted(
            k for k, v in gates.items() if v.phase == 5 and not v.runtime_enabled
        ),
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
