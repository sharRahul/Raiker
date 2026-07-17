from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import PolicyDecision
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.runtime.authority.activation import evaluate_activation_requirement
from raiker.runtime.authority.decision_modes import (
    DEFAULT_DECISION_MODE,
    PERMISSIVE_MODES,
    DecisionMode,
    auto_requires_approval,
    parse_decision_mode,
)
from raiker.runtime.authority.models import (
    AI_ROLE_NAMES,
    HUMAN_ONLY_ROLES,
    Principal,
    PrincipalType,
    RiskAcceptance,
    RiskLevelValue,
)
from raiker.runtime.executors.registry import ExecutorRegistry
from raiker.storage.sqlite import SQLiteStore

NON_ALLOW_DECISIONS = frozenset({
    "deny",
    "needs_approval",
    "needs_risk_acceptance",
    "needs_human_confirmation",
    "disabled_by_capability_gate",
})

# Maps action_type / tool_or_service_name to capability gate names
CAPABILITY_GATE_MAP: dict[str, str] = {
    "admin_mutation": "admin_mutation",
    "role_mutation": "role_mutation",
    "policy_mutation": "policy_mutation",
    "user_create": "admin_mutation",
    "user_deactivate": "admin_mutation",
    "role_create": "role_mutation",
    "role_grant": "role_mutation",
    "role_revoke": "role_mutation",
    "write_file": "file_write_execution",
    "edit_file": "file_write_execution",
    "apply_patch": "patch_apply_execution",
    "memory_write": "memory_write_execution",
    "memory_forget": "memory_forget_execution",
    "shell": "shell_execution",
    "process": "process_execution",
    "network": "network_execution",
    "web_fetch": "web_fetch",
    "graph_indexing": "graph_indexing_runtime",
    "semantic_memory": "semantic_memory_runtime",
    "vector_embedding": "vector_embedding_runtime",
    "model_provider": "model_provider_runtime",
    "plugin_install": "plugin_install",
    "plugin_execution_cap": "plugin_execution_cap",
    "plugin_revocation_cap": "plugin_revocation_cap",
    "plugin_runtime_cap": "plugin_runtime_cap",
    "plugin_sandboxed_runtime_cap": "plugin_sandboxed_runtime_cap",
    "plugin_sandbox_image_pull_cap": "plugin_sandbox_image_pull_cap",
    "external_channel_runtime": "external_channel_runtime",
    "channel_approval_relay": "channel_approval_relay",
    "remote_execution_cap": "remote_execution_cap",
    "container_execution_cap": "container_execution_cap",
    "cloud_execution_cap": "cloud_execution_cap",
    "hosted_model_runtime": "hosted_model_runtime",
    "private_network_model_runtime": "private_network_model_runtime",
    "advisor_model_runtime": "advisor_model_runtime",
    "connector_github_runtime": "connector_github_runtime",
    "connector_gmail_runtime": "connector_gmail_runtime",
    "connector_gcal_runtime": "connector_gcal_runtime",
    "connector_slack_runtime": "connector_slack_runtime",
    "scheduled_routines": "scheduled_routines",
    # Governed local stdio MCP builder + connector (Control Deck task 4).
    "mcp_server_create": "mcp_builder_runtime",
    "mcp_builder_runtime": "mcp_builder_runtime",
    "mcp_connect": "mcp_connector_runtime",
    "mcp_list_tools": "mcp_connector_runtime",
    "mcp_call_tool": "mcp_connector_runtime",
    "mcp_connector_runtime": "mcp_connector_runtime",
    "subagents": "subagents",
    "multi_agent_teams": "multi_agent_teams",
    "email_runtime": "email_runtime",
    "calendar_runtime": "calendar_runtime",
    "reminder_runtime": "reminder_runtime",
    "finance_runtime": "finance_runtime",
    "investment_runtime": "investment_runtime",
    "medical_runtime": "medical_runtime",
    "pregnancy_baby_runtime": "pregnancy_baby_runtime",
    "cctv_runtime": "cctv_runtime",
    "home_security_runtime": "home_security_runtime",
    "hardware_operator_runtime": "hardware_operator_runtime",
}


@dataclass(frozen=True)
class GovernedAction:
    action_id: str
    principal_id: str
    action_type: str
    tool_or_service_name: str
    arguments: dict[str, Any]
    domain_scope: str = ""
    risk_level: str = RiskLevelValue.LOW
    expected_effect: str = ""
    requires_approval: bool = False
    requires_risk_acceptance: bool = False
    session_id: str = ""
    turn_id: str | None = None


@dataclass(frozen=True)
class GovernedActionResult:
    action_id: str
    decision: str
    policy_decision: PolicyDecision | None = None
    risk_acceptance: RiskAcceptance | None = None
    approved: bool = False
    message: str = ""
    error: str | None = None


class RuntimeAuthority:
    def __init__(
        self,
        store: SQLiteStore,
        writer: EventLogWriter,
        policy_engine: PolicyEngine | None = None,
        executor_registry: ExecutorRegistry | None = None,
    ) -> None:
        self.store = store
        self.writer = writer
        self.policy_engine = policy_engine or PolicyEngine(
            StaticPolicyConfig(store.paths.workspace_root),
            store=store,
        )
        self.executor_registry = executor_registry or ExecutorRegistry()

    def _uses_principal_controls(self, principal_id: str | None) -> bool:
        return bool(principal_id and self.store.get_account(principal_id) is not None)

    def _event(
        self,
        event_type: str,
        actor: str,
        payload: dict[str, object],
        session_id: str = "",
        turn_id: str | None = None,
    ) -> None:
        self.writer.append(
            make_event(
                session_id=session_id or "authz",
                turn_id=turn_id,
                event_type=event_type,
                actor=actor,
                payload=payload,
            )
        )

    def get_principal(self, principal_id: str) -> Principal | None:
        raw = self.store.get_principal(principal_id)
        if raw is None:
            return None
        return Principal(**raw)

    def is_human_role(self, role_name: str) -> bool:
        return role_name in HUMAN_ONLY_ROLES

    def is_ai_role(self, role_name: str) -> bool:
        return role_name in AI_ROLE_NAMES

    def check_ai_role_assignment(self, principal: Principal) -> str | None:
        for role_id in principal.role_ids:
            role_name = self.store.get_role_name(role_id)
            if role_name and role_name in HUMAN_ONLY_ROLES:
                return f"cannot_assign_human_role_to_ai:{role_name}"
        return None

    def check_principal_active(self, principal: Principal) -> str | None:
        if not principal.is_active:
            return "principal_not_active"
        if principal.expires_at and utc_now() > principal.expires_at:
            return "principal_expired"
        return None

    def check_domain_scope(
        self, principal: Principal, required_scope: str
    ) -> str | None:
        if required_scope and required_scope not in principal.domain_scopes:
            return f"domain_scope_denied:{required_scope}"
        return None

    def check_self_approval(
        self, principal: Principal, action: GovernedAction
    ) -> str | None:
        if action.principal_id == principal.principal_id and action.requires_approval and principal.principal_type != PrincipalType.HUMAN:
            return "ai_cannot_approve_own_action"
        return None

    def check_self_grant(self, principal: Principal, action_type: str) -> str | None:
        if action_type in ("role_grant", "role_assign") and principal.principal_type != PrincipalType.HUMAN:
            return "ai_cannot_grant_roles"
        return None

    def _check_human_runtime_gate_manager(self, principal: Principal) -> str | None:
        if principal.principal_type != PrincipalType.HUMAN:
            return "ai_cannot_manage_runtime_gates"
        is_gate_manager = any(
            self.store.get_role_name(rid) == "runtime_gate_manager"
            for rid in principal.role_ids
        )
        if not is_gate_manager:
            return "only_runtime_gate_manager_can_manage_gates"
        return None

    def check_runtime_gate_enable(self, principal: Principal, action_type: str) -> str | None:
        if action_type == "enable_runtime_gate":
            if principal.principal_type != PrincipalType.HUMAN:
                return "ai_cannot_enable_runtime_gate"
            is_runtime_manager = any(
                self.store.get_role_name(rid) == "runtime_gate_manager"
                for rid in principal.role_ids
            )
            if not is_runtime_manager:
                return "only_runtime_gate_manager_can_enable_gates"
        return None

    def check_capability_gate(
        self, action_type: str, tool_or_service_name: str, principal_id: str | None = None
    ) -> str | None:
        from raiker.phase_gates import CapabilityState, default_capability_gates
        cap_name = CAPABILITY_GATE_MAP.get(action_type) or CAPABILITY_GATE_MAP.get(tool_or_service_name)
        if cap_name is None:
            return None
        persisted = (
            self.store.get_principal_capability_gate_state(str(principal_id), cap_name)
            if self._uses_principal_controls(principal_id)
            else self.store.get_capability_gate_state(cap_name)
        )
        if persisted is not None:
            state = persisted["state"]
            if state in (CapabilityState.DISABLED, CapabilityState.PLANNED):
                return "disabled_by_capability_gate"
            return None
        if self._uses_principal_controls(principal_id):
            return "disabled_by_capability_gate"
        try:
            gates = default_capability_gates()
            gate = gates.get(cap_name)
            if gate is None:
                return "unknown_capability_gate"
            if gate.state in (CapabilityState.DISABLED, CapabilityState.PLANNED):
                return "disabled_by_capability_gate"
            return None
        except Exception:
            return "unknown_capability_gate"

    def get_persisted_capability_state(
        self, cap_name: str, principal_id: str | None = None
    ) -> dict[str, Any] | None:
        return (
            self.store.get_principal_capability_gate_state(str(principal_id), cap_name)
            if self._uses_principal_controls(principal_id)
            else self.store.get_capability_gate_state(cap_name)
        )

    def get_effective_capability_gate(
        self, cap_name: str, principal_id: str | None = None
    ) -> dict[str, Any]:
        from raiker.phase_gates import CapabilityState, default_capability_gates
        persisted = self.get_persisted_capability_state(cap_name, principal_id)
        if persisted is not None:
            return {"capability": cap_name, "state": persisted["state"], "source": "persisted"}
        if self._uses_principal_controls(principal_id):
            return {
                "capability": cap_name,
                "state": CapabilityState.DISABLED,
                "source": "principal_fail_closed",
            }
        gates = default_capability_gates()
        gate = gates.get(cap_name)
        if gate is None:
            return {"capability": cap_name, "state": CapabilityState.DISABLED, "source": "unknown"}
        return {"capability": cap_name, "state": gate.state.value, "source": "static_default"}

    def _resolve_decision_mode(self, capability: str, principal_id: str | None = None) -> DecisionMode:
        persisted = (
            self.store.get_principal_capability_decision_mode(str(principal_id), capability)
            if self._uses_principal_controls(principal_id)
            else self.store.get_capability_decision_mode(capability)
        )
        mode = parse_decision_mode(persisted) if persisted else None
        return mode or DEFAULT_DECISION_MODE

    def get_capability_decision_mode(self, capability: str, principal_id: str | None = None) -> str:
        return self._resolve_decision_mode(capability, principal_id).value

    def set_capability_decision_mode(
        self, capability: str, mode: str, principal: Principal, reason: str = "",
    ) -> str | None:
        """Governed, human-only change of a capability's decision mode.

        Returns None on success or a reason-code string when refused. Permissive
        modes (``always_allow``/``auto``) may only be set on capabilities with a
        real executor, so a sensitive/no-executor domain can never be relaxed
        into acting.
        """
        from raiker.phase_gates import ALL_CAPABILITIES
        from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES

        gate_check = self._check_human_runtime_gate_manager(principal)
        if gate_check:
            self._event("capability_decision_mode_set", principal.principal_id, {
                "capability": capability, "requested_mode": mode,
                "status": "denied", "reason": gate_check,
            })
            return gate_check
        if capability not in ALL_CAPABILITIES:
            return f"unknown_capability:{capability}"
        parsed = parse_decision_mode(mode)
        if parsed is None:
            return f"invalid_decision_mode:{mode}"
        if parsed in PERMISSIVE_MODES and capability not in REAL_EXECUTOR_CAPABILITIES:
            self._event("capability_decision_mode_set", principal.principal_id, {
                "capability": capability, "requested_mode": parsed.value,
                "status": "denied", "reason": "decision_mode_requires_executor",
            })
            return f"decision_mode_requires_executor:{capability}"
        now = utc_now()
        record = {
            "capability": capability,
            "decision_mode": parsed.value,
            "set_by": principal.principal_id,
            "set_at": now,
            "reason": reason,
            "event_id": "",
            "created_at": now,
            "updated_at": now,
        }
        if self._uses_principal_controls(principal.principal_id):
            self.store.upsert_principal_capability_decision_mode(principal.principal_id, record)
        else:
            self.store.upsert_capability_decision_mode(record)
        self._event("capability_decision_mode_set", principal.principal_id, {
            "capability": capability, "decision_mode": parsed.value, "reason": reason,
        })
        return None

    def get_runtime_mode(self, principal_id: str | None = None) -> dict[str, Any]:
        active = (
            self.store.get_principal_runtime_mode(str(principal_id))
            if self._uses_principal_controls(principal_id) else self.store.get_active_runtime_mode()
        )
        if active is not None:
            return active
        return {
            "runtime_mode_id": "default_dev_preview",
            "mode_name": "development_preview",
            "status": "active",
            "activated_by": "system",
            "activated_at": utc_now(),
            "reason": "Default runtime mode",
        }

    def activate_runtime_mode(
        self, mode_name: str, principal: Principal, reason: str = "",
    ) -> str | None:
        gate_check = self._check_human_runtime_gate_manager(principal)
        if gate_check:
            self._event("runtime_mode_activation_requested", principal.principal_id, {
                "mode_name": mode_name, "status": "denied", "reason": gate_check,
            })
            return gate_check
        if mode_name not in ("development_preview", "local_single_user_safe", "local_single_user_runtime",
                             "multi_user_local_runtime", "hosted_or_networked_runtime"):
            return f"unknown_runtime_mode:{mode_name}"
        now = utc_now()
        record = {
            "runtime_mode_id": new_id("rm_"),
            "mode_name": mode_name,
            "status": "active",
            "activated_by": principal.principal_id,
            "activated_at": now,
            "reason": reason,
            "created_at": now,
            "updated_at": now,
        }
        if self._uses_principal_controls(principal.principal_id):
            self.store.upsert_principal_runtime_mode(principal.principal_id, record)
        else:
            self.store.disable_all_runtime_modes(principal.principal_id, f"activating {mode_name}")
            self.store.insert_runtime_mode_state(record)
        self._event("runtime_mode_activated", principal.principal_id, {
            "mode_name": mode_name, "runtime_mode_id": record["runtime_mode_id"], "reason": reason,
        })
        return None

    def disable_runtime_mode(self, principal: Principal, reason: str = "") -> str | None:
        gate_check = self._check_human_runtime_gate_manager(principal)
        if gate_check:
            self._event("runtime_mode_disabled", principal.principal_id, {
                "status": "denied", "reason": gate_check,
            })
            return gate_check
        now = utc_now()
        record = {
            "runtime_mode_id": new_id("rm_"),
            "mode_name": "development_preview",
            "status": "active",
            "activated_by": principal.principal_id,
            "activated_at": now,
            "reason": "Disabled; reverted to development_preview",
            "created_at": now,
            "updated_at": now,
        }
        if self._uses_principal_controls(principal.principal_id):
            self.store.upsert_principal_runtime_mode(principal.principal_id, record)
        else:
            self.store.disable_all_runtime_modes(principal.principal_id, reason)
            self.store.insert_runtime_mode_state(record)
        self._event("runtime_mode_disabled", principal.principal_id, {
            "mode_name": "development_preview", "reason": reason,
        })
        return None

    def request_capability_transition(
        self, capability: str, target_state: str, principal: Principal, reason: str = "",
        confirmation_token: str | None = None,
    ) -> str | None:
        from raiker.phase_gates import ALL_CAPABILITIES, CapabilityState, default_capability_gates
        gate_check = self._check_human_runtime_gate_manager(principal)
        if gate_check:
            self._event("capability_transition_requested", principal.principal_id, {
                "capability": capability, "target_state": target_state,
                "status": "denied", "reason": gate_check,
            })
            return gate_check
        if capability not in ALL_CAPABILITIES:
            return f"unknown_capability:{capability}"
        allowed_targets = {s.value for s in CapabilityState}
        if target_state not in allowed_targets:
            return f"invalid_target_state:{target_state}"
        activation_reason = evaluate_activation_requirement(
            capability, target_state, principal, self.store,
            registry=self.executor_registry, confirmation_token=confirmation_token,
        )
        if activation_reason is not None:
            return activation_reason
        now = utc_now()
        gates = default_capability_gates()
        default_gate = gates.get(capability)
        readiness_json = ""
        if default_gate is not None:
            readiness_json = json.dumps({
                "phase": default_gate.phase,
                "default_state": default_gate.state.value,
                "policy_ready": default_gate.policy_ready,
                "contract_ready": default_gate.contract_ready,
                "storage_ready": default_gate.storage_ready,
                "event_ready": default_gate.event_ready,
                "test_ready": default_gate.test_ready,
            })
        self._event("capability_transition_requested", principal.principal_id, {
            "capability": capability, "target_state": target_state, "reason": reason,
        })
        record = {
            "capability": capability,
            "state": target_state,
            "runtime_mode": "",
            "requested_by": principal.principal_id,
            "requested_at": now,
            "activated_by": principal.principal_id,
            "activated_at": now if target_state not in ("disabled", "planned") else "",
            "reason": reason,
            "readiness_snapshot_json": readiness_json,
            "created_at": now,
            "updated_at": now,
        }
        if self._uses_principal_controls(principal.principal_id):
            self.store.upsert_principal_capability_gate_state(principal.principal_id, record)
        else:
            self.store.upsert_capability_gate_state(record)
        event_type = "capability_enabled" if target_state not in ("disabled", "planned") else "capability_disabled"
        self._event(event_type, principal.principal_id, {
            "capability": capability, "new_state": target_state, "reason": reason,
        })
        return None

    def evaluate_effective_permissions(self, principal: Principal) -> dict[str, Any]:
        return {
            "principal_id": principal.principal_id,
            "principal_type": principal.principal_type.value,
            "role_ids": list(principal.role_ids),
            "domain_scopes": list(principal.domain_scopes),
            "max_runtime_mode": principal.max_runtime_mode,
            "is_active": principal.is_active,
            "is_expired": principal.expires_at is not None and utc_now() > principal.expires_at,
        }

    def route_action(self, action: GovernedAction, principal: Principal) -> GovernedActionResult:
        self._event(
            event_type="action_proposed",
            actor="runtime_authority",
            payload={
                "action_id": action.action_id,
                "action_type": action.action_type,
                "principal_id": action.principal_id,
                "domain_scope": action.domain_scope,
                "risk_level": action.risk_level,
            },
            session_id=action.session_id,
            turn_id=action.turn_id,
        )

        active_check = self.check_principal_active(principal)
        if active_check:
            return GovernedActionResult(
                action_id=action.action_id,
                decision="deny",
                message=active_check,
            )

        domain_check = self.check_domain_scope(principal, action.domain_scope)
        if domain_check:
            return GovernedActionResult(
                action_id=action.action_id,
                decision="deny",
                message=domain_check,
            )

        self_approval = self.check_self_approval(principal, action)
        if self_approval:
            return GovernedActionResult(
                action_id=action.action_id,
                decision="deny",
                message=self_approval,
            )

        self_grant = self.check_self_grant(principal, action.action_type)
        if self_grant:
            return GovernedActionResult(
                action_id=action.action_id,
                decision="deny",
                message=self_grant,
            )

        gate_check = self.check_runtime_gate_enable(principal, action.action_type)
        if gate_check:
            return GovernedActionResult(
                action_id=action.action_id,
                decision="deny",
                message=gate_check,
            )

        cap_gate = self.check_capability_gate(
            action.action_type, action.tool_or_service_name, principal.principal_id
        )
        if cap_gate:
            return GovernedActionResult(
                action_id=action.action_id,
                decision="disabled_by_capability_gate" if cap_gate == "disabled_by_capability_gate" else "deny",
                message=cap_gate,
            )

        from raiker.contracts.models import ToolAction

        tool_action = ToolAction(
            action_id=action.action_id,
            tool_name=action.tool_or_service_name,
            arguments=action.arguments,
            risk_level=action.risk_level,
            requires_approval=action.requires_approval,
            proposed_by=principal.principal_id,
        )
        decision = self.policy_engine.review(tool_action)
        self._event(
            event_type="policy_decision",
            actor="policy_engine",
            payload=decision.to_dict(),
            session_id=action.session_id,
            turn_id=action.turn_id,
        )

        if decision.decision == "deny":
            return GovernedActionResult(
                action_id=action.action_id,
                decision="deny",
                policy_decision=decision,
                message="denied_by_policy",
            )

        # Per-capability decision mode (ask / deny / always_allow / auto) is
        # resolved only for governed capabilities; unmapped action types keep
        # their pre-existing behavior.
        cap_for_mode = CAPABILITY_GATE_MAP.get(action.action_type) or CAPABILITY_GATE_MAP.get(
            action.tool_or_service_name
        )
        mode = self._resolve_decision_mode(cap_for_mode, principal.principal_id) if cap_for_mode else None
        if mode == DecisionMode.DENY:
            return GovernedActionResult(
                action_id=action.action_id,
                decision="deny",
                policy_decision=decision,
                message="denied_by_decision_mode",
            )

        # Critical-risk actions always require a human, regardless of decision
        # mode — always_allow/auto can never let an AI take a critical action.
        if action.risk_level == RiskLevelValue.CRITICAL:
            if principal.principal_type != PrincipalType.HUMAN:
                return GovernedActionResult(
                    action_id=action.action_id,
                    decision="deny",
                    policy_decision=decision,
                    message="critical_action_requires_human_confirmation",
                )
            return GovernedActionResult(
                action_id=action.action_id,
                decision="needs_human_confirmation",
                policy_decision=decision,
                message="critical_action_requires_human_confirmation",
            )

        raw_needs_approval = action.requires_approval or decision.decision == "needs_approval"
        if mode is None:
            effective_needs_approval = raw_needs_approval
        elif mode == DecisionMode.ALWAYS_ALLOW:
            effective_needs_approval = False
        elif mode == DecisionMode.AUTO:
            # Owner delegated the decision to Raiker's deterministic risk policy;
            # policy hard-denies already returned above, and critical is floored.
            effective_needs_approval = auto_requires_approval(action.risk_level)
        else:  # ASK (default) forces approval for AI-proposed actions
            effective_needs_approval = True

        if effective_needs_approval and principal.principal_type != PrincipalType.HUMAN:
            return GovernedActionResult(
                    action_id=action.action_id,
                    decision="needs_approval",
                    policy_decision=decision,
                    message="approval_required",
                )

        if action.requires_risk_acceptance:
            valid = self.store.find_valid_risk_acceptance(
                principal_id=principal.principal_id,
                action_type=action.action_type,
                domain_scope=action.domain_scope,
                risk_level=action.risk_level,
            )
            if not valid:
                return GovernedActionResult(
                    action_id=action.action_id,
                    decision="needs_risk_acceptance",
                    policy_decision=decision,
                    message="risk_acceptance_required",
                )
            if valid.get("one_time_or_reusable") == "one_time":
                self.store.consume_risk_acceptance(valid["risk_acceptance_id"])

        capability = CAPABILITY_GATE_MAP.get(action.action_type, action.action_type)
        executor = self.executor_registry.get(capability)
        if executor is not None:
            result = executor.execute(action, principal)
            event_type = "action_executed" if result.ok else "action_failed"
            self._event(
                event_type=event_type,
                actor="executor",
                payload={
                    "action_id": result.action_id,
                    "capability": result.capability,
                    "ok": result.ok,
                    "reason_code": result.reason_code,
                    "summary": result.summary,
                    "artifacts": result.artifacts,
                },
                session_id=action.session_id,
                turn_id=action.turn_id,
            )
            return GovernedActionResult(
                action_id=action.action_id,
                decision="allow",
                policy_decision=decision,
                message="executed" if result.ok else f"execution_failed:{result.reason_code}",
                error=None if result.ok else result.reason_code,
            )

        return GovernedActionResult(
            action_id=action.action_id,
            decision="allow",
            policy_decision=decision,
            message="allowed",
            error="execution_unavailable:no_executor",
        )


class ActionRouter:
    def __init__(self, authority: RuntimeAuthority) -> None:
        self.authority = authority

    def route(
        self,
        action_type: str,
        tool_or_service_name: str,
        arguments: dict[str, Any],
        principal: Principal,
        *,
        domain_scope: str = "",
        risk_level: str = RiskLevelValue.LOW,
        expected_effect: str = "",
        requires_approval: bool = False,
        requires_risk_acceptance: bool = False,
        session_id: str = "",
        turn_id: str | None = None,
    ) -> GovernedActionResult:
        action = GovernedAction(
            action_id=new_id("act_"),
            principal_id=principal.principal_id,
            action_type=action_type,
            tool_or_service_name=tool_or_service_name,
            arguments=arguments,
            domain_scope=domain_scope,
            risk_level=risk_level,
            expected_effect=expected_effect,
            requires_approval=requires_approval,
            requires_risk_acceptance=requires_risk_acceptance,
            session_id=session_id,
            turn_id=turn_id,
        )
        return self.authority.route_action(action, principal)
