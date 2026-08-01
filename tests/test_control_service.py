from __future__ import annotations

from pathlib import Path

import pytest

from raiker.control.dtos import (
    CapabilityGateView,
    ControlPrincipalRef,
    RuntimeModeView,
    RuntimeReadinessView,
)
from raiker.control.service import RuntimeControlService
from raiker.events.writer import EventLogWriter
from raiker.phase_gates import ALL_CAPABILITIES, CapabilityState, default_capability_gates
from raiker.runtime.authority.models import Principal, PrincipalType
from raiker.runtime.authority.router import RuntimeAuthority
from raiker.storage.sqlite import SQLiteStore


def _insert_gov_acks(root: Path) -> None:
    from raiker.contracts.ids import utc_now
    store = SQLiteStore(root)
    with store.connect() as connection:
        for cap in ("admin_mutation", "policy_mutation", "role_mutation"):
            connection.execute(
                "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref) VALUES (?, ?, ?, ?)",
                (cap, "test_fixture", utc_now(), "test_doc"),
            )


# ── fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def service(tmp_path: Path) -> RuntimeControlService:
    _insert_gov_acks(tmp_path)
    return RuntimeControlService(tmp_path)


@pytest.fixture
def authority(tmp_path: Path) -> RuntimeAuthority:
    store = SQLiteStore(tmp_path)
    writer = EventLogWriter(store)
    return RuntimeAuthority(store, writer)


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    return SQLiteStore(tmp_path)


@pytest.fixture
def owner_principal(store: SQLiteStore) -> Principal:
    """Create a persisted human owner principal with runtime_gate_manager role."""
    from raiker.contracts.ids import utc_now
    from raiker.contracts.models import Role
    now = utc_now()
    store.insert_role(Role(
        role_id="rl_owner", name="owner",
        description="", is_system_role=True, created_at=now,
    ))
    store.insert_role(Role(
        role_id="rl_gm", name="runtime_gate_manager",
        description="", is_system_role=True, created_at=now,
    ))
    principal = Principal(
        principal_id="p_owner",
        principal_type=PrincipalType.HUMAN,
        display_name="Owner",
        role_ids=("rl_owner", "rl_gm"),
        is_active=True,
    )
    store.insert_principal(
        principal_id="p_owner",
        principal_type=PrincipalType.HUMAN.value,
        display_name="Owner",
        role_ids=("rl_owner", "rl_gm"),
        max_runtime_mode="local_single_user_runtime",
        is_active=True,
    )
    return principal


# ── resolve_principal ─────────────────────────────────────────────────────


class TestResolvePrincipal:
    def test_no_owner_returns_none(self, service: RuntimeControlService) -> None:
        ref, err = service.resolve_principal()
        assert ref is None
        assert err is not None

    def test_owner_resolved(self, service: RuntimeControlService, owner_principal: Principal) -> None:
        ref, err = service.resolve_principal()
        assert err is None
        assert ref is not None
        assert isinstance(ref, ControlPrincipalRef)
        assert ref.principal_id == owner_principal.principal_id
        assert ref.display_name == owner_principal.display_name
        assert ref.principal_type == PrincipalType.HUMAN.value
        assert ref.is_authorized_gate_manager is True  # has runtime_gate_manager role

    def test_explicit_principal_resolved(self, service: RuntimeControlService, owner_principal: Principal) -> None:
        ref, err = service.resolve_principal(owner_principal.principal_id)
        assert err is None
        assert ref is not None
        assert ref.principal_id == owner_principal.principal_id

    def test_unknown_principal_returns_none(self, service: RuntimeControlService) -> None:
        ref, err = service.resolve_principal("nonexistent")
        assert ref is None
        assert err is not None


# ── get_runtime_mode ──────────────────────────────────────────────────────


class TestGetRuntimeMode:
    def test_default_mode(self, service: RuntimeControlService) -> None:
        """A fresh workspace reports the one runtime, active, with nothing to pick."""
        view = service.get_runtime_mode()
        assert isinstance(view, RuntimeModeView)
        assert view.mode_name == "raiker_runtime"
        assert view.status == "active"
        assert view.activated_by == "system"
        assert view.allowed_modes == ("raiker_runtime",)

    def test_mode_matches_authority(self, service: RuntimeControlService, authority: RuntimeAuthority) -> None:
        view = service.get_runtime_mode()
        raw = authority.get_runtime_mode()
        assert view.mode_name == raw["mode_name"]
        assert view.status == raw["status"]

    def test_allowed_modes_is_the_single_runtime(
        self, service: RuntimeControlService,
    ) -> None:
        """There is one runtime, so the list a client renders holds one entry."""
        view = service.get_runtime_mode()
        assert view.allowed_modes == ("raiker_runtime",)

    def test_to_dict_no_secrets(self, service: RuntimeControlService) -> None:
        view = service.get_runtime_mode()
        d = view.to_dict()
        assert "mode_name" in d
        assert "status" in d
        assert "activated_by" in d
        assert "activated_at" in d
        assert "allowed_modes" in d


# ── list_capability_gates ─────────────────────────────────────────────────


class TestListCapabilityGates:
    def test_returns_all_capabilities(self, service: RuntimeControlService) -> None:
        views = service.list_capability_gates()
        assert len(views) == len(ALL_CAPABILITIES)
        returned_caps = {v.capability for v in views}
        assert returned_caps == ALL_CAPABILITIES

    def test_each_view_has_expected_fields(self, service: RuntimeControlService) -> None:
        views = service.list_capability_gates()
        for v in views:
            assert isinstance(v, CapabilityGateView)
            assert v.capability in ALL_CAPABILITIES
            assert v.state in {s.value for s in CapabilityState}
            assert v.default_state in {s.value for s in CapabilityState}
            assert v.phase in (1, 2, 3, 4, 5, 6)
            assert isinstance(v.allowed_transitions, tuple)
            assert isinstance(v.can_current_principal_change, bool)
            assert "policy_ready" in v.readiness
            assert "contract_ready" in v.readiness

    def test_state_matches_authority(self, service: RuntimeControlService, authority: RuntimeAuthority) -> None:
        views = service.list_capability_gates()
        for v in views:
            raw = authority.get_effective_capability_gate(v.capability)
            assert v.state == raw["state"]

    def test_runtime_enabled_true_for_integrated_false_otherwise(
        self, service: RuntimeControlService
    ) -> None:
        from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES

        views = {v.capability: v for v in service.list_capability_gates()}
        # Integrated (real-executor) capabilities ship enabled; everything else stays disabled.
        for cap, v in views.items():
            assert v.runtime_enabled is (cap in REAL_EXECUTOR_CAPABILITIES)

    def test_can_current_principal_change_false_when_no_principal(
        self, service: RuntimeControlService,
    ) -> None:
        views = service.list_capability_gates()
        for v in views:
            assert v.can_current_principal_change is False
            assert v.blocked_reason_code is None

    def test_executor_required_caps_exclude_enabled_transitions(
        self, service: RuntimeControlService,
    ) -> None:
        from raiker.runtime.authority.activation import get_activation_requirement, has_executor
        views = service.list_capability_gates()
        for v in views:
            req = get_activation_requirement(v.capability)
            # A capability that requires an executor but has none registered must
            # never offer an enabled transition.
            if req is not None and req.requires_executor and not has_executor(v.capability, service._registry):
                for state in ("enabled_runtime", "enabled_policy_gated"):
                    assert state not in v.allowed_transitions, (
                        f"{v.capability} should exclude {state} due to missing executor"
                    )


# ── get_capability_gate ───────────────────────────────────────────────────


class TestGetCapabilityGate:
    def test_known_capability(self, service: RuntimeControlService, authority: RuntimeAuthority) -> None:
        view = service.get_capability_gate("admin_mutation")
        assert view is not None
        assert isinstance(view, CapabilityGateView)
        raw = authority.get_effective_capability_gate("admin_mutation")
        assert view.state == raw["state"]
        assert view.capability == "admin_mutation"

    def test_unknown_capability_returns_none(self, service: RuntimeControlService) -> None:
        view = service.get_capability_gate("nonexistent_cap")
        assert view is None

    def test_fields_match_default_gate(self, service: RuntimeControlService) -> None:
        view = service.get_capability_gate("admin_mutation")
        assert view is not None
        gates = default_capability_gates()
        default = gates.get("admin_mutation")
        assert default is not None
        assert view.phase == default.phase
        assert view.default_state == default.state.value
        assert view.readiness["policy_ready"] == default.policy_ready


# ── get_runtime_readiness ─────────────────────────────────────────────────


class TestGetRuntimeReadiness:
    def test_returns_runtime_readiness_view(self, service: RuntimeControlService) -> None:
        view = service.get_runtime_readiness()
        assert isinstance(view, RuntimeReadinessView)
        assert isinstance(view.mode, RuntimeModeView)

    def test_summary_contains_expected_keys(self, service: RuntimeControlService) -> None:
        view = service.get_runtime_readiness()
        assert "owner_bootstrapped" in view.summary
        assert "acting_principal_available" in view.summary
        assert "runtime_gate_manager_available" in view.summary
        assert "dangerous_capabilities_disabled" in view.summary
        assert "production_ready_local_single_user_runtime" in view.summary

    def test_dangerous_caps_disabled_true_by_default(self, service: RuntimeControlService) -> None:
        view = service.get_runtime_readiness()
        assert view.summary["dangerous_capabilities_disabled"] is True

    def test_owner_not_bootstrapped_by_default(self, service: RuntimeControlService) -> None:
        view = service.get_runtime_readiness()
        assert view.summary["owner_bootstrapped"] is False

    def test_gates_count_matches_all_capabilities(self, service: RuntimeControlService) -> None:
        view = service.get_runtime_readiness()
        assert len(view.gates) == len(ALL_CAPABILITIES)

    def test_to_dict_no_secrets(self, service: RuntimeControlService) -> None:
        view = service.get_runtime_readiness()
        d = view.to_dict()
        assert "mode" in d
        assert "gates" in d
        assert "summary" in d


# ── activate_runtime_mode ──────────────────────────────────────────────────


class TestActivateRuntimeMode:
    def test_owner_can_activate(self, service: RuntimeControlService, owner_principal: Principal) -> None:
        result = service.activate_runtime_mode("local_single_user_safe", None, "testing")
        assert result.ok is True
        assert result.reason_code is None

    def test_denied_when_no_owner(self, service: RuntimeControlService) -> None:
        result = service.activate_runtime_mode("local_single_user_safe", None, "")
        assert result.ok is False
        assert result.reason_code is not None

    def test_unknown_mode_denied(self, service: RuntimeControlService, owner_principal: Principal) -> None:
        result = service.activate_runtime_mode("nonexistent_mode", None, "")
        assert result.ok is False
        assert "unknown_runtime_mode" in (result.reason_code or "")

    def test_mode_persisted(self, service: RuntimeControlService, owner_principal: Principal) -> None:
        """A legacy mode name still activates, and resolves to the one runtime."""
        service.activate_runtime_mode("local_single_user_runtime", None, "enable")
        mode_view = service.get_runtime_mode()
        assert mode_view.mode_name == "raiker_runtime"
        assert mode_view.status == "active"

    def test_ai_principal_refused(self, service: RuntimeControlService, store: SQLiteStore) -> None:
        from raiker.contracts.ids import utc_now
        from raiker.contracts.models import Role
        now = utc_now()
        store.insert_role(Role(
            role_id="rl_ai", name="assistant",
            description="", is_system_role=True, created_at=now,
        ))
        store.insert_principal(
            principal_id="p_ai",
            principal_type="ai_agent",
            display_name="AI Agent",
            role_ids=("rl_ai",),
            is_active=True,
        )
        result = service.activate_runtime_mode("local_single_user_safe", "p_ai", "")
        assert result.ok is False
        assert result.reason_code is not None


# ── disable_runtime_mode ───────────────────────────────────────────────────


class TestDisableRuntimeMode:
    def test_owner_can_disable(self, service: RuntimeControlService, owner_principal: Principal) -> None:
        service.activate_runtime_mode("local_single_user_runtime", None, "")
        result = service.disable_runtime_mode(None, "done testing")
        assert result.ok is True

    def test_denied_when_no_owner(self, service: RuntimeControlService) -> None:
        result = service.disable_runtime_mode(None, "")
        assert result.ok is False
        assert result.reason_code is not None

    def test_disable_stops_the_runtime_rather_than_renaming_it(
        self, service: RuntimeControlService, owner_principal: Principal,
    ) -> None:
        """Disabling means the runtime stops accepting executions, not that it
        keeps running under a name that implies it is not."""
        service.activate_runtime_mode("local_single_user_safe", None, "")
        service.disable_runtime_mode(None, "revert")
        mode_view = service.get_runtime_mode()
        assert mode_view.mode_name == "raiker_runtime"
        assert mode_view.status == "disabled"

    def test_ai_principal_refused(self, service: RuntimeControlService, store: SQLiteStore) -> None:
        from raiker.contracts.ids import utc_now
        from raiker.contracts.models import Role
        now = utc_now()
        store.insert_role(Role(
            role_id="rl_ai", name="assistant",
            description="", is_system_role=True, created_at=now,
        ))
        store.insert_principal(
            principal_id="p_ai2",
            principal_type="ai_agent",
            display_name="AI Agent",
            role_ids=("rl_ai",),
            is_active=True,
        )
        result = service.disable_runtime_mode("p_ai2", "")
        assert result.ok is False


# ── set_capability_state ───────────────────────────────────────────────────


class TestSetCapabilityState:
    def test_owner_can_enable_admin_mutation(self, service: RuntimeControlService, owner_principal: Principal) -> None:
        result = service.set_capability_state("admin_mutation", "enabled_policy_gated", None, "testing")
        assert result.ok is True
        assert result.reason_code is None

    def test_state_persisted(self, service: RuntimeControlService, owner_principal: Principal) -> None:
        service.set_capability_state("admin_mutation", "enabled_policy_gated", None, "enable")
        view = service.get_capability_gate("admin_mutation")
        assert view is not None
        assert view.state == "enabled_policy_gated"

    def test_denied_when_no_owner(self, service: RuntimeControlService) -> None:
        result = service.set_capability_state("admin_mutation", "enabled_policy_gated", None, "")
        assert result.ok is False

    def test_unknown_capability_denied(self, service: RuntimeControlService, owner_principal: Principal) -> None:
        result = service.set_capability_state("nonexistent_cap", "disabled", None, "")
        assert result.ok is False
        assert "unknown_capability" in (result.reason_code or "")

    def test_invalid_target_state_denied(self, service: RuntimeControlService, owner_principal: Principal) -> None:
        result = service.set_capability_state("admin_mutation", "invalid_state", None, "")
        assert result.ok is False
        assert "invalid_target_state" in (result.reason_code or "")

    def test_enabled_runtime_needs_no_mode_selection(
        self, service: RuntimeControlService, owner_principal: Principal,
    ) -> None:
        """One runtime, active by default: nothing has to be selected first."""
        result = service.set_capability_state("admin_mutation", "enabled_runtime", None, "")
        assert result.ok is True

    def test_enabled_runtime_refused_while_the_runtime_is_disabled(
        self, service: RuntimeControlService, owner_principal: Principal,
    ) -> None:
        """The danger-zone switch is the one runtime-level refusal left."""
        service.disable_runtime_mode(None, "stop accepting work")
        result = service.set_capability_state("admin_mutation", "enabled_runtime", None, "")
        assert result.ok is False
        assert result.reason_code is not None and "runtime_mode_not_active" in result.reason_code

    def test_dangerous_cap_denied(self, service: RuntimeControlService, owner_principal: Principal) -> None:
        result = service.set_capability_state("shell_execution", "enabled_policy_gated", None, "")
        assert result.ok is False

    def test_ai_principal_refused(self, service: RuntimeControlService, store: SQLiteStore) -> None:
        from raiker.contracts.ids import utc_now
        from raiker.contracts.models import Role
        now = utc_now()
        store.insert_role(Role(
            role_id="rl_ai", name="assistant",
            description="", is_system_role=True, created_at=now,
        ))
        store.insert_principal(
            principal_id="p_ai3",
            principal_type="ai_agent",
            display_name="AI Agent",
            role_ids=("rl_ai",),
            is_active=True,
        )
        result = service.set_capability_state("admin_mutation", "enabled_policy_gated", "p_ai3", "")
        assert result.ok is False

    def test_reversible(self, service: RuntimeControlService, owner_principal: Principal) -> None:
        service.set_capability_state("admin_mutation", "enabled_policy_gated", None, "enable")
        service.set_capability_state("admin_mutation", "disabled", None, "disable")
        view = service.get_capability_gate("admin_mutation")
        assert view is not None
        assert view.state == "disabled"


# ── disable_capability ─────────────────────────────────────────────────────


class TestDisableCapability:
    def test_owner_can_disable(self, service: RuntimeControlService, owner_principal: Principal) -> None:
        service.set_capability_state("admin_mutation", "enabled_policy_gated", None, "enable")
        result = service.disable_capability("admin_mutation", None, "disable")
        assert result.ok is True

    def test_denied_when_no_owner(self, service: RuntimeControlService) -> None:
        result = service.disable_capability("admin_mutation", None, "")
        assert result.ok is False

    def test_unknown_capability_denied(self, service: RuntimeControlService, owner_principal: Principal) -> None:
        result = service.disable_capability("nonexistent_cap", None, "")
        assert result.ok is False
        assert "unknown_capability" in (result.reason_code or "")

    def test_disabled_state_persisted(self, service: RuntimeControlService, owner_principal: Principal) -> None:
        service.set_capability_state("admin_mutation", "enabled_policy_gated", None, "enable")
        service.disable_capability("admin_mutation", None, "off")
        view = service.get_capability_gate("admin_mutation")
        assert view is not None
        assert view.state == "disabled"

    def test_ai_principal_refused(self, service: RuntimeControlService, store: SQLiteStore) -> None:
        from raiker.contracts.ids import utc_now
        from raiker.contracts.models import Role
        now = utc_now()
        store.insert_role(Role(
            role_id="rl_ai", name="assistant",
            description="", is_system_role=True, created_at=now,
        ))
        store.insert_principal(
            principal_id="p_ai4",
            principal_type="ai_agent",
            display_name="AI Agent",
            role_ids=("rl_ai",),
            is_active=True,
        )
        result = service.disable_capability("admin_mutation", "p_ai4", "")
        assert result.ok is False
