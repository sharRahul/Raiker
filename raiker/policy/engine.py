from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import PolicyDecision, ToolAction
from raiker.policy.config import StaticPolicyConfig


class PolicyEngine:
    def __init__(self, config: StaticPolicyConfig, store: Any = None) -> None:
        self.config = config
        self.store = store

    def _is_inside_workspace(self, path: Path) -> bool:
        try:
            path.resolve(strict=False).relative_to(self.config.workspace_root)
            return True
        except ValueError:
            return False

    def _path_arguments_inside_workspace(self, action: ToolAction) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        keys = ["path", "root"]
        for key in keys:
            value = action.arguments.get(key)
            if value is None:
                continue
            candidate = Path(str(value))
            resolved = (
                candidate if candidate.is_absolute() else self.config.workspace_root / candidate
            )
            if not self._is_inside_workspace(resolved):
                reasons.append(f"outside_workspace:{key}")
        pattern = action.arguments.get("pattern")
        if (
            action.tool_name == "glob"
            and isinstance(pattern, str)
            and (Path(pattern).is_absolute() or ".." in Path(pattern).parts)
        ):
            reasons.append("outside_workspace:pattern")
        return (not reasons, reasons)

    def _check_managed_policy(self, action: ToolAction) -> PolicyDecision | None:
        if self.store is None:
            return None
        try:
            rules = self.store.list_managed_policies(enabled_only=True)
        except Exception:
            return None
        for rule in rules:
            if not fnmatch.fnmatch(action.tool_name, str(rule.get("tool_pattern", "*"))):
                continue
            effect = str(rule.get("effect", "deny"))
            if effect != "deny":
                continue
            return PolicyDecision(
                decision_id=new_id("mng_"),
                action_id=action.action_id,
                decision="deny",
                reasons=["managed_policy_denied", str(rule.get("reason", ""))],
                requires_user_approval=False,
                policy_version="phase5-managed-v1",
                risk_level="blocked",
                timestamp=utc_now(),
            )
        return None

    def review(self, action: ToolAction) -> PolicyDecision:
        managed = self._check_managed_policy(action)
        if managed is not None:
            return managed
        if action.tool_name in self.config.allowed_read_actions:
            inside, reasons = self._path_arguments_inside_workspace(action)
            if not inside:
                return PolicyDecision(
                    decision_id=new_id("pol_"),
                    action_id=action.action_id,
                    decision="deny",
                    reasons=["workspace_boundary_denied", *reasons],
                    requires_user_approval=False,
                    policy_version=self.config.policy_version,
                    risk_level="blocked",
                    timestamp=utc_now(),
                )
            return PolicyDecision(
                decision_id=new_id("pol_"),
                action_id=action.action_id,
                decision="allow",
                reasons=["workspace_read_allowed"],
                requires_user_approval=False,
                policy_version=self.config.policy_version,
                risk_level=action.risk_level,
                timestamp=utc_now(),
            )
        if action.tool_name in self.config.approval_required_actions:
            return PolicyDecision(
                decision_id=new_id("pol_"),
                action_id=action.action_id,
                decision="needs_approval",
                reasons=[
                    f"{action.tool_name}_requires_approval",
                    "phase2_action_bound_approval_required",
                ],
                requires_user_approval=True,
                policy_version=self.config.policy_version,
                risk_level="high",
                timestamp=utc_now(),
            )
        return PolicyDecision(
            decision_id=new_id("pol_"),
            action_id=action.action_id,
            decision="deny",
            reasons=["unknown_or_denied_tool", f"tool:{action.tool_name}"],
            requires_user_approval=False,
            policy_version=self.config.policy_version,
            risk_level="blocked",
            timestamp=utc_now(),
        )
