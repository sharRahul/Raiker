from __future__ import annotations

import pytest

from raiker.control.dtos import (
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
            "requires_threat_model_ack": False,
            "requires_human_confirmation": False,
            "threat_model_ack_recorded": False,
            # GEP-04 — what this gate actually decides. A DTO that carried the
            # state and not this let the web app render every gate as a switch
            # that governs its capability, and for fifteen of them it did not.
            "gate_reality": "own_gate",
            "governance_note": "",
            # BUG-239 — how the *enforcing* path reads an empty gate table, and
            # what it would answer for this principal right now. Reported beside
            # `state` so a surface cannot describe a capability as off when the
            # runtime would run it.
            "unset_resolution": "off",
            "enforced_enabled": False,
            # BUG-293 — what this would cost if it ran without the owner, and
            # what stands in the way. Empty on the DTO's own defaults, because
            # the record is looked up by the service: a capability with no real
            # executor has no cost to state, and an empty cell is the honest
            # answer rather than a missing one.
            "side_effect": "",
            "ungoverned_consequence": "",
            "authority_requirement": "",
            "network_boundary": "",
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
                    "requires_threat_model_ack": False,
                    "requires_human_confirmation": False,
                    "threat_model_ack_recorded": False,
                    "gate_reality": "own_gate",
                    "governance_note": "",
                    "unset_resolution": "off",
                    "enforced_enabled": False,
                    # BUG-293 — empty on the DTO's own defaults, as above: the
                    # record is looked up by the service, and a capability with
                    # no real executor has no cost to state.
                    "side_effect": "",
                    "ungoverned_consequence": "",
                    "authority_requirement": "",
                    "network_boundary": "",
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
