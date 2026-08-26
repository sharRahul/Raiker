from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import PolicyDecision
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.models.tool_registry import TOOL_CAPABILITY_BY_TOOL
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.runtime.authority import grants
from raiker.runtime.authority.activation import evaluate_activation_requirement
from raiker.runtime.authority.critical import classify_critical
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
    RAIKER_RUNTIME,
    RUNTIME_STATUS_ACTIVE,
    RUNTIME_STATUS_DISABLED,
    Principal,
    PrincipalType,
    RiskAcceptance,
    RiskLevelValue,
    normalize_runtime_mode,
)
from raiker.runtime.executors.registry import ExecutorRegistry
from raiker.storage.internal_paths import display_path
from raiker.storage.sqlite import SQLiteStore

if TYPE_CHECKING:
    from raiker.checkpoints.capture import CheckpointCaptureService

NON_ALLOW_DECISIONS = frozenset({
    "deny",
    "needs_approval",
    "needs_risk_acceptance",
    "needs_human_confirmation",
    "disabled_by_capability_gate",
})

# Maps action_type / tool_or_service_name to capability gate names
# Tool -> capability, plus the capability aliases the runtime authority routes
# on directly. The **tool** half is derived from `raiker.models.tool_registry`,
# so a tool cannot be added to the catalogue and left answering to no gate; the
# aliases below stay written out, because a capability name is a different
# vocabulary from a tool name and has no registry entry to come from.
CAPABILITY_GATE_MAP: dict[str, str] = {
    **TOOL_CAPABILITY_BY_TOOL,
    "admin_mutation": "admin_mutation",
    "role_mutation": "role_mutation",
    "policy_mutation": "policy_mutation",
    "user_create": "admin_mutation",
    "user_deactivate": "admin_mutation",
    "role_create": "role_mutation",
    "role_grant": "role_mutation",
    "role_revoke": "role_mutation",
    # The relay is a governed capability in its own right, so name it here too:
    # without a mapping, `check_capability_gate` finds no gate for it and the
    # owner's off switch would silently not apply to the one executor that turns
    # an approval into a real mutation.
    "approval_execution_relay": "approval_execution_relay",
    "write_file": "file_write_execution",
    "create_document": "file_write_execution",
    "edit_file": "file_write_execution",
    "file_write_execution": "file_write_execution",
    "apply_patch": "patch_apply_execution",
    "patch_apply_execution": "patch_apply_execution",
    "memory_write": "memory_write_execution",
    "memory_forget": "memory_forget_execution",
    "audit_export": "audit_export",
    "checkpoint_restore": "checkpoint_restore_execution",
    "checkpoint_restore_execution": "checkpoint_restore_execution",
    # BUG-62 — the two local planning mutations. Naming them here is what gives
    # the owner a switch over them and what lets an approval carry them out: an
    # unmapped tool has no gate to consult and no capability to relay into.
    "create_task": "task_management_runtime",
    "task_management_runtime": "task_management_runtime",
    "assign_session_project": "project_assignment_runtime",
    "project_assignment_runtime": "project_assignment_runtime",
    # B11 — the git write path. Both tools answer to one capability, so the
    # owner has a single switch over "may the agent change my repository".
    "git_branch": "git_write_execution",
    "git_commit": "git_write_execution",
    "git_write_execution": "git_write_execution",
    # BUG-67 — a push is not a local write. It carries repository content off the
    # machine with the owner's credential, so it answers to its own switch: an
    # owner who lets the agent commit has not thereby let it publish.
    "git_push": "git_push_execution",
    "git_push_execution": "git_push_execution",
    # B11 — a GitHub write is the same credential reaching the same host as
    # `github_read`, so it answers to the connector's own gate rather than
    # inventing a second one.
    "github_write": "connector_github_runtime",
    "shell": "shell_execution",
    "remote_execute": "remote_execution_cap",
    "cloud_execute": "cloud_execution_cap",
    "process": "process_execution",
    "web_fetch": "web_fetch",
    # B12/C7 — search is the same capability pointed at an owner-configured
    # endpoint, so it answers to the same gate and the same decision mode.
    "web_search": "web_fetch",
    "graph_indexing": "graph_indexing_runtime",
    # B9 — the repository code map. `code_map_search` is a *read* of a local,
    # derived index, so it is read-shaped in the policy engine; naming it here is
    # what gives the owner one switch over the whole feature — the scan and the
    # search alike — instead of a gate that only covers half of it.
    "code_map_search": "code_map_indexing",
    "code_map_references": "code_map_indexing",
    "code_map_indexing": "code_map_indexing",
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
    # GEP-04 — the tool an owner actually meets. Naming it here is what gives
    # them one switch over delegation, the same way `code_map_search` above
    # gives them one switch over the whole code map rather than half of it.
    "spawn_subagent": "subagents",
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
class CriticalConfirmation:
    """A live human's manual confirmation of one parked critical action (F7).

    Produced *only* by :meth:`RuntimeAuthority.resolve_critical_approval`, after
    it has verified the resolver is human, the approving session is valid, step-up
    was satisfied, and the intent is unchanged. It rides on the target action
    through the Workstream A relay into :meth:`RuntimeAuthority.route_action`,
    where it is the single signal that lets a critical action past the deny floor.
    It is never constructed on the AI-proposed path, and the router re-validates
    it against persisted state (human principal + a claimed critical approval), so
    its mere presence cannot smuggle a critical action through.
    """

    approval_id: str
    confirmed_by: str
    step_up_verified: bool = False


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
    # The conversation this action *came from*, when that is not the session
    # executing it. An approval resolved from the inbox executes under the
    # inbox's API session, so a capability whose subject is the proposing chat —
    # `project_assignment_runtime` moves that chat — would otherwise have no way
    # to name it. Set only by the approval relay, from the approval row.
    origin_session_id: str = ""
    critical_confirmation: CriticalConfirmation | None = None
    # Internal broker-only override after the owner's per-turn approval mode has
    # already selected auto/skip. It changes the decision path, never the actor.
    decision_mode_override: str | None = None
    # Runtime-authored proof for command execution. Model arguments can never
    # populate these fields; the approval relay or standing-grant broker does.
    authority_kind: str = ""
    authority_id: str = ""


@dataclass(frozen=True)
class GovernedActionResult:
    action_id: str
    decision: str
    policy_decision: PolicyDecision | None = None
    risk_acceptance: RiskAcceptance | None = None
    approved: bool = False
    message: str = ""
    error: str | None = None
    approval_id: str | None = None
    artifacts: dict[str, Any] = field(default_factory=dict)
    # Executor output for the immediate in-process consumer only. Unlike
    # artifacts, this is never copied into the event log.
    transient: dict[str, Any] = field(default_factory=dict)


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
        self._capture_service: CheckpointCaptureService | None = None

    @property
    def capture_service(self) -> CheckpointCaptureService:
        """Lazily-built pre-image capture service (Workstream B / B1).

        Records the pre-image of every workspace-file mutation routed through
        this authority into a content-addressed blob store, so mutations become
        reversible. Built lazily to avoid an import cycle at module load and to
        keep the constructor signature unchanged for existing callers.
        """
        if self._capture_service is None:
            from raiker.checkpoints.capture import CheckpointCaptureService

            self._capture_service = CheckpointCaptureService(self.store)
        return self._capture_service

    @staticmethod
    def _checkpoint_reason(stage: str, exc: Exception) -> str:
        kind = "os_error" if isinstance(exc, OSError) else "invalid_path" if isinstance(
            exc, ValueError
        ) else "internal_error"
        return f"checkpoint_{stage}_{kind}"

    @staticmethod
    def _checkpoint_remediation(reason_code: str) -> str:
        if reason_code.endswith("_os_error"):
            return "Check workspace permissions and enable Windows long-path support."
        if reason_code.endswith("_invalid_path"):
            return "Choose a valid file path inside the workspace."
        return "Open Diagnostics and retry after repairing checkpoint storage."

    def _capture_outcome(
        self,
        *,
        ok: bool,
        stage: str,
        reason_code: str,
        path: object | None,
    ) -> dict[str, Any]:
        checked_at = utc_now()
        safe_path = display_path(str(path))[:512] if path else None
        remediation = "" if ok else self._checkpoint_remediation(reason_code)
        outcome = {
            "ok": ok,
            "stage": stage,
            "reason_code": reason_code,
            "display_path": safe_path,
            "checked_at": checked_at,
            "remediation": remediation,
        }
        self.store.upsert_checkpoint_capture_health(
            ok=ok,
            stage=stage,
            reason_code=reason_code,
            display_path=safe_path,
            checked_at=checked_at,
            remediation=remediation,
        )
        return outcome

    def _snapshot_pre_image(
        self, capability: str, arguments: dict[str, Any]
    ) -> tuple[Any, dict[str, Any] | None]:
        """Return a snapshot plus an honest structured eligibility/outcome."""
        if not self.capture_service.eligible(capability):
            return None, None
        path = arguments.get("path")
        try:
            pre_image = self.capture_service.snapshot_pre_image(capability, arguments)
        except Exception as exc:  # capture cannot block an approved mutation
            reason = self._checkpoint_reason("snapshot", exc)
            return None, self._capture_outcome(
                ok=False, stage="snapshot", reason_code=reason, path=path
            )
        if pre_image is None:
            return None, {
                "ok": False,
                "stage": "ineligible",
                "reason_code": "checkpoint_capture_ineligible",
                "display_path": display_path(str(path))[:512] if path else None,
                "checked_at": utc_now(),
                "remediation": "Choose a valid file path inside the workspace.",
            }
        return pre_image, {
            "ok": True,
            "stage": "snapshot_ready",
            "reason_code": "checkpoint_snapshot_ready",
            "display_path": display_path(str(path))[:512] if path else None,
            "checked_at": utc_now(),
            "remediation": "",
        }

    def _commit_pre_image(
        self, pre_image: Any, action: GovernedAction, principal: Principal
    ) -> dict[str, Any]:
        """Persist the captured pre-image + emit a metadata-only capture event.

        Isolated in try/except: a checkpoint-capture failure is recorded as a
        metadata event but never propagates into the mutation result.
        """
        # BUG-235 — file the pre-image under the *conversation*, not the inbox.
        # A file write approved from the Approvals inbox executes under the API
        # session that resolved it, while the checkpoints it must be restorable
        # from belong to the chat that proposed it. `compute_restore_plan`
        # selects capture entries by the checkpoint's `session_id`, so a capture
        # filed under the API session was invisible to every restore plan ever
        # computed: the pre-image existed, and nothing could reach it. The relay
        # already carries the proposing conversation in `origin_session_id`;
        # using it is what makes the capture and the checkpoint agree.
        capture_session_id = action.origin_session_id or action.session_id
        try:
            for item in pre_image if isinstance(pre_image, list) else [pre_image]:
                meta = self.capture_service.commit(
                    item,
                    session_id=capture_session_id,
                    turn_id=action.turn_id,
                    action_id=action.action_id,
                    principal_id=principal.principal_id,
                )
                self._event(
                    event_type="checkpoint_captured",
                    actor="checkpoint_capture",
                    payload=meta,
                    session_id=capture_session_id,
                    turn_id=action.turn_id,
                )
            return self._capture_outcome(
                ok=True,
                stage="commit",
                reason_code="checkpoint_capture_ok",
                path=pre_image[0].workspace_path
                if isinstance(pre_image, list) and pre_image
                else pre_image.workspace_path,
            )
        except Exception as exc:  # pragma: no cover - defensive; capture is best-effort
            reason_code = self._checkpoint_reason("commit", exc)
            self._event(
                event_type="checkpoint_capture_failed",
                actor="checkpoint_capture",
                payload={
                    "action_id": action.action_id,
                    "capability": (
                        pre_image[0].capability if isinstance(pre_image, list) and pre_image
                        else pre_image.capability if pre_image else None
                    ),
                    "reason": type(exc).__name__,
                },
                session_id=action.session_id,
                turn_id=action.turn_id,
            )
            return self._capture_outcome(
                ok=False,
                stage="commit",
                reason_code=reason_code,
                path=(
                    pre_image[0].workspace_path
                    if isinstance(pre_image, list) and pre_image
                    else pre_image.workspace_path if pre_image else None
                ),
            )

    def _capture_action_posture(
        self,
        principal: Principal,
        action: GovernedAction,
        *,
        mode: DecisionMode | None = None,
        grant_applied: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build the F1 (ZT-3) posture snapshot for a governed action.

        Extends the base identity/session/auth-strength snapshot with the
        *decision path* — which decision mode governed the action and which
        standing grant (if any) authorized an unprompted run. Metadata-only and
        never raises into the action path.
        """
        from raiker.runtime.authority.posture import capture_posture

        try:
            posture = capture_posture(self.store, principal, action.session_id or "")
        except Exception:  # pragma: no cover - posture is best-effort metadata
            posture = {"principal_id": principal.principal_id}
        posture["decision_mode"] = mode.value if mode is not None else None
        posture["grant_id"] = str(grant_applied["grant_id"]) if grant_applied else None
        posture["action_type"] = action.action_type
        return posture

    def _uses_principal_controls(self, principal_id: str | None) -> bool:
        return self.store.account_scope(principal_id) is not None

    def _control_scope(self, principal_id: str | None) -> str | None:
        """Return the owner's control scope without changing the acting principal."""
        return self.store.account_scope(principal_id)

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
        control_scope = self._control_scope(principal_id)
        persisted = (
            self.store.get_principal_capability_gate_state(control_scope, cap_name)
            if control_scope is not None
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
        control_scope = self._control_scope(principal_id)
        return (
            self.store.get_principal_capability_gate_state(control_scope, cap_name)
            if control_scope is not None
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
        control_scope = self._control_scope(principal_id)
        persisted = (
            self.store.get_principal_capability_decision_mode(control_scope, capability)
            if control_scope is not None
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
        """The one runtime, and whether it is accepting executions.

        A stored row keeps whatever it recorded, except that its ``mode_name``
        is normalised: a workspace written before the runtime was unified holds
        one of the five historical names, and reporting those back would imply a
        choice that no longer exists. With no stored row at all the runtime is
        active — there is nothing left to select, so a fresh install is ready.
        """
        control_scope = self._control_scope(principal_id)
        stored = (
            self.store.get_principal_runtime_mode(control_scope)
            if control_scope is not None else self.store.get_latest_runtime_mode()
        )
        if stored is not None:
            record = dict(stored)
            record["mode_name"] = normalize_runtime_mode(record.get("mode_name")) or RAIKER_RUNTIME
            return record
        return {
            "runtime_mode_id": "raiker_runtime_default",
            "mode_name": RAIKER_RUNTIME,
            "status": RUNTIME_STATUS_ACTIVE,
            "activated_by": "system",
            "activated_at": utc_now(),
            "reason": "Raiker runs one runtime; it is active unless explicitly disabled.",
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
        # Every historical mode name still resolves — a CLI line, a stored row,
        # or an older client asking for `local_single_user_runtime` gets the one
        # runtime. Anything else is still refused rather than assumed.
        resolved = normalize_runtime_mode(mode_name)
        if resolved is None:
            return f"unknown_runtime_mode:{mode_name}"
        now = utc_now()
        record = {
            "runtime_mode_id": new_id("rm_"),
            "mode_name": resolved,
            "status": RUNTIME_STATUS_ACTIVE,
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
            "mode_name": resolved, "runtime_mode_id": record["runtime_mode_id"], "reason": reason,
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
        # Disabling is now what it says: the one runtime stops accepting new
        # executions. It used to mean "fall back to development_preview", which
        # left a runtime running under a name that implied it was not.
        record = {
            "runtime_mode_id": new_id("rm_"),
            "mode_name": RAIKER_RUNTIME,
            "status": RUNTIME_STATUS_DISABLED,
            "activated_by": principal.principal_id,
            "activated_at": now,
            "reason": reason or "The owner disabled the agent runtime.",
            "created_at": now,
            "updated_at": now,
        }
        if self._uses_principal_controls(principal.principal_id):
            self.store.upsert_principal_runtime_mode(principal.principal_id, record)
        else:
            self.store.disable_all_runtime_modes(principal.principal_id, reason)
            self.store.insert_runtime_mode_state(record)
        self._event("runtime_mode_disabled", principal.principal_id, {
            "mode_name": RAIKER_RUNTIME, "status": RUNTIME_STATUS_DISABLED, "reason": reason,
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

    # ── scoped standing grants (Workstream F / F3, ZT-5) ──────────────────────

    def create_standing_grant(
        self,
        *,
        granted_by: Principal,
        principal_id: str,
        action_type: str,
        risk_ceiling: str,
        tool_name: str = "",
        scope_pattern: str = "*",
        reason: str = "",
        ttl_days: float = grants.DEFAULT_GRANT_TTL_DAYS,
    ) -> str | dict[str, Any]:
        """Create a scoped standing grant (a critical, human-decided action).

        Returns a reason-code string on refusal or the persisted grant row on
        success. Only a human may create a grant, the ceiling must be strictly
        sub-critical, and the grant is created for a *sub-critical* action shape:
        if the requested action type itself classifies as critical (F6), it can
        never be pre-authorized by a grant and creation is refused.
        """
        critical_match = classify_critical(action_type, tool_name, {})
        if critical_match is not None:
            self._event("standing_grant_denied", granted_by.principal_id, {
                "action_type": action_type, "reason": "grant_target_is_critical",
                "criterion": critical_match.code,
            })
            return "grant_target_is_critical"
        try:
            record = grants.build_grant_record(
                principal_id=principal_id,
                granted_by=granted_by,
                action_type=action_type,
                tool_name=tool_name,
                scope_pattern=scope_pattern,
                risk_ceiling=risk_ceiling,
                reason=reason,
                ttl_days=ttl_days,
            )
        except grants.GrantValidationError as exc:
            self._event("standing_grant_denied", granted_by.principal_id, {
                "action_type": action_type, "reason": str(exc),
            })
            return str(exc)
        self.store.insert_standing_grant(record)
        self._event("standing_grant_created", granted_by.principal_id, {
            "grant_id": record["grant_id"],
            "principal_id": principal_id,
            "action_type": action_type,
            "tool_name": tool_name,
            "scope_pattern": scope_pattern,
            "risk_ceiling": risk_ceiling,
            "expires_at": record["expires_at"],
            "reason": reason,
        })
        return record

    def list_standing_grants(
        self, granted_by: str | None = None, *, include_inactive: bool = True
    ) -> list[dict[str, Any]]:
        return self.store.list_standing_grants(
            granted_by=granted_by, include_inactive=include_inactive
        )

    def revoke_standing_grant(
        self, grant_id: str, revoker: Principal, granted_by: str | None = None
    ) -> str | None:
        """Human-only revoke. Returns None on success or a reason code."""
        if revoker.principal_type != PrincipalType.HUMAN:
            return "only_human_may_revoke_grant"
        ok = self.store.revoke_standing_grant(
            grant_id, revoked_by=revoker.principal_id, granted_by=granted_by
        )
        if not ok:
            return "grant_not_found_or_already_revoked"
        self._event("standing_grant_revoked", revoker.principal_id, {"grant_id": grant_id})
        return None

    def find_matching_standing_grant(
        self, principal: Principal, action: GovernedAction, risk_level: str
    ) -> dict[str, Any] | None:
        """Return the active grant that covers this action shape, if any.

        Consulted only for sub-critical AI-proposed actions that would otherwise
        need approval (the router guarantees critical never reaches here). The
        first covering grant wins; the caller logs its use.
        """
        if principal.principal_type == PrincipalType.HUMAN:
            return None
        if risk_level == RiskLevelValue.CRITICAL:
            return None
        for row in self.store.find_active_standing_grants(
            principal.principal_id, action.action_type
        ):
            if grants.grant_covers(
                row,
                action_type=action.action_type,
                tool_name=action.tool_or_service_name,
                scope=action.domain_scope,
                risk_level=risk_level,
            ):
                return row
        return None

    # ── critical approval lifecycle (Workstream F / F7, ZT-7) ─────────────────

    def _critical_confirmation_valid(
        self, action: GovernedAction, principal: Principal
    ) -> bool:
        """True only for a genuine, human-issued confirmation of a parked critical.

        A confirmation lets a critical action past the deny floor, so this guard
        is deliberately strict and re-checks *persisted* state (never trusting the
        object's mere presence): the acting principal must be a human, must be the
        principal named on the confirmation, and the referenced approval must be a
        real critical approval that the relay has already claimed for execution
        (``executing``). An AI can never satisfy the human-principal check, so no
        decision mode, grant, or subagent can forge its way through here.
        """
        confirmation = action.critical_confirmation
        if confirmation is None:
            return False
        if principal.principal_type != PrincipalType.HUMAN:
            return False
        if confirmation.confirmed_by != principal.principal_id:
            return False
        approval = self.store.load_approval(confirmation.approval_id)
        if approval is None or not approval.get("critical"):
            return False
        return approval.get("status") == "executing"

    def _park_critical_action(
        self,
        action: GovernedAction,
        principal: Principal,
        critical_match: Any,
    ) -> GovernedActionResult:
        """Park a critical action as an approval and notify the owner (F7).

        Replaces the old silent flat-deny of AI-proposed critical actions: the
        action's resting state is deny, but the owner is always told, and the
        parked approval is the object a live human later resolves (approve with
        step-up → execute; reject / expiry / non-human attempt → deny). Metadata
        only; the arguments never enter the notification or the audit payloads.
        """
        from raiker.contracts.models import ToolAction

        approval_id = new_id("appr_")
        tool_action = ToolAction(
            action_id=action.action_id,
            tool_name=action.tool_or_service_name,
            arguments=action.arguments,
            risk_level=action.risk_level,
            requires_approval=True,
            proposed_by=principal.principal_id,
        )
        posture = self._capture_action_posture(principal, action)
        criterion = critical_match.code if critical_match is not None else "declared_critical"
        try:
            self.store.insert_tool_action(
                tool_action, action.session_id or "critical", action.turn_id, "critical_pending"
            )
            self.store.insert_approval(approval_id, tool_action, critical=True)
        except Exception as exc:  # pragma: no cover - storage failure is fail-closed
            return GovernedActionResult(
                action_id=action.action_id,
                decision="deny",
                message=f"critical_park_failed:{type(exc).__name__}",
            )

        self._event(
            event_type="critical_approval_created",
            actor="runtime_authority",
            payload={
                "approval_id": approval_id,
                "action_id": action.action_id,
                "action_type": action.action_type,
                "criterion": criterion,
                "proposed_by": principal.principal_id,
                "posture": posture,
            },
            session_id=action.session_id,
            turn_id=action.turn_id,
        )

        notification_id: str | None = None
        try:
            from raiker.notify import notify_critical_approval_pending

            notification_id = notify_critical_approval_pending(
                self.store,
                acting_principal_id=principal.principal_id,
                approval_id=approval_id,
                tool_name=action.tool_or_service_name,
                criterion=criterion,
                risk_level=action.risk_level,
            )
        except Exception:  # pragma: no cover - delivery is best-effort
            notification_id = None

        self._event(
            event_type="critical_approval_notified",
            actor="runtime_authority",
            payload={
                "approval_id": approval_id,
                "notification_id": notification_id,
                "delivered": notification_id is not None,
                "posture": posture,
            },
            session_id=action.session_id,
            turn_id=action.turn_id,
        )
        return GovernedActionResult(
            action_id=action.action_id,
            decision="needs_human_confirmation",
            message="critical_action_parked_for_human",
            approval_id=approval_id,
        )

    def resolve_critical_approval(
        self,
        approval_id: str,
        resolver: Principal,
        *,
        approve: bool,
        step_up_verified: bool = False,
        session_id: str = "",
        reason: str = "",
    ) -> GovernedActionResult:
        """Resolve a parked critical approval by a live human's manual decision.

        The only path that can move a critical action off its deny resting state.
        Enforced here (F7): only a human may resolve; approving requires step-up
        verification and a non-degraded posture; the immutable intent and TTL are
        re-checked; and execution runs through the Workstream A relay with a
        one-shot :class:`CriticalConfirmation` so the target is re-verified at
        execution time. Any non-human attempt, manual reject, expiry, tamper, or
        degraded posture resolves to deny (or, for step-up, parks it unchanged so
        the human can verify harder and retry).
        """
        approval = self.store.load_approval(approval_id)
        if approval is None:
            return GovernedActionResult(
                action_id=approval_id, decision="deny",
                message="approval_not_found", approval_id=approval_id,
            )
        if not approval.get("critical"):
            return GovernedActionResult(
                action_id=approval_id, decision="deny",
                message="not_a_critical_approval", approval_id=approval_id,
            )
        if approval.get("status") != "pending":
            return GovernedActionResult(
                action_id=approval_id, decision="deny",
                message="approval_already_resolved", approval_id=approval_id,
            )

        # A non-human principal may never resolve a critical approval — the attempt
        # itself resolves the (critical, pending) action to deny, its resting state.
        # No decision mode, standing grant, scheduled routine, or subagent can
        # reach past this point.
        if resolver.principal_type != PrincipalType.HUMAN:
            self.store.resolve_approval(
                approval_id, status="denied", resolved_by=resolver.principal_id,
                resolved_at=utc_now(),
            )
            self._event(
                event_type="critical_approval_denied",
                actor="runtime_authority",
                payload={
                    "approval_id": approval_id,
                    "reason": "non_human_resolution",
                    "resolver": resolver.principal_id,
                },
                session_id=session_id,
            )
            return GovernedActionResult(
                action_id=approval_id,
                decision="deny",
                message="only_human_may_resolve_critical",
                approval_id=approval_id,
            )

        # TTL — a past-expiry critical approval resolves to `expired` and never runs.
        expires_at = approval.get("expires_at")
        if expires_at is not None and str(expires_at) and utc_now() > str(expires_at):
            self.store.expire_approval(approval_id)
            self._event(
                event_type="critical_approval_expired",
                actor="runtime_authority",
                payload={"approval_id": approval_id, "resolver": resolver.principal_id},
                session_id=session_id,
            )
            return GovernedActionResult(
                action_id=approval_id, decision="deny",
                message="critical_approval_expired", approval_id=approval_id,
            )

        # TOCTOU — the human approves the exact intent captured at park time.
        stored_hash = approval.get("action_payload_sha256")
        if stored_hash is not None:
            current_hash = self.store.tool_action_payload_sha256(
                str(approval.get("tool_name", "")),
                str(approval.get("arguments_json", "{}")),
                str(approval.get("risk_level", "")),
            )
            if str(stored_hash) != current_hash:
                self._event(
                    event_type="critical_approval_denied",
                    actor="runtime_authority",
                    payload={"approval_id": approval_id, "reason": "payload_tampered"},
                    session_id=session_id,
                )
                return GovernedActionResult(
                    action_id=approval_id, decision="deny",
                    message="critical_approval_payload_tampered", approval_id=approval_id,
                )

        # Posture — a revoked approving session denies before anything runs.
        posture = self._capture_action_posture(
            resolver, self._approval_as_action(approval, session_id)
        )
        from raiker.runtime.authority.posture import posture_degraded_reason

        degraded = posture_degraded_reason(posture)
        if degraded is not None:
            self._event(
                event_type="critical_approval_denied",
                actor="runtime_authority",
                payload={"approval_id": approval_id, "reason": degraded, "posture": posture},
                session_id=session_id,
            )
            return GovernedActionResult(
                action_id=approval_id, decision="deny",
                message=degraded, approval_id=approval_id,
            )

        # Manual reject → deny.
        if not approve:
            self.store.resolve_approval(
                approval_id, status="denied", resolved_by=resolver.principal_id,
                resolved_at=utc_now(),
            )
            self._event(
                event_type="critical_approval_resolved",
                actor="runtime_authority",
                payload={
                    "approval_id": approval_id, "outcome": "rejected",
                    "resolver": resolver.principal_id, "reason": reason, "posture": posture,
                },
                session_id=session_id,
            )
            return GovernedActionResult(
                action_id=approval_id, decision="deny",
                message="critical_action_rejected", approval_id=approval_id,
            )

        # Step-up — approving a critical action requires fresh verification. Until
        # F4 lands MFA-freshness tracking, the conservative rule is: an MFA-enrolled
        # human must present a step-up (fresh TOTP/re-auth); a human without MFA
        # cannot (nothing to step up to). The approval stays pending so the human
        # can verify harder and retry — "verify harder, not block harder".
        if posture.get("mfa_enrolled") and not step_up_verified:
            self._event(
                event_type="critical_approval_step_up_required",
                actor="runtime_authority",
                payload={"approval_id": approval_id, "resolver": resolver.principal_id, "posture": posture},
                session_id=session_id,
            )
            return GovernedActionResult(
                action_id=approval_id, decision="needs_step_up",
                message="critical_approval_step_up_required", approval_id=approval_id,
            )

        # Human-approved with step-up satisfied. Log the resolution, then execute
        # through the Workstream A relay with a one-shot confirmation so the target
        # is re-governed (gate + policy + posture) at execution time.
        self._event(
            event_type="critical_approval_resolved",
            actor="runtime_authority",
            payload={
                "approval_id": approval_id, "outcome": "approved",
                "resolver": resolver.principal_id, "step_up_verified": step_up_verified,
                "reason": reason, "posture": posture,
            },
            session_id=session_id,
        )
        confirmation = CriticalConfirmation(
            approval_id=approval_id,
            confirmed_by=resolver.principal_id,
            step_up_verified=step_up_verified,
        )
        from raiker.runtime.executors.tier1_approval import ApprovalExecutionRelay

        relay = ApprovalExecutionRelay(self.store.paths.workspace_root, self.store)
        relay_action = GovernedAction(
            action_id=new_id("act_"),
            principal_id=resolver.principal_id,
            action_type="approval_execution_relay",
            tool_or_service_name="approval_execution_relay",
            arguments={"approval_id": approval_id},
            risk_level=RiskLevelValue.LOW,
            session_id=session_id,
            turn_id=approval.get("turn_id"),
            critical_confirmation=confirmation,
        )
        result = relay.execute(relay_action, resolver)
        if result.ok:
            return GovernedActionResult(
                action_id=approval_id, decision="allow",
                message="critical_action_executed", approval_id=approval_id,
            )
        return GovernedActionResult(
            action_id=approval_id, decision="deny",
            message=f"critical_execution_failed:{result.reason_code}", approval_id=approval_id,
        )

    def _approval_as_action(
        self, approval: dict[str, Any], session_id: str
    ) -> GovernedAction:
        """A minimal GovernedAction view of a stored approval, for posture capture."""
        return GovernedAction(
            action_id=str(approval.get("action_id", "")),
            principal_id="",
            action_type=str(approval.get("tool_name", "")),
            tool_or_service_name=str(approval.get("tool_name", "")),
            arguments={},
            risk_level=str(approval.get("risk_level", RiskLevelValue.LOW)),
            session_id=session_id,
        )

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

        # F6 (ZT-7) — production critical-risk classification. The in-code table
        # (raiker/runtime/authority/critical.py) is the single source of truth for
        # what "critical" means in production. A critical action is routed to the
        # human-confirmation floor here — before policy review and decision-mode
        # resolution — so that critical dominates every other outcome: its resting
        # state is deny, and only a live human may resolve it (no decision mode,
        # standing grant, or subagent can). An action's declared risk is also
        # honoured: an explicitly-CRITICAL action floors too.
        if action.action_type in {"checkpoint_restore", "checkpoint_restore_execution"}:
            checkpoint_id = str(action.arguments.get("checkpoint_id", ""))
            if checkpoint_id:
                try:
                    from raiker.checkpoints.service import CheckpointService

                    restore_plan = CheckpointService(self.store).compute_restore_plan(
                        checkpoint_id, restoring_principal_id=principal.principal_id
                    )
                    action = replace(
                        action,
                        arguments={
                            **action.arguments,
                            "touches_other_principal": bool(
                                restore_plan["touches_other_principal"]
                            ),
                        },
                        risk_level=RiskLevelValue.MEDIUM,
                    )
                except (OSError, ValueError):
                    action = replace(action, risk_level=RiskLevelValue.MEDIUM)

        critical_match = classify_critical(
            action.action_type, action.tool_or_service_name, action.arguments
        )
        is_critical = critical_match is not None or action.risk_level == RiskLevelValue.CRITICAL
        if is_critical:
            if critical_match is not None:
                self._event(
                    event_type="critical_action_classified",
                    actor="runtime_authority",
                    payload={
                        "action_id": action.action_id,
                        "action_type": action.action_type,
                        "criterion": critical_match.code,
                        "zt_ref": critical_match.zt_ref,
                        "detail": critical_match.detail,
                        "declared_risk": action.risk_level,
                    },
                    session_id=action.session_id,
                    turn_id=action.turn_id,
                )
            # F7 (ZT-7) — critical approval lifecycle. A live human's manual
            # confirmation (issued only by `resolve_critical_approval`, re-verified
            # against persisted state) is the *only* thing that lets a critical
            # action past the deny floor. Everything else — an AI principal, or a
            # human without a valid confirmation — parks the action and defaults to
            # deny until a human resolves it. No decision mode, standing grant,
            # scheduled routine, or subagent can reach this branch with a valid
            # confirmation, because confirmations require a human principal.
            if self._critical_confirmation_valid(action, principal):
                # Human-confirmed: fall through into normal governance below so the
                # target still runs under its gate, policy review, and posture check
                # at execution time (execution-time re-verification).
                pass
            else:
                return self._park_critical_action(action, principal, critical_match)

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
        mode = (
            parse_decision_mode(action.decision_mode_override)
            if action.decision_mode_override is not None
            else self._resolve_decision_mode(cap_for_mode, principal.principal_id)
            if cap_for_mode
            else None
        )
        if mode == DecisionMode.DENY:
            return GovernedActionResult(
                action_id=action.action_id,
                decision="deny",
                policy_decision=decision,
                message="denied_by_decision_mode",
            )

        # Critical is already floored above (before policy review), so every
        # action from here on is sub-critical.
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

        # F3 (ZT-5) — scoped standing grant. Before parking an AI-proposed action
        # for approval, check for an active, non-expired, human-created grant that
        # covers this exact action shape at or above its (sub-critical) risk. A
        # match satisfies the approval requirement without a fresh prompt — this
        # is the "frictionless" mechanism. Critical actions can never reach here
        # (floored above), and grant ceilings are sub-critical by construction.
        grant_applied: dict[str, Any] | None = None
        if effective_needs_approval and principal.principal_type != PrincipalType.HUMAN:
            grant = self.find_matching_standing_grant(
                principal, action, action.risk_level
            )
            if grant is not None:
                grant_applied = grant
                effective_needs_approval = False

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

        # F1 (ZT-3) — capture the per-action posture snapshot once, so every
        # governed execution/failure event carries "who was in control, on what
        # session, how strongly authenticated, and by what decision path" as
        # metadata. The decision-mode / grant used is recorded alongside it.
        posture = self._capture_action_posture(
            principal, action, mode=mode, grant_applied=grant_applied
        )

        # F3 — a matching standing grant satisfied the approval requirement. Log
        # its use (with the grant id) before executing, so the audit trail shows
        # the grant that authorized this unprompted run.
        if grant_applied is not None:
            self.store.record_standing_grant_use(str(grant_applied["grant_id"]))
            self._event(
                event_type="standing_grant_applied",
                actor="runtime_authority",
                payload={
                    "grant_id": grant_applied["grant_id"],
                    "action_id": action.action_id,
                    "action_type": action.action_type,
                    "risk_level": action.risk_level,
                    "posture": posture,
                },
                session_id=action.session_id,
                turn_id=action.turn_id,
            )

        capability = CAPABILITY_GATE_MAP.get(action.action_type, action.action_type)
        executor = self.executor_registry.get(capability)
        if executor is not None:
            # B1 capture: snapshot the target file's pre-image *before* the
            # executor overwrites it, so the mutation is reversible. Best-effort
            # and fully isolated — a capture failure must never fail or block the
            # real mutation.
            pre_image, checkpoint_capture = self._snapshot_pre_image(
                capability, action.arguments
            )
            result = executor.execute(action, principal)
            if pre_image is not None and result.ok:
                checkpoint_capture = self._commit_pre_image(pre_image, action, principal)
            execution_artifacts = dict(result.artifacts)
            if checkpoint_capture is not None and result.ok:
                execution_artifacts["checkpoint_capture"] = checkpoint_capture
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
                    "artifacts": execution_artifacts,
                    "posture": posture,
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
                artifacts=execution_artifacts,
                transient=dict(result.transient),
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
