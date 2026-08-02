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


def test_every_model_exposed_tool_has_a_policy_verdict(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A tool advertised to the model must not fall through to a hard deny.

    Found while implementing B6/B7: `create_task` and `assign_session_project`
    were both in the model's tool schema and in neither policy set, so every
    call the model made was answered `unknown_or_denied_tool`. The schema and
    the policy are two lists that have to agree, and this is what says so.
    """
    from raiker.models.tool_call_validation import _MODEL_EXPOSED_TOOLS

    engine = _engine(tmp_path)
    denied = [
        name
        for name in sorted(_MODEL_EXPOSED_TOOLS)
        if "unknown_or_denied_tool"
        in engine.review(ToolAction(new_id("act_"), name, {}, "medium", False)).reasons
    ]
    assert denied == []


def test_planning_and_delegation_are_read_shaped(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """B6/B7 — neither tool pauses the loop for an approval it does not need."""
    for name in ("update_plan", "spawn_subagent"):
        decision = _engine(tmp_path).review(
            ToolAction(new_id("act_"), name, {}, "medium", False)
        )
        assert decision.decision == "allow", name
        assert decision.requires_user_approval is False, name


def test_local_organisation_tools_take_the_approval_path(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """They mutate owner data, so they wait for the owner rather than run."""
    for name in ("create_task", "assign_session_project"):
        decision = _engine(tmp_path).review(
            ToolAction(new_id("act_"), name, {}, "high", True)
        )
        assert decision.decision == "needs_approval", name
