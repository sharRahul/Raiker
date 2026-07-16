from __future__ import annotations

from typing import Any

from raiker.models.factory import ProviderRuntimePolicy

# Gate states that count as "owner has enabled this capability".
_ENABLED_GATE_STATES = {"enabled_read_only", "enabled_policy_gated", "enabled_runtime"}

HOSTED_MODEL_GATE = "hosted_model_runtime"
PRIVATE_NETWORK_MODEL_GATE = "private_network_model_runtime"


def _gate_enabled(store: Any, capability: str, principal_id: str | None = None) -> bool:
    try:
        scoped = bool(principal_id and store.get_account(principal_id) is not None)
        record = (
            store.get_principal_capability_gate_state(principal_id, capability)
            if scoped else store.get_capability_gate_state(capability)
        )
    except Exception:
        return False
    if not record:
        return False
    return str(record.get("state", "")) in _ENABLED_GATE_STATES


def provider_runtime_policy_from_gates(
    store: Any, principal_id: str | None = None
) -> ProviderRuntimePolicy:
    """Derive the model-provider runtime policy from persisted capability gates.

    Hosted and private-network model access stay OFF unless the owner has
    flipped the corresponding capability gate (`hosted_model_runtime` /
    `private_network_model_runtime`) through the governed control plane —
    which itself requires a HUMAN `runtime_gate_manager`, the registered
    executor, a threat-model ack, and a confirmation token. Missing store,
    missing rows, or read errors all resolve to the fail-closed default.
    """
    hosted = _gate_enabled(store, HOSTED_MODEL_GATE, principal_id)
    private = _gate_enabled(store, PRIVATE_NETWORK_MODEL_GATE, principal_id)
    return ProviderRuntimePolicy(
        allow_policy_gated_provider=hosted or private,
        allow_hosted_provider=hosted,
        allow_private_network_provider=private,
    )
