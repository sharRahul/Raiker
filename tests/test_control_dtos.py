from __future__ import annotations

import pytest

from raiker.control.dtos import (
    REASON_AI_CANNOT_APPROVE_OWN_ACTION,
    REASON_AI_CANNOT_GRANT_ROLES,
    REASON_AI_CANNOT_MANAGE_RUNTIME_GATES,
    REASON_AI_ENABLE_RUNTIME_GATE,
    REASON_APPROVAL_REQUIRED,
    REASON_CANNOT_ASSIGN_HUMAN_ROLE_TO_AI,
    REASON_CAPABILITY_REQUIRES_ACTIVATION_TASK,
    REASON_CRITICAL_REQUIRES_HUMAN,
    REASON_DENIED_BY_POLICY,
    REASON_DISABLED_BY_CAPABILITY_GATE,
    REASON_DOMAIN_SCOPE_DENIED,
    REASON_INVALID_TARGET_STATE,
    REASON_NOT_RUNTIME_GATE_MANAGER,
    REASON_ONLY_GATE_MANAGER_CAN_ENABLE,
    REASON_ONLY_GATE_MANAGER_CAN_MANAGE,
    REASON_PRINCIPAL_EXPIRED,
    REASON_PRINCIPAL_NOT_ACTIVE,
    REASON_RISK_ACCEPTANCE_REQUIRED,
    REASON_RUNTIME_MODE_NOT_ACTIVATED,
    REASON_UNKNOWN_CAPABILITY,
    REASON_UNKNOWN_CAPABILITY_GATE,
    REASON_UNKNOWN_RUNTIME_MODE,
    CapabilityGateView,
    ControlPrincipalRef,
    ControlResult,
    RuntimeModeView,
    RuntimeReadinessView,
)

SECRET_PATTERNS = [
    "api_key", "api-key", "apiKey",
    "authorization", "Authorization",
    "secret", "password", "token",
    "private_key", "private-key",
    "raw_prompt", "raw_output",
    "file_content", "file-content",
]


def _check_no_secrets(obj: object, path: str = "") -> None:
    """Recursively check that no dict key or string value contains secret patterns."""
    if isinstance(obj, dict):
        for key, val in obj.items():
            _check_no_secrets(key, f"{path}.{key}" if path else key)
            _check_no_secrets(val, f"{path}.{key}" if path else key)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _check_no_secrets(item, f"{path}[{i}]")
    elif isinstance(obj, str):
        for pat in SECRET_PATTERNS:
            if pat in obj.lower():
                pytest.fail(f"Secret-like content at {path}: contains pattern '{pat}'")


class TestControlPrincipalRef:
    def test_to_dict_shape(self) -> None:
        dto = ControlPrincipalRef(
            principal_id="p_001",
            display_name="Test Owner",
            principal_type="human",
            role_ids=("owner", "runtime_gate_manager"),
            is_authorized_gate_manager=True,
        )
        d = dto.to_dict()
        assert d == {
            "principal_id": "p_001",
            "display_name": "Test Owner",
            "principal_type": "human",
            "role_ids": ["owner", "runtime_gate_manager"],
            "is_authorized_gate_manager": True,
        }

    def test_to_dict_no_secrets(self) -> None:
        dto = ControlPrincipalRef(
            principal_id="p_001",
            display_name="Owner",
            principal_type="human",
        )
        _check_no_secrets(dto.to_dict())

    def test_defaults(self) -> None:
        dto = ControlPrincipalRef(principal_id="p_001", display_name="X", principal_type="human")
        assert dto.role_ids == ()
        assert dto.is_authorized_gate_manager is False


class TestCapabilityGateView:
    def test_to_dict_shape(self) -> None:
        dto = CapabilityGateView(
            capability="admin_mutation",
            phase=5,
            state="disabled",
            default_state="disabled",
            runtime_enabled=False,
            allowed_transitions=("disabled", "enabled_policy_gated"),
            can_current_principal_change=True,
            blocked_reason_code=None,
            readiness={"policy_ready": True, "contract_ready": False},
            decision_mode="ask",
        )
        d = dto.to_dict()
        assert d == {
            "capability": "admin_mutation",
            "phase": 5,
            "state": "disabled",
            "default_state": "disabled",
            "source": "unknown",
            "runtime_enabled": False,
            "allowed_transitions": ["disabled", "enabled_policy_gated"],
            "can_current_principal_change": True,
            "blocked_reason_code": None,
            "readiness": {"policy_ready": True, "contract_ready": False},
            "decision_mode": "ask",
        }

    def test_to_dict_no_secrets(self) -> None:
        dto = CapabilityGateView(
            capability="shell_execution",
            phase=5,
            state="disabled",
            default_state="disabled",
        )
        _check_no_secrets(dto.to_dict())

    def test_defaults(self) -> None:
        dto = CapabilityGateView(capability="x", phase=3, state="disabled", default_state="disabled")
        assert dto.source == "unknown"
        assert dto.runtime_enabled is False
        assert dto.allowed_transitions == ()
        assert dto.can_current_principal_change is False
        assert dto.blocked_reason_code is None
        assert dto.readiness == {}


class TestRuntimeModeView:
    def test_to_dict_shape(self) -> None:
        dto = RuntimeModeView(
            mode_name="local_single_user_runtime",
            status="active",
            activated_by="p_001",
            activated_at="2026-06-21T12:00:00",
            allowed_modes=(
                "development_preview",
                "local_single_user_safe",
                "local_single_user_runtime",
            ),
        )
        d = dto.to_dict()
        assert d == {
            "mode_name": "local_single_user_runtime",
            "status": "active",
            "activated_by": "p_001",
            "activated_at": "2026-06-21T12:00:00",
            "reason": "",
            "allowed_modes": [
                "development_preview",
                "local_single_user_safe",
                "local_single_user_runtime",
            ],
        }

    def test_to_dict_no_secrets(self) -> None:
        dto = RuntimeModeView(mode_name="dev", status="active")
        _check_no_secrets(dto.to_dict())

    def test_defaults(self) -> None:
        dto = RuntimeModeView(mode_name="dev", status="inactive")
        assert dto.activated_by == ""
        assert dto.activated_at == ""
        assert dto.reason == ""
        assert dto.allowed_modes == ()


class TestControlResult:
    def test_to_dict_shape_ok(self) -> None:
        dto = ControlResult(ok=True, data={"mode_name": "local_single_user_runtime"})
        d = dto.to_dict()
        assert d == {
            "ok": True,
            "reason_code": None,
            "message_key": None,
            "data": {"mode_name": "local_single_user_runtime"},
        }

    def test_to_dict_shape_denied(self) -> None:
        dto = ControlResult(
            ok=False,
            reason_code="only_runtime_gate_manager_can_manage_gates",
            message_key="runtime.denied.not_gate_manager",
        )
        d = dto.to_dict()
        assert d == {
            "ok": False,
            "reason_code": "only_runtime_gate_manager_can_manage_gates",
            "message_key": "runtime.denied.not_gate_manager",
            "data": {},
        }

    def test_to_dict_no_secrets(self) -> None:
        dto = ControlResult(ok=True)
        _check_no_secrets(dto.to_dict())

    def test_defaults(self) -> None:
        dto = ControlResult(ok=False)
        assert dto.reason_code is None
        assert dto.message_key is None
        assert dto.data == {}


class TestRuntimeReadinessView:
    def test_to_dict_shape(self) -> None:
        mode = RuntimeModeView(mode_name="dev", status="active")
        gate = CapabilityGateView(
            capability="admin_mutation", phase=5, state="disabled", default_state="disabled",
        )
        dto = RuntimeReadinessView(
            mode=mode,
            gates=(gate,),
            summary={"owner_bootstrapped": True, "dangerous_caps_disabled": True},
        )
        d = dto.to_dict()
        assert d == {
            "mode": {
                "mode_name": "dev",
                "status": "active",
                "activated_by": "",
                "activated_at": "",
                "reason": "",
                "allowed_modes": [],
            },
            "gates": [
                {
                    "capability": "admin_mutation",
                    "phase": 5,
                    "state": "disabled",
                    "default_state": "disabled",
                    "source": "unknown",
                    "runtime_enabled": False,
                    "allowed_transitions": [],
                    "can_current_principal_change": False,
                    "blocked_reason_code": None,
                    "readiness": {},
                    "decision_mode": "ask",
                },
            ],
            "summary": {"owner_bootstrapped": True, "dangerous_caps_disabled": True},
        }

    def test_to_dict_no_secrets(self) -> None:
        mode = RuntimeModeView(mode_name="dev", status="active")
        gate = CapabilityGateView(
            capability="x", phase=3, state="disabled", default_state="disabled",
        )
        dto = RuntimeReadinessView(mode=mode, gates=(gate,), summary={"ok": True})
        _check_no_secrets(dto.to_dict())

    def test_defaults(self) -> None:
        mode = RuntimeModeView(mode_name="dev", status="active")
        dto = RuntimeReadinessView(mode=mode)
        assert dto.gates == ()
        assert dto.summary == {}


class TestReasonCodeConstants:
    def test_values_match_authority_strings(self) -> None:
        assert REASON_NOT_RUNTIME_GATE_MANAGER == "not_runtime_gate_manager"
        assert REASON_ONLY_GATE_MANAGER_CAN_MANAGE == "only_runtime_gate_manager_can_manage_gates"
        assert REASON_ONLY_GATE_MANAGER_CAN_ENABLE == "only_runtime_gate_manager_can_enable_gates"
        assert REASON_AI_CANNOT_MANAGE_RUNTIME_GATES == "ai_cannot_manage_runtime_gates"
        assert REASON_AI_ENABLE_RUNTIME_GATE == "ai_cannot_enable_runtime_gate"
        assert REASON_DISABLED_BY_CAPABILITY_GATE == "disabled_by_capability_gate"
        assert REASON_UNKNOWN_CAPABILITY_GATE == "unknown_capability_gate"
        assert REASON_UNKNOWN_CAPABILITY == "unknown_capability"
        assert REASON_INVALID_TARGET_STATE == "invalid_target_state"
        assert REASON_RUNTIME_MODE_NOT_ACTIVATED == "runtime_mode_not_activated"
        assert REASON_CAPABILITY_REQUIRES_ACTIVATION_TASK == "capability_requires_activation_task"
        assert REASON_UNKNOWN_RUNTIME_MODE == "unknown_runtime_mode"
        assert REASON_PRINCIPAL_NOT_ACTIVE == "principal_not_active"
        assert REASON_PRINCIPAL_EXPIRED == "principal_expired"
        assert REASON_DOMAIN_SCOPE_DENIED == "domain_scope_denied"
        assert REASON_CANNOT_ASSIGN_HUMAN_ROLE_TO_AI == "cannot_assign_human_role_to_ai"
        assert REASON_AI_CANNOT_APPROVE_OWN_ACTION == "ai_cannot_approve_own_action"
        assert REASON_AI_CANNOT_GRANT_ROLES == "ai_cannot_grant_roles"
        assert REASON_CRITICAL_REQUIRES_HUMAN == "critical_action_requires_human_confirmation"
        assert REASON_DENIED_BY_POLICY == "denied_by_policy"
        assert REASON_APPROVAL_REQUIRED == "approval_required"
        assert REASON_RISK_ACCEPTANCE_REQUIRED == "risk_acceptance_required"

    def test_no_secret_patterns_in_constant_values(self) -> None:
        import raiker.control.dtos as dtos

        for name in dir(dtos):
            val = getattr(dtos, name)
            if name.startswith("REASON_") and isinstance(val, str):
                for pat in SECRET_PATTERNS:
                    if pat in val.lower():
                        pytest.fail(f"{name} value contains secret pattern '{pat}': {val}")

    def test_constants_are_exported(self) -> None:
        import raiker.control

        assert raiker.control.REASON_NOT_RUNTIME_GATE_MANAGER == "not_runtime_gate_manager"
        assert raiker.control.REASON_ONLY_GATE_MANAGER_CAN_MANAGE == "only_runtime_gate_manager_can_manage_gates"
        assert raiker.control.REASON_ONLY_GATE_MANAGER_CAN_ENABLE == "only_runtime_gate_manager_can_enable_gates"
        assert raiker.control.REASON_AI_CANNOT_MANAGE_RUNTIME_GATES == "ai_cannot_manage_runtime_gates"
        assert raiker.control.REASON_AI_ENABLE_RUNTIME_GATE == "ai_cannot_enable_runtime_gate"
