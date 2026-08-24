from __future__ import annotations

from typing import Any

from raiker.models.factory import ProviderRuntimePolicy

# Synthesised "nobody has decided yet" markers. `get_effective_capability_gate`
# invents these above the store when there is no persisted row; only "persisted"
# reflects an actual owner decision.
_UNDECIDED_GATE_SOURCES = {"principal_fail_closed", "fail_closed", "static_default", "unknown"}

HOSTED_MODEL_GATE = "hosted_model_runtime"
PRIVATE_NETWORK_MODEL_GATE = "private_network_model_runtime"


def _gate_record(store: Any, capability: str, principal_id: str | None = None) -> Any:
    from raiker.runtime.authority.admission import capability_gate_record

    return capability_gate_record(store, principal_id, capability)


def _gate_enabled(store: Any, capability: str, principal_id: str | None = None) -> bool:
    from raiker.runtime.authority.admission import gate_enabled

    return gate_enabled(store, principal_id, capability)


def gate_explicitly_disabled(
    store: Any, capability: str, principal_id: str | None = None
) -> bool:
    """True only when the owner **decided** to turn this capability off.

    Absence of a persisted row is not a decision — it means nobody has said
    anything yet, and the runtime synthesises a fail-closed default above the
    store. Distinguishing the two is what lets configuration imply consent while
    leaving an explicit revocation absolutely authoritative.

    The store returns the persisted row itself, so its presence *is* the owner's
    decision; the ``source`` check additionally handles callers that pass an
    already-resolved effective gate.
    """
    record = _gate_record(store, capability, principal_id)
    if not record:
        return False
    from raiker.runtime.authority.admission import ENABLED_GATE_STATES

    if str(record.get("state", "")) in ENABLED_GATE_STATES:
        return False
    source = record.get("source")
    return source is None or str(source) not in _UNDECIDED_GATE_SOURCES


def owner_configured_providers(store: Any, principal_id: str | None = None) -> frozenset[str]:
    """Profile ids for which the owner has saved a connection.

    Saving a credential for a provider is a deliberate, authenticated act by the
    owner. Under Raiker's stated posture — owner-authoritative and monitored,
    not prevention-by-restriction — that act *is* the authorization to use the
    provider. Requiring a second, separate switch afterwards is a wall in front
    of a choice the owner already made.
    """
    if not principal_id:
        return frozenset()
    try:
        from raiker.models.connections import list_model_connections

        return frozenset(list_model_connections(store, principal_id))
    except Exception:  # noqa: BLE001 — unreadable connections grant nothing
        return frozenset()


def provider_runtime_policy_from_gates(
    store: Any,
    principal_id: str | None = None,
    *,
    configuring_profile_id: str | None = None,
) -> ProviderRuntimePolicy:
    """Derive the model-provider runtime policy for this principal.

    Three inputs, in decreasing authority:

    1. **Explicit owner revocation.** A capability gate the owner deliberately
       set to a disabled state blocks the provider, full stop. Revocation must
       always work, or the controls are theatre.
    2. **Explicit owner enablement.** The gate turned on through the governed
       control plane, as before.
    3. **Owner-configured connection.** A saved credential for a provider is the
       owner's consent to use it. This is what removes the "configure a
       provider, then separately discover you must also flip a switch" trap.

    Every action taken under (3) still passes through the same policy, approval,
    audit, and monitoring paths — consent by configuration changes who has to
    click, not what gets recorded.

    ``configuring_profile_id`` covers the save itself: the connection is
    validated before it is persisted, so on a first save there is nothing on
    disk yet. Without it the very act of configuring a provider would be
    refused for not having configured it.
    """
    hosted_revoked = gate_explicitly_disabled(store, HOSTED_MODEL_GATE, principal_id)
    private_revoked = gate_explicitly_disabled(store, PRIVATE_NETWORK_MODEL_GATE, principal_id)

    configured = owner_configured_providers(store, principal_id)
    consented = bool(configured) or bool(configuring_profile_id)

    hosted = not hosted_revoked and (_gate_enabled(store, HOSTED_MODEL_GATE, principal_id) or consented)
    private = not private_revoked and (
        _gate_enabled(store, PRIVATE_NETWORK_MODEL_GATE, principal_id) or consented
    )
    return ProviderRuntimePolicy(
        allow_policy_gated_provider=hosted or private,
        allow_hosted_provider=hosted,
        allow_private_network_provider=private,
    )
