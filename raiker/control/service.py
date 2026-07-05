from __future__ import annotations

from pathlib import Path
from typing import Any

from raiker.cli.principal_resolver import (
    check_acting_principal_available,
    check_owner_bootstrapped,
    check_runtime_gate_manager_available,
    resolve_local_principal,
)
from raiker.control.dtos import (
    CapabilityGateView,
    ControlPrincipalRef,
    ControlResult,
    RuntimeModeView,
    RuntimeReadinessView,
)
from raiker.events.writer import EventLogWriter
from raiker.phase_gates import ALL_CAPABILITIES, CapabilityState, default_capability_gates
from raiker.runtime.authority.activation import get_activation_requirement, has_executor
from raiker.runtime.authority.models import Principal, PrincipalType
from raiker.runtime.authority.router import RuntimeAuthority
from raiker.storage.sqlite import SQLiteStore

_RUNTIME_ENABLEMENT_MODES = frozenset({
    "local_single_user_runtime",
    "multi_user_local_runtime",
})

_DANGEROUS_CAPS = frozenset({
    "shell_execution", "process_execution", "network_execution",
    "web_fetch", "email_runtime", "calendar_runtime", "finance_runtime",
    "investment_runtime", "medical_runtime", "pregnancy_baby_runtime",
    "cctv_runtime", "home_security_runtime", "plugin_execution_cap",
    "plugin_install", "plugin_revocation_cap", "plugin_runtime_cap",
    "external_channel_runtime", "channel_approval_relay",
    "remote_execution_cap", "container_execution_cap", "cloud_execution_cap",
    "approval_execution_relay", "scheduled_routines", "graph_indexing_runtime",
    "semantic_memory_runtime", "vector_embedding_runtime",
    "hosted_model_runtime", "private_network_model_runtime",
})

_ALLOWED_RUNTIME_MODES = (
    "development_preview",
    "local_single_user_safe",
    "local_single_user_runtime",
    "multi_user_local_runtime",
    "hosted_or_networked_runtime",
)


class RuntimeControlService:
    """Interface-agnostic control-plane facade.

    Constructs its own store / writer / authority internally (mirroring the
    CLI handlers).  Every read method returns a typed DTO.  No governance
    logic — delegates every decision to RuntimeAuthority.
    """

    def __init__(
        self, workspace_root: str | Path = ".",
        executor_registry: Any | None = None,
    ) -> None:
        self._workspace_root = Path(workspace_root)
        self._store = SQLiteStore(self._workspace_root)
        self._writer = EventLogWriter(self._store)
        if executor_registry is None:
            from raiker.runtime.executors import build_default_executor_registry
            executor_registry = build_default_executor_registry(self._workspace_root, self._store)
        self._registry = executor_registry
        self._authority = RuntimeAuthority(
            self._store, self._writer,
            executor_registry=executor_registry,
        )

    # -- internals ----------------------------------------------------------

    def _resolve_or_none(self, principal_id: str | None) -> Principal | None:
        if principal_id is None:
            return None
        raw = self._store.get_principal(principal_id)
        if raw is None:
            return None
        if isinstance(raw.get("principal_type"), str):
            raw["principal_type"] = PrincipalType(raw["principal_type"])
        return Principal(**raw)

    def _is_gate_manager(self, principal: Principal) -> bool:
        return self._authority._check_human_runtime_gate_manager(principal) is None  # noqa: SLF001

    def _compute_allowed_transitions(self, capability: str) -> tuple[str, ...]:
        req = get_activation_requirement(capability)
        allowed: list[str] = []
        for cs in CapabilityState:
            sv = cs.value
            if cs == CapabilityState.ENABLED_RUNTIME:
                active_mode = self._store.get_active_runtime_mode()
                mode_name = (active_mode or {}).get("mode_name", "development_preview")
                if mode_name not in _RUNTIME_ENABLEMENT_MODES:
                    continue
            if cs in (CapabilityState.ENABLED_RUNTIME, CapabilityState.ENABLED_POLICY_GATED) and req is not None and req.requires_executor and not has_executor(capability, self._registry):
                    continue
            allowed.append(sv)
        return tuple(allowed)

    def _build_gate_view(
        self,
        capability: str,
        gates: dict[str, Any],
        principal: Principal | None,
    ) -> CapabilityGateView:
        effective = self._authority.get_effective_capability_gate(capability)
        state: str = effective["state"]
        default_gate = gates.get(capability)
        default_state: str = default_gate.state.value if default_gate else "disabled"
        phase: int = default_gate.phase if default_gate else 0

        readiness: dict[str, Any] = {}
        if default_gate is not None:
            readiness = {
                "policy_ready": default_gate.policy_ready,
                "contract_ready": default_gate.contract_ready,
                "storage_ready": default_gate.storage_ready,
                "event_ready": default_gate.event_ready,
                "test_ready": default_gate.test_ready,
            }

        can_change = False
        blocked_reason: str | None = None
        if principal is not None:
            denial = self._authority._check_human_runtime_gate_manager(principal)  # noqa: SLF001
            if denial is not None:
                blocked_reason = denial
            else:
                can_change = True

        return CapabilityGateView(
            capability=capability,
            phase=phase,
            state=state,
            default_state=default_state,
            source=effective.get("source", "unknown"),
            runtime_enabled=(state == CapabilityState.ENABLED_RUNTIME),
            allowed_transitions=self._compute_allowed_transitions(capability),
            can_current_principal_change=can_change,
            blocked_reason_code=blocked_reason,
            readiness=readiness,
        )

    # -- read methods -------------------------------------------------------

    def resolve_principal(
        self,
        explicit_principal_id: str | None = None,
    ) -> tuple[ControlPrincipalRef | None, str | None]:
        principal, err = resolve_local_principal(
            self._workspace_root, explicit_principal_id,
        )
        if principal is None:
            return None, err
        return ControlPrincipalRef(
            principal_id=principal.principal_id,
            display_name=principal.display_name,
            principal_type=principal.principal_type.value,
            role_ids=principal.role_ids,
            is_authorized_gate_manager=self._is_gate_manager(principal),
        ), None

    def get_persisted_capability_state(self, capability: str) -> dict[str, Any] | None:
        return self._store.get_capability_gate_state(capability)

    def get_runtime_mode(self) -> RuntimeModeView:
        mode = self._authority.get_runtime_mode()
        return RuntimeModeView(
            mode_name=mode.get("mode_name", "development_preview"),
            status=mode.get("status", "inactive"),
            activated_by=mode.get("activated_by", "") or "",
            activated_at=mode.get("activated_at", "") or "",
            reason=mode.get("reason", "") or "",
            allowed_modes=_ALLOWED_RUNTIME_MODES,
        )

    def list_capability_gates(
        self,
        acting_principal_id: str | None = None,
    ) -> list[CapabilityGateView]:
        principal = self._resolve_or_none(acting_principal_id)
        gates = default_capability_gates()
        return [
            self._build_gate_view(cap, gates, principal)
            for cap in sorted(ALL_CAPABILITIES)
        ]

    def get_capability_gate(
        self,
        capability: str,
        acting_principal_id: str | None = None,
    ) -> CapabilityGateView | None:
        if capability not in ALL_CAPABILITIES:
            return None
        principal = self._resolve_or_none(acting_principal_id)
        gates = default_capability_gates()
        return self._build_gate_view(capability, gates, principal)

    def get_runtime_readiness(
        self,
        acting_principal_id: str | None = None,
    ) -> RuntimeReadinessView:
        mode_view = self.get_runtime_mode()
        principal = self._resolve_or_none(acting_principal_id)
        gates = default_capability_gates()
        gate_views = tuple(
            self._build_gate_view(cap, gates, principal)
            for cap in sorted(ALL_CAPABILITIES)
        )

        owner_ok = check_owner_bootstrapped(self._workspace_root)
        acting_ok = check_acting_principal_available(self._workspace_root)
        gm_ok = check_runtime_gate_manager_available(self._workspace_root)

        dangerous_caps_disabled = True
        for cap in _DANGEROUS_CAPS:
            g = self._authority.get_effective_capability_gate(cap)
            if g["state"] not in ("disabled", "planned"):
                dangerous_caps_disabled = False
                break

        production_ready = (
            owner_ok
            and mode_view.mode_name in ("local_single_user_runtime", "local_single_user_safe")
            and mode_view.status == "active"
            and gm_ok
            and acting_ok
            and dangerous_caps_disabled
        )

        summary: dict[str, Any] = {
            "owner_bootstrapped": owner_ok,
            "acting_principal_available": acting_ok,
            "runtime_gate_manager_available": gm_ok,
            "dangerous_capabilities_disabled": dangerous_caps_disabled,
            "production_ready_local_single_user_runtime": production_ready,
        }
        return RuntimeReadinessView(
            mode=mode_view,
            gates=gate_views,
            summary=summary,
        )

    # -- mutate methods ------------------------------------------------------

    def activate_runtime_mode(
        self,
        mode_name: str,
        acting_principal_id: str | None,
        reason: str = "",
    ) -> ControlResult:
        principal, err = resolve_local_principal(self._workspace_root, acting_principal_id)
        if principal is None:
            return ControlResult(ok=False, reason_code=err or "principal_not_resolved")
        denial = self._authority.activate_runtime_mode(mode_name, principal, reason)
        if denial is not None:
            return ControlResult(ok=False, reason_code=denial)
        return ControlResult(ok=True, data={"mode_name": mode_name})

    def disable_runtime_mode(
        self,
        acting_principal_id: str | None,
        reason: str = "",
    ) -> ControlResult:
        principal, err = resolve_local_principal(self._workspace_root, acting_principal_id)
        if principal is None:
            return ControlResult(ok=False, reason_code=err or "principal_not_resolved")
        denial = self._authority.disable_runtime_mode(principal, reason)
        if denial is not None:
            return ControlResult(ok=False, reason_code=denial)
        return ControlResult(ok=True)

    def set_capability_state(
        self,
        capability: str,
        target_state: str,
        acting_principal_id: str | None,
        reason: str = "",
        confirmation_token: str | None = None,
    ) -> ControlResult:
        principal, err = resolve_local_principal(self._workspace_root, acting_principal_id)
        if principal is None:
            return ControlResult(ok=False, reason_code=err or "principal_not_resolved")
        denial = self._authority.request_capability_transition(
            capability, target_state, principal, reason, confirmation_token=confirmation_token,
        )
        if denial is not None:
            return ControlResult(ok=False, reason_code=denial)
        return ControlResult(ok=True, data={"capability": capability, "target_state": target_state})

    def disable_capability(
        self,
        capability: str,
        acting_principal_id: str | None,
        reason: str = "",
    ) -> ControlResult:
        principal, err = resolve_local_principal(self._workspace_root, acting_principal_id)
        if principal is None:
            return ControlResult(ok=False, reason_code=err or "principal_not_resolved")
        denial = self._authority.request_capability_transition(capability, "disabled", principal, reason)
        if denial is not None:
            return ControlResult(ok=False, reason_code=denial)
        return ControlResult(ok=True, data={"capability": capability})
