"""Tool policy regression: connector_read / connector_write must not be denied.

These tools are advertised to the model and have real executors in the tool
broker (connector_read) or special intent handling (connector_write). A prior
policy-config gap left them un-routed, so the policy engine denied them as
``unknown_or_denied_tool`` — the model could propose them but they never ran.
"""
from __future__ import annotations

from pathlib import Path

from raiker.contracts.ids import new_id
from raiker.contracts.models import ToolAction
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine


def _engine(tmp_path: Path) -> PolicyEngine:
    return PolicyEngine(StaticPolicyConfig(tmp_path))


def _action(tool_name: str, args: dict[str, object], *, risk: str, approval: bool) -> ToolAction:
    return ToolAction(
        action_id=new_id("act_"),
        tool_name=tool_name,
        arguments=args,
        risk_level=risk,
        requires_approval=approval,
        proposed_by="model",
    )


class TestConnectorToolPolicy:
    def test_connector_read_is_allowed(self, tmp_path: Path) -> None:
        # connector_read is governed inside the tool (connector gate + decision
        # mode + credential + egress + manifest operation allowlist), exactly
        # like github_read. The policy proposal must allow it.
        decision = _engine(tmp_path).review(
            _action(
                "connector_read",
                {"connector_id": "github", "operation_id": "getRepo"},
                risk="medium",
                approval=False,
            )
        )
        assert decision.decision == "allow"
        assert "workspace_read_allowed" in decision.reasons

    def test_connector_write_requires_approval(self, tmp_path: Path) -> None:
        # connector_write is a real external mutation; it must route to the
        # approval path (the broker stores an immutable intent and the
        # approval resolution executes the exact approved operation once).
        decision = _engine(tmp_path).review(
            _action(
                "connector_write",
                {"connector_id": "github", "operation_id": "postRepo"},
                risk="high",
                approval=True,
            )
        )
        assert decision.decision == "needs_approval"
        assert decision.requires_user_approval is True
        assert "connector_write_requires_approval" in decision.reasons

    def test_connector_tools_are_not_unknown_or_denied(self, tmp_path: Path) -> None:
        engine = _engine(tmp_path)
        for tool in ("connector_read", "connector_write"):
            decision = engine.review(
                _action(
                    tool,
                    {"connector_id": "github", "operation_id": "op"},
                    risk="high" if tool == "connector_write" else "medium",
                    approval=tool == "connector_write",
                )
            )
            assert decision.decision != "deny", (
                f"{tool} was denied ({decision.reasons}); it must be routed, "
                "not blocked as unknown."
            )
