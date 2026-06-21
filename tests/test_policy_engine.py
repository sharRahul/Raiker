from __future__ import annotations

from raiker.contracts.ids import new_id
from raiker.contracts.models import ToolAction
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine


def _engine(tmp_path):  # type: ignore[no-untyped-def]
    return PolicyEngine(StaticPolicyConfig(tmp_path))


def test_policy_allows_workspace_read(tmp_path) -> None:  # type: ignore[no-untyped-def]
    decision = _engine(tmp_path).review(
        ToolAction(new_id("act_"), "read_file", {"path": "README.md"}, "medium", False)
    )
    assert decision.decision == "allow"


def test_policy_denies_outside_workspace(tmp_path) -> None:  # type: ignore[no-untyped-def]
    decision = _engine(tmp_path).review(
        ToolAction(new_id("act_"), "read_file", {"path": "../secret.txt"}, "blocked", False)
    )
    assert decision.decision == "deny"


def test_policy_requires_approval_for_shell(tmp_path) -> None:  # type: ignore[no-untyped-def]
    decision = _engine(tmp_path).review(
        ToolAction(new_id("act_"), "shell", {"command": "pytest"}, "high", True)
    )
    assert decision.decision == "needs_approval"


def test_policy_denies_secret_like_memory_write(tmp_path) -> None:  # type: ignore[no-untyped-def]
    decision = _engine(tmp_path).review(
        ToolAction(
            new_id("act_"),
            "memory_write",
            {"text": "api_key=supersecret123456789", "scope": "project"},
            "high",
            True,
        )
    )
    assert decision.decision == "deny"
    assert "secret_or_credential_like_memory_blocked" in decision.reasons
