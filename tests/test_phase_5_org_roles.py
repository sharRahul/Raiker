from __future__ import annotations

import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import (
    Role,
    ToolAction,
    User,
    UserRoleAssignment,
)
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def workspace() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        yield Path(d)


@pytest.fixture
def store(workspace: Path) -> SQLiteStore:
    return SQLiteStore(workspace)


@pytest.fixture
def engine(workspace: Path, store: SQLiteStore) -> PolicyEngine:
    return PolicyEngine(StaticPolicyConfig(workspace), store=store)


def _read_action(path: str = "README.md") -> ToolAction:
    return ToolAction(new_id("act_"), "read_file", {"path": path}, "medium", False)


def _shell_action() -> ToolAction:
    return ToolAction(new_id("act_"), "shell", {"command": "echo hi"}, "high", True)


# ── User CRUD ──


def test_create_user(store: SQLiteStore) -> None:
    now = utc_now()
    user = User(
        user_id="test_user_1",
        display_name="Test User",
        email="test@example.com",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    store.insert_user(user)
    loaded = store.load_user("test_user_1")
    assert loaded is not None
    assert loaded["display_name"] == "Test User"
    assert loaded["email"] == "test@example.com"


def test_list_users(store: SQLiteStore) -> None:
    now = utc_now()
    store.insert_user(User(user_id="u1", display_name="Alice", email=None, is_active=True, created_at=now, updated_at=now))
    store.insert_user(User(user_id="u2", display_name="Bob", email=None, is_active=True, created_at=now, updated_at=now))
    users = store.list_users()
    assert len(users) == 2
    ids = {u["user_id"] for u in users}
    assert ids == {"u1", "u2"}


def test_deactivate_user(store: SQLiteStore) -> None:
    now = utc_now()
    store.insert_user(User(user_id="u1", display_name="Test", email=None, is_active=True, created_at=now, updated_at=now))
    assert store.deactivate_user("u1") is True
    loaded = store.load_user("u1")
    assert loaded is not None
    assert loaded["is_active"] == 0
    assert store.deactivate_user("u1") is False


# ── Role CRUD ──


def test_create_role(store: SQLiteStore) -> None:
    now = utc_now()
    role = Role(role_id="viewer", name="viewer", description="Read-only access", is_system_role=True, created_at=now)
    store.insert_role(role)
    loaded = store.load_role("viewer")
    assert loaded is not None
    assert loaded["name"] == "viewer"


def test_list_roles(store: SQLiteStore) -> None:
    now = utc_now()
    store.insert_role(Role(role_id="r1", name="admin", description=None, is_system_role=True, created_at=now))
    store.insert_role(Role(role_id="r2", name="operator", description=None, is_system_role=False, created_at=now))
    roles = store.list_roles()
    assert len(roles) == 2


def test_delete_role(store: SQLiteStore) -> None:
    now = utc_now()
    store.insert_role(Role(role_id="custom", name="custom", description=None, is_system_role=False, created_at=now))
    assert store.delete_role("custom") is True
    assert store.delete_role("custom") is False


# ── User-Role Assignment ──


def test_assign_role_to_user(store: SQLiteStore) -> None:
    now = utc_now()
    store.insert_user(User(user_id="u1", display_name="Test", email=None, is_active=True, created_at=now, updated_at=now))
    store.insert_role(Role(role_id="admin", name="admin", description=None, is_system_role=True, created_at=now))
    assignment = UserRoleAssignment(
        assignment_id=new_id("ura_"),
        user_id="u1",
        role_id="admin",
        granted_at=now,
        granted_by="test",
    )
    store.insert_user_role_assignment(assignment)
    roles = store.list_user_roles("u1")
    assert len(roles) == 1
    assert roles[0]["role_name"] == "admin"


def test_revoke_user_role(store: SQLiteStore) -> None:
    now = utc_now()
    store.insert_user(User(user_id="u1", display_name="Test", email=None, is_active=True, created_at=now, updated_at=now))
    store.insert_role(Role(role_id="dev", name="developer", description=None, is_system_role=False, created_at=now))
    assignment = UserRoleAssignment(
        assignment_id=new_id("ura_"),
        user_id="u1",
        role_id="dev",
        granted_at=now,
        granted_by="test",
    )
    store.insert_user_role_assignment(assignment)
    assert len(store.list_user_roles("u1")) == 1
    assert store.delete_user_role_assignment(assignment.assignment_id) is True
    assert len(store.list_user_roles("u1")) == 0


# ── Session user binding ──


def test_create_session_with_user(store: SQLiteStore) -> None:
    now = utc_now()
    store.insert_user(User(user_id="u1", display_name="Test", email=None, is_active=True, created_at=now, updated_at=now))
    store.create_session(new_id("sess_"), str(store.paths.workspace_root), user_id="u1")
    sessions = store.list_sessions()
    assert any(s.get("user_id") == "u1" for s in sessions)


# ── PolicyEngine role-based checks ──


def test_unknown_user_denied(engine: PolicyEngine) -> None:
    decision = engine.review(_read_action(), user_id="nonexistent")
    assert decision.decision == "deny"
    assert any("unknown_user" in r for r in decision.reasons)


def test_inactive_user_denied(engine: PolicyEngine, store: SQLiteStore) -> None:
    now = utc_now()
    store.insert_user(User(user_id="inactive", display_name="Old", email=None, is_active=False, created_at=now, updated_at=now))
    decision = engine.review(_read_action(), user_id="inactive")
    assert decision.decision == "deny"
    assert any("user_not_active" in r for r in decision.reasons)


def test_active_user_allows_read(engine: PolicyEngine, store: SQLiteStore) -> None:
    now = utc_now()
    store.insert_user(User(user_id="active", display_name="Active", email=None, is_active=True, created_at=now, updated_at=now))
    decision = engine.review(_read_action(), user_id="active")
    assert decision.decision == "allow"


def test_active_user_still_needs_approval(engine: PolicyEngine, store: SQLiteStore) -> None:
    now = utc_now()
    store.insert_user(User(user_id="active", display_name="Active", email=None, is_active=True, created_at=now, updated_at=now))
    decision = engine.review(_shell_action(), user_id="active")
    assert decision.decision == "needs_approval"


def test_role_check_after_managed_deny(engine: PolicyEngine, store: SQLiteStore) -> None:
    """Managed deny still wins over user/role checks."""
    now = utc_now()
    store.insert_user(User(user_id="admin", display_name="Admin", email=None, is_active=True, created_at=now, updated_at=now))
    from raiker.contracts.models import ManagedPolicyRule
    store.insert_managed_policy(ManagedPolicyRule(
        rule_id=new_id("mng_"),
        effect="deny",
        tool_pattern="read_file",
        arguments_json=None,
        priority=100,
        enabled=True,
        reason="Block all reads",
        created_by="test",
        created_at=now,
        updated_at=now,
    ))
    decision = engine.review(_read_action(), user_id="admin")
    assert decision.decision == "deny"
    assert "managed_policy_denied" in decision.reasons


# ── Persistence ──


def test_users_persist_across_store_reopen(workspace: Path) -> None:
    store1 = SQLiteStore(workspace)
    now = utc_now()
    store1.insert_user(User(user_id="persist", display_name="Persist", email=None, is_active=True, created_at=now, updated_at=now))

    store2 = SQLiteStore(workspace)
    loaded = store2.load_user("persist")
    assert loaded is not None


def test_roles_persist_across_store_reopen(workspace: Path) -> None:
    store1 = SQLiteStore(workspace)
    store1.insert_role(Role(role_id="auditor", name="auditor", description=None, is_system_role=False, created_at=utc_now()))

    store2 = SQLiteStore(workspace)
    loaded = store2.load_role("auditor")
    assert loaded is not None


def test_user_role_assignments_persist(workspace: Path) -> None:
    store1 = SQLiteStore(workspace)
    now = utc_now()
    store1.insert_user(User(user_id="u1", display_name="U1", email=None, is_active=True, created_at=now, updated_at=now))
    store1.insert_role(Role(role_id="operator", name="operator", description=None, is_system_role=False, created_at=now))
    store1.insert_user_role_assignment(UserRoleAssignment(
        assignment_id=new_id("ura_"), user_id="u1", role_id="operator", granted_at=now, granted_by="test",
    ))

    store2 = SQLiteStore(workspace)
    roles = store2.list_user_roles("u1")
    assert len(roles) == 1
    assert roles[0]["role_name"] == "operator"
