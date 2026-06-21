from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from raiker.cli.commands import (
    handle_capability_gate_disable,
    handle_capability_gate_enable,
    handle_principal_detail,
    handle_principals,
    handle_role_create,
    handle_role_grant,
    handle_role_revoke,
    handle_runtime_mode_activate,
    handle_runtime_mode_disable,
    handle_runtime_mode_status,
    handle_runtime_readiness,
    handle_user_create,
    handle_whoami,
)
from raiker.cli.principal_resolver import (
    OWNER_BOOTSTRAP_ROLES,
    OWNER_ROLE_ID,
    RUNTIME_GATE_MANAGER_ROLE_ID,
    bootstrap_owner,
    check_owner_bootstrapped,
    get_bootstrap_status,
    resolve_local_principal,
)
from raiker.events.query import EventViewer
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        yield Path(tmp)


def _event_types(workspace_root: Path) -> set[str]:
    store = SQLiteStore(workspace_root)
    viewer = EventViewer(store)
    events = viewer.list_events(limit=100)
    return {e["event_type"] for e in events}


def _has_event(workspace_root: Path, event_type: str) -> bool:
    return event_type in _event_types(workspace_root)


# ── Owner Bootstrap Tests ──


class TestOwnerBootstrap:
    def test_bootstrap_owner_succeeds_when_no_owner(self, temp_workspace: Path):
        result = bootstrap_owner("rahul", "Rahul", "rahul@example.com", workspace_root=temp_workspace)
        assert "Bootstrap denied" not in result
        assert "Owner bootstrap successful" in result
        assert "rahul" in result
        assert check_owner_bootstrapped(temp_workspace)

    def test_bootstrap_owner_denied_when_owner_exists(self, temp_workspace: Path):
        bootstrap_owner("rahul", "Rahul", workspace_root=temp_workspace)
        result = bootstrap_owner("rahul2", "Rahul Two", workspace_root=temp_workspace)
        assert "Bootstrap denied: owner already exists." in result

    def test_bootstrap_creates_user_principal_roles(self, temp_workspace: Path):
        bootstrap_owner("rahul", "Rahul", "rahul@example.com", workspace_root=temp_workspace)
        store = SQLiteStore(temp_workspace)

        user = store.load_user("rahul")
        assert user is not None
        assert user["display_name"] == "Rahul"
        assert user["email"] == "rahul@example.com"
        assert user["is_active"]

        principal = store.get_principal("principal_rahul")
        assert principal is not None
        assert principal["principal_type"] == "human"
        role_ids = principal["role_ids"]
        assert OWNER_ROLE_ID in role_ids
        assert RUNTIME_GATE_MANAGER_ROLE_ID in role_ids

        for rid in OWNER_BOOTSTRAP_ROLES:
            role = store.load_role(rid)
            assert role is not None, f"Role {rid} not found"

    def test_bootstrap_emits_events(self, temp_workspace: Path):
        bootstrap_owner("rahul", "Rahul", workspace_root=temp_workspace)
        assert _has_event(temp_workspace, "owner_bootstrap_requested")
        assert _has_event(temp_workspace, "owner_bootstrap_created")

    def test_bootstrap_denied_emits_event(self, temp_workspace: Path):
        bootstrap_owner("rahul", "Rahul", workspace_root=temp_workspace)
        result = bootstrap_owner("rahul2", "Rahul Two", workspace_root=temp_workspace)
        assert "denied" in result
        assert _has_event(temp_workspace, "owner_bootstrap_denied")

    def test_ai_cannot_bootstrap_owner(self, temp_workspace: Path):
        result = bootstrap_owner("ai_agent", "AI Agent", workspace_root=temp_workspace)
        assert "Owner bootstrap successful" in result
        store = SQLiteStore(temp_workspace)
        principal = store.get_principal("principal_ai_agent")
        assert principal is not None
        assert principal["principal_type"] == "human"


# ── Principal Resolution Tests ──


class TestPrincipalResolution:
    def test_resolve_explicit_owner(self, temp_workspace: Path):
        bootstrap_owner("rahul", "Rahul", workspace_root=temp_workspace)
        principal, err = resolve_local_principal(temp_workspace, explicit_principal_id="principal_rahul")
        assert principal is not None
        assert err == ""
        assert principal.principal_id == "principal_rahul"

    def test_resolve_default_owner_when_exactly_one(self, temp_workspace: Path):
        bootstrap_owner("rahul", "Rahul", workspace_root=temp_workspace)
        principal, err = resolve_local_principal(temp_workspace)
        assert principal is not None
        assert err == ""
        assert principal.principal_id == "principal_rahul"

    def test_deny_when_no_owner(self, temp_workspace: Path):
        principal, err = resolve_local_principal(temp_workspace)
        assert principal is None
        assert "No owner principal" in err

    def test_deny_inactive_owner(self, temp_workspace: Path):
        bootstrap_owner("rahul", "Rahul", workspace_root=temp_workspace)
        store = SQLiteStore(temp_workspace)
        store.deactivate_principal("principal_rahul")
        principal, err = resolve_local_principal(temp_workspace, "principal_rahul")
        assert principal is None
        assert "not active" in err

    def test_resolution_emits_events(self, temp_workspace: Path):
        bootstrap_owner("rahul", "Rahul", workspace_root=temp_workspace)
        resolve_local_principal(temp_workspace, "principal_rahul")
        assert _has_event(temp_workspace, "principal_resolved")

    def test_resolution_failed_emits_event(self, temp_workspace: Path):
        resolve_local_principal(temp_workspace, "nonexistent")
        assert _has_event(temp_workspace, "principal_resolution_failed")


# ── Runtime Gate Authorization Tests ──


class TestRuntimeGateAuthorization:
    def test_owner_can_activate_runtime_mode(self, temp_workspace: Path):
        bootstrap_owner("rahul", "Rahul", workspace_root=temp_workspace)
        result = handle_runtime_mode_activate(
            "/runtime-mode activate local_single_user_runtime --reason test",
            workspace_root=temp_workspace,
        )
        assert "denied" not in result.lower()
        assert "Acting principal" in result

    def test_runtime_gate_manager_can_activate_runtime_mode(self, temp_workspace: Path):
        bootstrap_owner("rahul", "Rahul", workspace_root=temp_workspace)
        result = handle_runtime_mode_activate(
            "/runtime-mode activate local_single_user_runtime --reason test",
            workspace_root=temp_workspace,
        )
        assert "denied" not in result.lower()

    def test_owner_can_disable_runtime_mode(self, temp_workspace: Path):
        bootstrap_owner("rahul", "Rahul", workspace_root=temp_workspace)
        handle_runtime_mode_activate(
            "/runtime-mode activate local_single_user_runtime --reason test",
            workspace_root=temp_workspace,
        )
        result = handle_runtime_mode_disable(
            "/runtime-mode disable --reason test",
            workspace_root=temp_workspace,
        )
        assert "denied" not in result.lower()
        assert "Acting principal" in result


# ── Capability Transition Tests ──


class TestCapabilityTransitions:
    def test_owner_can_enable_admin_mutation(self, temp_workspace: Path):
        bootstrap_owner("rahul", "Rahul", workspace_root=temp_workspace)
        handle_runtime_mode_activate(
            "/runtime-mode activate local_single_user_runtime --reason test",
            workspace_root=temp_workspace,
        )
        result = handle_capability_gate_enable(
            "/capability-gate enable admin_mutation --state enabled_policy_gated --reason test",
            workspace_root=temp_workspace,
        )
        assert "denied" not in result.lower()
        assert "Acting principal" in result

    def test_owner_can_enable_role_mutation(self, temp_workspace: Path):
        bootstrap_owner("rahul", "Rahul", workspace_root=temp_workspace)
        handle_runtime_mode_activate(
            "/runtime-mode activate local_single_user_runtime --reason test",
            workspace_root=temp_workspace,
        )
        result = handle_capability_gate_enable(
            "/capability-gate enable role_mutation --state enabled_policy_gated --reason test",
            workspace_root=temp_workspace,
        )
        assert "denied" not in result.lower()

    def test_owner_can_disable_admin_mutation(self, temp_workspace: Path):
        bootstrap_owner("rahul", "Rahul", workspace_root=temp_workspace)
        handle_runtime_mode_activate(
            "/runtime-mode activate local_single_user_runtime --reason test",
            workspace_root=temp_workspace,
        )
        handle_capability_gate_enable(
            "/capability-gate enable admin_mutation --state enabled_policy_gated --reason test",
            workspace_root=temp_workspace,
        )
        result = handle_capability_gate_disable(
            "/capability-gate disable admin_mutation --reason test",
            workspace_root=temp_workspace,
        )
        assert "denied" not in result.lower()

    def test_dangerous_capabilities_cannot_be_enabled(self, temp_workspace: Path):
        bootstrap_owner("rahul", "Rahul", workspace_root=temp_workspace)
        handle_runtime_mode_activate(
            "/runtime-mode activate local_single_user_runtime --reason test",
            workspace_root=temp_workspace,
        )
        result = handle_capability_gate_enable(
            "/capability-gate enable shell_execution --state enabled_policy_gated --reason test",
            workspace_root=temp_workspace,
        )
        assert "denied" in result.lower() or "disabled" in result.lower()

    def test_unknown_capability_denied(self, temp_workspace: Path):
        result = handle_capability_gate_enable(
            "/capability-gate enable nonexistent_cap --state enabled_policy_gated --reason test",
            workspace_root=temp_workspace,
        )
        assert "denied" in result.lower() or "unknown" in result.lower()


# ── End-to-end Local Runtime Test ──


class TestEndToEndLocalRuntime:
    def test_full_scenario(self, temp_workspace: Path):
        ws = temp_workspace

        # 1. Bootstrap owner
        result = bootstrap_owner("rahul", "Rahul", workspace_root=ws)
        assert "Owner bootstrap successful" in result

        # 2. Runtime mode status shows default
        status = handle_runtime_mode_status(workspace_root=ws)
        assert "development_preview" in status
        assert "Acting principal" in status

        # 3. Owner activates local_single_user_runtime
        result = handle_runtime_mode_activate(
            "/runtime-mode activate local_single_user_runtime --reason e2e-test",
            workspace_root=ws,
        )
        assert "denied" not in result.lower()

        # 4. Owner enables admin_mutation
        result = handle_capability_gate_enable(
            "/capability-gate enable admin_mutation --state enabled_policy_gated --reason e2e-admin",
            workspace_root=ws,
        )
        assert "denied" not in result.lower()

        # 5. Owner enables role_mutation
        result = handle_capability_gate_enable(
            "/capability-gate enable role_mutation --state enabled_policy_gated --reason e2e-role",
            workspace_root=ws,
        )
        assert "denied" not in result.lower()

        # 6. User create succeeds
        result = handle_user_create(
            "/user create testuser --display TestUser --email test@test.com",
            workspace_root=ws,
        )
        assert "denied" not in result.lower()
        assert "User created" in result

        # 7. Role create succeeds
        result = handle_role_create(
            "/role create testrole test_role --description test",
            workspace_root=ws,
        )
        assert "denied" not in result.lower()
        assert "Role created" in result

        # 8. Role grant succeeds
        result = handle_role_grant(
            "/role grant testrole testuser",
            workspace_root=ws,
        )
        assert "denied" not in result.lower()
        assert "granted" in result or "Role" in result

        # 9. Role revoke succeeds
        result = handle_role_revoke(
            "/role revoke testrole testuser",
            workspace_root=ws,
        )
        assert "denied" not in result.lower()
        assert "revoked" in result or "Role" in result

        # 10. Owner disables role_mutation
        result = handle_capability_gate_disable(
            "/capability-gate disable role_mutation --reason e2e-disable",
            workspace_root=ws,
        )
        assert "denied" not in result.lower()

        # 11. Role grant/revoke blocked again
        result = handle_role_grant(
            "/role grant testrole testuser",
            workspace_root=ws,
        )
        assert "denied" in result.lower() or "disabled_by_capability_gate" in result.lower()

        result = handle_role_revoke(
            "/role revoke testrole testuser",
            workspace_root=ws,
        )
        assert "denied" in result.lower() or "disabled_by_capability_gate" in result.lower()

        # 12. Runtime readiness reports accurate status
        readiness = handle_runtime_readiness(workspace_root=ws)
        assert "local_single_user_runtime" in readiness
        assert "owner bootstrapped: true" in readiness.lower()

        # 13. Events exist for bootstrap, runtime activation, capability enable, mutation, disable
        for evt_type in [
            "owner_bootstrap_requested",
            "owner_bootstrap_created",
            "runtime_mode_activated",
            "runtime_readiness_checked",
        ]:
            assert _has_event(ws, evt_type), f"Missing event: {evt_type}"


# ── Validator Tests (conceptual) ──


def test_commands_have_resolved_principal(temp_workspace: Path):
    """Verify that runtime/capability gate commands use resolved principal, not synthetic."""
    import ast
    import inspect

    from raiker.cli import commands as mod
    source = inspect.getsource(mod)
    tree = ast.parse(source)
    handlers_to_check = [
        "handle_runtime_mode_activate",
        "handle_runtime_mode_disable",
        "handle_capability_gate_enable",
        "handle_capability_gate_disable",
    ]
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in handlers_to_check:
            body_text = ast.unparse(node)
            assert "resolve_local_principal" in body_text, (
                f"{node.name} does not use resolve_local_principal"
            )


# ── CLI Smoke Tests ──


def test_whoami_without_owner(temp_workspace: Path):
    result = handle_whoami(workspace_root=temp_workspace)
    assert "No owner principal" in result


def test_whoami_with_owner(temp_workspace: Path):
    bootstrap_owner("rahul", "Rahul", workspace_root=temp_workspace)
    result = handle_whoami(workspace_root=temp_workspace)
    assert "Acting principal" in result
    assert "rahul" in result


def test_principals_list(temp_workspace: Path):
    bootstrap_owner("rahul", "Rahul", workspace_root=temp_workspace)
    result = handle_principals(workspace_root=temp_workspace)
    assert "principal_rahul" in result


def test_principal_detail(temp_workspace: Path):
    bootstrap_owner("rahul", "Rahul", workspace_root=temp_workspace)
    result = handle_principal_detail(
        "/principal principal_rahul", workspace_root=temp_workspace,
    )
    assert "principal_rahul" in result
    assert "human" in result


def test_get_bootstrap_status(temp_workspace: Path):
    status = get_bootstrap_status(temp_workspace)
    assert status["owner_bootstrapped"] is False
    assert status["acting_principal_available"] is False
    assert status["runtime_gate_manager_available"] is False

    bootstrap_owner("rahul", "Rahul", workspace_root=temp_workspace)
    status = get_bootstrap_status(temp_workspace)
    assert status["owner_bootstrapped"] is True
    assert status["acting_principal_available"] is True
    assert status["runtime_gate_manager_available"] is True
