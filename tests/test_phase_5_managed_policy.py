from __future__ import annotations

import json
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import ManagedPolicyRule, ToolAction
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def workspace() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        path = Path(d)
        (path / ".raiker").mkdir(parents=True, exist_ok=True)
        yield path


@pytest.fixture
def config(workspace: Path) -> StaticPolicyConfig:
    return StaticPolicyConfig(workspace)


@pytest.fixture
def store(workspace: Path) -> SQLiteStore:
    return SQLiteStore(workspace)


@pytest.fixture
def engine(config: StaticPolicyConfig, store: SQLiteStore) -> PolicyEngine:
    return PolicyEngine(config, store=store)


def _read_action(path: str = "README.md") -> ToolAction:
    return ToolAction(new_id("act_"), "read_file", {"path": path}, "medium", False)


def _shell_action(command: str = "echo hello") -> ToolAction:
    return ToolAction(new_id("act_"), "shell", {"command": command}, "high", True)


def _write_action(path: str = "test.txt") -> ToolAction:
    return ToolAction(new_id("act_"), "write_file", {"path": path}, "high", True)


def _memory_write_action() -> ToolAction:
    return ToolAction(new_id("act_"), "memory_write", {"text": "test"}, "medium", False)


def _managed_rule(
    effect: str = "deny",
    tool_pattern: str = "*",
    reason: str = "Managed policy test rule",
) -> ManagedPolicyRule:
    now = utc_now()
    return ManagedPolicyRule(
        rule_id=new_id("mng_"),
        effect=effect,
        tool_pattern=tool_pattern,
        arguments_json=None,
        priority=100,
        enabled=True,
        reason=reason,
        created_by="test",
        created_at=now,
        updated_at=now,
    )


def test_managed_deny_overrides_static_allow(workspace: Path, engine: PolicyEngine, store: SQLiteStore) -> None:
    store.insert_managed_policy(_managed_rule(effect="deny", tool_pattern="read_file"))
    decision = engine.review(_read_action())
    assert decision.decision == "deny"
    assert "managed_policy_denied" in decision.reasons


def test_managed_deny_overrides_approval_required(workspace: Path, engine: PolicyEngine, store: SQLiteStore) -> None:
    store.insert_managed_policy(_managed_rule(effect="deny", tool_pattern="shell"))
    decision = engine.review(_shell_action())
    assert decision.decision == "deny"
    assert "managed_policy_denied" in decision.reasons


def test_managed_deny_overrides_denied_tool(workspace: Path, engine: PolicyEngine, store: SQLiteStore) -> None:
    store.insert_managed_policy(_managed_rule(effect="deny", tool_pattern="delete_file"))
    decision = engine.review(
        ToolAction(new_id("act_"), "delete_file", {"path": "x.txt"}, "blocked", False)
    )
    assert decision.decision == "deny"
    assert "managed_policy_denied" in decision.reasons


def test_static_allow_still_works_without_managed(engine: PolicyEngine, store: SQLiteStore) -> None:
    decision = engine.review(_read_action())
    assert decision.decision == "allow"


def test_static_approval_required_without_managed(engine: PolicyEngine, store: SQLiteStore) -> None:
    decision = engine.review(_shell_action())
    assert decision.decision == "needs_approval"


def test_managed_rule_tool_pattern_glob(workspace: Path, engine: PolicyEngine, store: SQLiteStore) -> None:
    store.insert_managed_policy(_managed_rule(effect="deny", tool_pattern="memory_*"))
    decision = engine.review(_memory_write_action())
    assert decision.decision == "deny"
    assert "managed_policy_denied" in decision.reasons

    decision = engine.review(_read_action())
    assert decision.decision == "allow"


def test_managed_rule_disabled_does_not_apply(workspace: Path, engine: PolicyEngine, store: SQLiteStore) -> None:
    rule = _managed_rule(effect="deny", tool_pattern="read_file")
    rule = ManagedPolicyRule(
        rule_id=rule.rule_id,
        effect=rule.effect,
        tool_pattern=rule.tool_pattern,
        arguments_json=rule.arguments_json,
        priority=rule.priority,
        enabled=False,
        reason=rule.reason,
        created_by=rule.created_by,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )
    store.insert_managed_policy(rule)
    decision = engine.review(_read_action())
    assert decision.decision == "allow"


def test_managed_policy_persistence(workspace: Path) -> None:
    store1 = SQLiteStore(workspace)
    store1.insert_managed_policy(_managed_rule(effect="deny", tool_pattern="shell"))

    store2 = SQLiteStore(workspace)
    rules = store2.list_managed_policies()
    assert len(rules) == 1
    assert rules[0]["tool_pattern"] == "shell"
    assert rules[0]["effect"] == "deny"


def test_managed_policy_delete(store: SQLiteStore) -> None:
    rule = _managed_rule(effect="deny", tool_pattern="shell")
    store.insert_managed_policy(rule)
    assert len(store.list_managed_policies()) == 1
    assert store.delete_managed_policy(rule.rule_id) is True
    assert len(store.list_managed_policies()) == 0
    assert store.delete_managed_policy("nonexistent") is False


def test_managed_policy_crud_via_sqlite(workspace: Path) -> None:
    store = SQLiteStore(workspace)
    now = utc_now()
    rule = ManagedPolicyRule(
        rule_id=new_id("mng_"),
        effect="deny",
        tool_pattern="network_request",
        arguments_json=json.dumps({"host": "evil.com"}),
        priority=50,
        enabled=True,
        reason="Block evil host",
        created_by="admin",
        created_at=now,
        updated_at=now,
    )
    store.insert_managed_policy(rule)
    rules = store.list_managed_policies()
    assert len(rules) == 1
    assert rules[0]["tool_pattern"] == "network_request"


def test_multiple_managed_rules(workspace: Path, engine: PolicyEngine, store: SQLiteStore) -> None:
    store.insert_managed_policy(_managed_rule(effect="deny", tool_pattern="shell", reason="Block shell"))
    store.insert_managed_policy(
        ManagedPolicyRule(
            rule_id=new_id("mng_"),
            effect="deny",
            tool_pattern="write_file",
            arguments_json=None,
            priority=50,
            enabled=True,
            reason="Block write_file",
            created_by="admin",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
    )

    decision = engine.review(_shell_action())
    assert decision.decision == "deny"
    assert "Block shell" in decision.reasons

    decision = engine.review(_write_action())
    assert decision.decision == "deny"
    assert "Block write_file" in decision.reasons

    decision = engine.review(_read_action())
    assert decision.decision == "allow"


def test_managed_policy_acceptance_cannot_be_bypassed_by_tool(workspace: Path, engine: PolicyEngine, store: SQLiteStore) -> None:
    store.insert_managed_policy(_managed_rule(effect="deny", tool_pattern="*"))
    for tool in ["read_file", "shell", "write_file", "grep", "memory_write"]:
        action = ToolAction(new_id("act_"), tool, {}, "medium", False)
        decision = engine.review(action)
        assert decision.decision == "deny", f"Tool {tool} was not denied by managed policy"
        assert "managed_policy_denied" in decision.reasons
