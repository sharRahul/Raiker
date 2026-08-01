from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from raiker.cli.principal_resolver import (
    check_acting_principal_available,
    check_owner_bootstrapped,
    check_runtime_gate_manager_available,
    resolve_local_principal,
)
from raiker.contracts.ids import new_id, utc_now
from raiker.control.dtos import (
    CapabilityGateView,
    ControlPrincipalRef,
    ControlResult,
    RuntimeModeView,
    RuntimeReadinessView,
)
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.phase_gates import ALL_CAPABILITIES, CapabilityState, default_capability_gates
from raiker.runtime.authority.activation import (
    get_activation_requirement,
    has_executor,
    has_threat_model_ack,
)
from raiker.runtime.authority.models import (
    RAIKER_RUNTIME,
    RUNTIME_STATUS_ACTIVE,
    Principal,
    PrincipalType,
    RiskLevelValue,
)
from raiker.runtime.authority.router import GovernedAction, GovernedActionResult, RuntimeAuthority
from raiker.storage.sqlite import SQLiteStore

_DANGEROUS_CAPS = frozenset({
    "shell_execution", "process_execution", "network_execution",
    "web_fetch", "email_runtime", "calendar_runtime", "finance_runtime",
    "investment_runtime", "medical_runtime", "pregnancy_baby_runtime",
    "cctv_runtime", "home_security_runtime", "plugin_execution_cap",
    "plugin_install", "plugin_revocation_cap", "plugin_runtime_cap",
    "plugin_sandboxed_runtime_cap", "plugin_sandbox_image_pull_cap",
    "external_channel_runtime", "channel_approval_relay",
    "remote_execution_cap", "container_execution_cap", "cloud_execution_cap",
    "approval_execution_relay", "scheduled_routines", "graph_indexing_runtime",
    "semantic_memory_runtime", "vector_embedding_runtime", "model_provider_runtime",
    "hosted_model_runtime", "private_network_model_runtime",
})

# Raiker has one runtime. `allowed_modes` stays on the DTO because clients read
# it, and it now reports the single truth rather than a menu: there is one entry,
# so a client that renders a picker from it renders a fact, not a choice.
_ALLOWED_RUNTIME_MODES = (RAIKER_RUNTIME,)


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

    def _compute_allowed_transitions(
        self, capability: str, principal_id: str | None = None
    ) -> tuple[str, ...]:
        req = get_activation_requirement(capability)
        allowed: list[str] = []
        for cs in CapabilityState:
            sv = cs.value
            if cs == CapabilityState.ENABLED_RUNTIME:
                # One runtime: the only thing that can withhold this transition
                # is the owner having switched the agent runtime off.
                runtime = (
                    self._store.get_principal_runtime_mode(principal_id)
                    if principal_id else self._store.get_latest_runtime_mode()
                )
                if runtime is not None and str(
                    runtime.get("status", RUNTIME_STATUS_ACTIVE)
                ) != RUNTIME_STATUS_ACTIVE:
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
        effective = self._authority.get_effective_capability_gate(
            capability, principal.principal_id if principal else None
        )
        req = get_activation_requirement(capability)
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
            allowed_transitions=self._compute_allowed_transitions(
                capability, principal.principal_id if principal else None
            ),
            can_current_principal_change=can_change,
            blocked_reason_code=blocked_reason,
            readiness=readiness,
            decision_mode=self._authority.get_capability_decision_mode(
                capability, principal.principal_id if principal else None
            ),
            requires_threat_model_ack=(req.requires_threat_model_ack if req else False),
            requires_human_confirmation=(req.requires_human_confirmation_to_enable if req else False),
            threat_model_ack_recorded=has_threat_model_ack(capability, self._store),
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

    def get_persisted_capability_state(
        self, capability: str, acting_principal_id: str | None = None
    ) -> dict[str, Any] | None:
        return self._authority.get_persisted_capability_state(capability, acting_principal_id)

    def get_runtime_mode(self, acting_principal_id: str | None = None) -> RuntimeModeView:
        mode = self._authority.get_runtime_mode(acting_principal_id)
        return RuntimeModeView(
            mode_name=mode.get("mode_name", RAIKER_RUNTIME) or RAIKER_RUNTIME,
            status=mode.get("status", RUNTIME_STATUS_ACTIVE) or RUNTIME_STATUS_ACTIVE,
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
        mode_view = self.get_runtime_mode(acting_principal_id)
        principal = self._resolve_or_none(acting_principal_id)
        gates = default_capability_gates()
        gate_views = tuple(
            self._build_gate_view(cap, gates, principal)
            for cap in sorted(ALL_CAPABILITIES)
        )

        owner_ok = check_owner_bootstrapped(self._workspace_root)
        acting_ok = check_acting_principal_available(self._workspace_root)
        gm_ok = check_runtime_gate_manager_available(self._workspace_root)

        # Integrated capabilities now ship enabled (governed by default-ask); the
        # readiness signal is that no *not-yet-integrated* dangerous capability is
        # enabled — those must stay fail-closed.
        from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES

        dangerous_caps_disabled = True
        for cap in _DANGEROUS_CAPS - REAL_EXECUTOR_CAPABILITIES:
            g = self._authority.get_effective_capability_gate(cap, acting_principal_id)
            if g["state"] not in ("disabled", "planned"):
                dangerous_caps_disabled = False
                break

        production_ready = (
            owner_ok
            # One runtime, so readiness asks whether it is accepting executions
            # rather than which of five names it happens to be running under.
            and mode_view.status == RUNTIME_STATUS_ACTIVE
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

    def record_threat_model_ack(
        self,
        capability: str,
        acting_principal_id: str | None,
        reason: str = "",
    ) -> ControlResult:
        """Record a human threat-model acknowledgement for *capability*.

        This is the governed, in-app equivalent of the operator/CLI ack step. It
        is owner/gate-manager-only and only accepted for capabilities that
        actually require an acknowledgement. It records the acknowledgement and
        an audit event — it does **not** enable the capability; the caller must
        still run the normal capability transition afterwards.
        """
        principal, err = resolve_local_principal(self._workspace_root, acting_principal_id)
        if principal is None:
            return ControlResult(ok=False, reason_code=err or "principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="threat_ack_requires_human")
        denial = self._authority._check_human_runtime_gate_manager(principal)  # noqa: SLF001
        if denial is not None:
            return ControlResult(ok=False, reason_code=denial)
        if capability not in ALL_CAPABILITIES:
            return ControlResult(ok=False, reason_code=f"unknown_capability:{capability}")
        req = get_activation_requirement(capability)
        if req is None or not req.requires_threat_model_ack:
            return ControlResult(ok=False, reason_code=f"threat_ack_not_required:{capability}")
        self._store.record_threat_model_ack(
            capability, principal.principal_id, utc_now(), doc_ref=reason or "web_dashboard_ack"
        )
        self._authority._event(  # noqa: SLF001
            "threat_model_acknowledged",
            principal.principal_id,
            {"capability": capability, "reason": reason},
        )
        return ControlResult(ok=True, data={"capability": capability, "acknowledged": True})

    def set_capability_decision_mode(
        self,
        capability: str,
        mode: str,
        acting_principal_id: str | None,
        reason: str = "",
    ) -> ControlResult:
        principal, err = resolve_local_principal(self._workspace_root, acting_principal_id)
        if principal is None:
            return ControlResult(ok=False, reason_code=err or "principal_not_resolved")
        denial = self._authority.set_capability_decision_mode(capability, mode, principal, reason)
        if denial is not None:
            return ControlResult(ok=False, reason_code=denial)
        return ControlResult(ok=True, data={"capability": capability, "decision_mode": mode})

    def get_capability_decision_mode(
        self, capability: str, acting_principal_id: str | None = None
    ) -> ControlResult:
        mode = self._authority.get_capability_decision_mode(capability, acting_principal_id)
        return ControlResult(ok=True, data={"capability": capability, "decision_mode": mode})

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

    # ── Scoped standing approval grants (Workstream F / F3, ZT-5) ───────────
    # Grants are user-owned, scope-bound, expiry-bound, revocable, and listed in
    # Security Settings. Creation is a critical, human-decided action; the
    # authority enforces the human-only + sub-critical-ceiling invariants.

    def create_standing_grant(
        self,
        acting_principal_id: str | None,
        *,
        action_type: str,
        risk_ceiling: str,
        tool_name: str = "",
        scope_pattern: str = "*",
        reason: str = "",
        ttl_days: float | None = None,
    ) -> ControlResult:
        from raiker.runtime.authority import grants

        principal, err = resolve_local_principal(self._workspace_root, acting_principal_id)
        if principal is None:
            return ControlResult(ok=False, reason_code=err or "principal_not_resolved")
        outcome = self._authority.create_standing_grant(
            granted_by=principal,
            principal_id=principal.principal_id,
            action_type=action_type,
            risk_ceiling=risk_ceiling,
            tool_name=tool_name,
            scope_pattern=scope_pattern,
            reason=reason,
            ttl_days=ttl_days if ttl_days is not None else grants.DEFAULT_GRANT_TTL_DAYS,
        )
        if isinstance(outcome, str):
            return ControlResult(ok=False, reason_code=outcome)
        return ControlResult(ok=True, data={"grant": outcome})

    def list_standing_grants(
        self, acting_principal_id: str | None, *, include_inactive: bool = True
    ) -> ControlResult:
        principal, err = resolve_local_principal(self._workspace_root, acting_principal_id)
        if principal is None:
            return ControlResult(ok=False, reason_code=err or "principal_not_resolved")
        grants_list = self._authority.list_standing_grants(
            granted_by=principal.principal_id, include_inactive=include_inactive
        )
        return ControlResult(ok=True, data={"grants": grants_list})

    def revoke_standing_grant(
        self, grant_id: str, acting_principal_id: str | None
    ) -> ControlResult:
        principal, err = resolve_local_principal(self._workspace_root, acting_principal_id)
        if principal is None:
            return ControlResult(ok=False, reason_code=err or "principal_not_resolved")
        denial = self._authority.revoke_standing_grant(
            grant_id, principal, granted_by=principal.principal_id
        )
        if denial is not None:
            return ControlResult(ok=False, reason_code=denial)
        return ControlResult(ok=True, data={"grant_id": grant_id})

    # ── Governed local MCP server management (Control Deck task 4b) ──────────
    # Create and Test/Connect run the real capability through route_action, so
    # the capability gate, policy, decision mode, and audit trail all apply — no
    # side-door. Rename and Delete are owner-scoped, human-only metadata
    # operations on the caller's own profile (Delete also removes the generated
    # template file). Every method is owner-scoped by the acting principal.

    def _mcp_action_result(self, result: GovernedActionResult) -> ControlResult:
        """Map a governed-action outcome onto a ControlResult, preserving the
        governed reason (a disabled gate, a policy denial, or an executor
        failure) so the caller can surface it verbatim."""
        if result.decision == "disabled_by_capability_gate":
            return ControlResult(ok=False, reason_code="disabled_by_capability_gate")
        if result.decision != "allow":
            return ControlResult(ok=False, reason_code=result.message or result.decision)
        if result.message != "executed":
            return ControlResult(ok=False, reason_code=result.error or result.message or "mcp_not_executed")
        return ControlResult(ok=True)

    def _route_mcp(
        self, principal: Principal, action_type: str, arguments: dict[str, Any]
    ) -> GovernedActionResult:
        action = GovernedAction(
            action_id=new_id("act_"),
            principal_id=principal.principal_id,
            action_type=action_type,
            tool_or_service_name=action_type,
            arguments=arguments,
            risk_level=RiskLevelValue.MEDIUM,
        )
        return self._authority.route_action(action, principal)

    def create_mcp_server(
        self, acting_principal_id: str | None, name: str, template: str
    ) -> ControlResult:
        """Governed build of a local stdio MCP server from a reviewed template."""
        from raiker.runtime.executors.mcp import _normalize_server_name

        principal, err = resolve_local_principal(self._workspace_root, acting_principal_id)
        if principal is None:
            return ControlResult(ok=False, reason_code=err or "principal_not_resolved")
        result = self._route_mcp(
            principal, "mcp_server_create", {"name": name, "template": template}
        )
        mapped = self._mcp_action_result(result)
        if not mapped.ok:
            return mapped
        normalized = _normalize_server_name(name)
        row = (
            self._store.get_mcp_server_by_name(principal.principal_id, normalized)
            if normalized
            else None
        )
        return ControlResult(
            ok=True, data={"server_id": row["server_id"] if row else None, "name": normalized}
        )

    def create_remote_mcp_server(
        self, acting_principal_id: str | None, name: str, endpoint_url: str, auth_ref: str | None
    ) -> ControlResult:
        """Add an owner-scoped **remote** MCP connection (HTTP endpoint + optional
        owner token reference). Owner-added and monitored, not allowlist-blocked;
        the actual reach happens on test-connect (governed). Human-only. The
        token itself is never stored — ``auth_ref`` names the env var that holds
        it."""
        from raiker.runtime.executors.mcp import _normalize_server_name

        principal, err = resolve_local_principal(self._workspace_root, acting_principal_id)
        if principal is None:
            return ControlResult(ok=False, reason_code=err or "principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        normalized = _normalize_server_name(name)
        if normalized is None:
            return ControlResult(ok=False, reason_code="mcp_invalid_server_name")
        parsed = urlparse(endpoint_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return ControlResult(ok=False, reason_code="mcp_remote_invalid_endpoint")
        if self._store.get_mcp_server_by_name(principal.principal_id, normalized) is not None:
            return ControlResult(ok=False, reason_code="mcp_name_taken")
        server_id = new_id("mcp_")
        self._store.create_mcp_server(
            server_id=server_id,
            principal_id=principal.principal_id,
            name=normalized,
            command=[],
            template=None,
            transport="http",
            status="created",
            endpoint_url=endpoint_url,
            auth_ref=auth_ref or None,
        )
        self._writer.append(
            make_event(
                session_id="mcp",
                turn_id=None,
                event_type="mcp_connection_added",
                actor="control_service",
                # Redacted metadata only — host, never the full URL query or token.
                payload={
                    "server_id": server_id,
                    "name": normalized,
                    "transport": "http",
                    "host": parsed.netloc,
                },
            )
        )
        return ControlResult(
            ok=True, data={"server_id": server_id, "name": normalized, "transport": "http"}
        )

    def connect_mcp_server(
        self, acting_principal_id: str | None, server_id: str
    ) -> ControlResult:
        """Governed test-connect of a stored server: run the handshake (stdio or
        remote HTTP) and persist the discovered tool names + status. Owner-scoped."""
        principal, err = resolve_local_principal(self._workspace_root, acting_principal_id)
        if principal is None:
            return ControlResult(ok=False, reason_code=err or "principal_not_resolved")
        server = self._store.get_mcp_server(server_id, principal.principal_id)
        if server is None:
            return ControlResult(ok=False, reason_code=f"unknown_mcp_server:{server_id}")
        if str(server.get("transport")) == "http":
            connect_args: dict[str, Any] = {
                "transport": "http",
                "endpoint_url": server.get("endpoint_url") or "",
                "auth_ref": server.get("auth_ref") or "",
                "name": server["name"],
                "server_id": server_id,
            }
        else:
            connect_args = {
                "command": server["command"],
                "name": server["name"],
                "server_id": server_id,
            }
        result = self._route_mcp(principal, "mcp_connect", connect_args)
        mapped = self._mcp_action_result(result)
        if not mapped.ok:
            return mapped
        updated = self._store.get_mcp_server(server_id, principal.principal_id) or {}
        return ControlResult(
            ok=True,
            data={
                "server_id": server_id,
                "status": updated.get("status", "connected"),
                "tools": list(updated.get("tools", [])),
            },
        )

    def rename_mcp_server(
        self, acting_principal_id: str | None, server_id: str, name: str
    ) -> ControlResult:
        """Owner-scoped, human-only rename of one server profile."""
        from raiker.runtime.executors.mcp import _normalize_server_name

        principal, err = resolve_local_principal(self._workspace_root, acting_principal_id)
        if principal is None:
            return ControlResult(ok=False, reason_code=err or "principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        normalized = _normalize_server_name(name)
        if normalized is None:
            return ControlResult(ok=False, reason_code="mcp_invalid_server_name")
        if self._store.get_mcp_server(server_id, principal.principal_id) is None:
            return ControlResult(ok=False, reason_code=f"unknown_mcp_server:{server_id}")
        if not self._store.rename_mcp_server(server_id, principal.principal_id, normalized):
            return ControlResult(ok=False, reason_code="mcp_name_taken")
        return ControlResult(ok=True, data={"server_id": server_id, "name": normalized})

    def delete_mcp_server(
        self, acting_principal_id: str | None, server_id: str
    ) -> ControlResult:
        """Owner-scoped, human-only delete of one server profile. Also removes
        the generated template file when it lives inside the workspace MCP
        directory (best-effort — a leftover file never blocks the delete)."""
        principal, err = resolve_local_principal(self._workspace_root, acting_principal_id)
        if principal is None:
            return ControlResult(ok=False, reason_code=err or "principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        server = self._store.get_mcp_server(server_id, principal.principal_id)
        if server is None:
            return ControlResult(ok=False, reason_code=f"unknown_mcp_server:{server_id}")
        if not self._store.delete_mcp_server(server_id, principal.principal_id):
            return ControlResult(ok=False, reason_code=f"unknown_mcp_server:{server_id}")
        self._remove_generated_mcp_file(server)
        return ControlResult(ok=True, data={"server_id": server_id})

    # ── Containment: instant kill switch + revocable pause (Phase C) ─────────
    # Owner-scoped, human-only lifecycle control over a monitored connection.
    # Pause is the one-call stop; kill is the instant kill switch; resume revokes
    # either. Each transition writes the new state, emits its audit event, and
    # raises an owner-facing notification via the shared McpContainment helper.

    def _containment_transition(
        self, acting_principal_id: str | None, server_id: str, verb: str, reason: str | None
    ) -> ControlResult:
        from raiker.security.mcp_monitor import McpContainment

        principal, err = resolve_local_principal(self._workspace_root, acting_principal_id)
        if principal is None:
            return ControlResult(ok=False, reason_code=err or "principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        server = self._store.get_mcp_server(server_id, principal.principal_id)
        if server is None:
            return ControlResult(ok=False, reason_code=f"unknown_mcp_server:{server_id}")
        containment = McpContainment(self._store, writer=self._writer)
        if verb == "pause":
            ok = containment.pause(
                principal.principal_id, server_id,
                reason=reason or "Paused by owner.", source="owner",
            )
            new_state = "paused"
        elif verb == "kill":
            ok = containment.kill(
                principal.principal_id, server_id,
                reason=reason or "Killed by owner.", source="owner",
            )
            new_state = "killed"
        else:  # resume
            ok = containment.resume(principal.principal_id, server_id, source="owner")
            new_state = "active"
        if not ok:
            return ControlResult(ok=False, reason_code=f"unknown_mcp_server:{server_id}")
        return ControlResult(
            ok=True, data={"server_id": server_id, "monitor_state": new_state}
        )

    def pause_mcp_server(
        self, acting_principal_id: str | None, server_id: str, reason: str | None = None
    ) -> ControlResult:
        """Owner-scoped, human-only one-call stop of a connection (revocable)."""
        return self._containment_transition(acting_principal_id, server_id, "pause", reason)

    def kill_mcp_server(
        self, acting_principal_id: str | None, server_id: str, reason: str | None = None
    ) -> ControlResult:
        """Owner-scoped, human-only instant kill switch (revocable via resume)."""
        return self._containment_transition(acting_principal_id, server_id, "kill", reason)

    def resume_mcp_server(
        self, acting_principal_id: str | None, server_id: str
    ) -> ControlResult:
        """Owner-scoped, human-only resume — revoke a pause/kill back to active."""
        return self._containment_transition(acting_principal_id, server_id, "resume", None)

    def _remove_generated_mcp_file(self, server: dict[str, Any]) -> None:
        from raiker.runtime.executors.mcp import _MCP_SERVERS_DIR, _safe_workspace_relative

        command = server.get("command") or []
        if len(command) < 2:
            return
        ws = Path(self._workspace_root).resolve()
        resolved = _safe_workspace_relative(ws, str(command[1]))
        if resolved is None:
            return
        try:
            rel = resolved.relative_to(ws).as_posix()
        except ValueError:
            return
        # Only ever unlink a file we generated under the managed servers dir.
        if not rel.startswith(f"{_MCP_SERVERS_DIR}/"):
            return
        try:
            resolved.unlink(missing_ok=True)
        except OSError:
            return
