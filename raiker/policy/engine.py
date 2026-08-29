from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import PolicyDecision, ToolAction
from raiker.memory.policy import MemorySensitivity, classify_memory_sensitivity
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.risk import assess
from raiker.tools.mcp_tools import is_mcp_tool


class PolicyEngine:
    def __init__(
        self, config: StaticPolicyConfig, store: Any = None, authority: Any = None
    ) -> None:
        self.config = config
        self.store = store
        # The same authority the executor will use. Policy decides before
        # execution and the executor decides again at the write; if the two
        # disagree about an attached root, a turn is refused after being allowed
        # or allowed after being refused.
        self.authority = authority

    def _is_inside_workspace(self, path: Path) -> bool:
        from raiker.tools.filesystem import FilesystemSafetyError
        from raiker.tools.path_authority import PathAuthority

        authority = self.authority or PathAuthority(self.config.workspace_root)
        try:
            authority.resolve_read(path)
            return True
        except FilesystemSafetyError:
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

    def _check_role_policy(self, action: ToolAction, user_id: str | None) -> PolicyDecision | None:
        if user_id is None or self.store is None:
            return None
        try:
            user = self.store.load_user(user_id)
        except Exception:
            return None
        if user is None:
            return PolicyDecision(
                decision_id=new_id("pol_"),
                action_id=action.action_id,
                decision="deny",
                reasons=[f"unknown_user:{user_id}"],
                requires_user_approval=False,
                policy_version=self.config.policy_version,
                risk_level="blocked",
                timestamp=utc_now(),
            )
        if not user.get("is_active", 0):
            return PolicyDecision(
                decision_id=new_id("pol_"),
                action_id=action.action_id,
                decision="deny",
                reasons=[f"user_not_active:{user_id}"],
                requires_user_approval=False,
                policy_version=self.config.policy_version,
                risk_level="blocked",
                timestamp=utc_now(),
            )
        return None

    def review(self, action: ToolAction, user_id: str | None = None) -> PolicyDecision:
        managed = self._check_managed_policy(action)
        if managed is not None:
            return managed
        role_check = self._check_role_policy(action, user_id)
        if role_check is not None:
            return role_check
        if action.tool_name == "memory_write":
            text = str(action.arguments.get("text", ""))
            sensitivity = classify_memory_sensitivity(text)
            if sensitivity in {
                MemorySensitivity.SECRET_LIKE,
                MemorySensitivity.CREDENTIAL_LIKE,
            }:
                return PolicyDecision(
                    decision_id=new_id("pol_"),
                    action_id=action.action_id,
                    decision="deny",
                    reasons=[
                        "secret_or_credential_like_memory_blocked",
                        f"sensitivity:{sensitivity.value}",
                    ],
                    requires_user_approval=False,
                    policy_version=self.config.policy_version,
                    risk_level="blocked",
                    timestamp=utc_now(),
                )
        if is_mcp_tool(action.tool_name):
            # A projected MCP tool call (BUG-12). Read-shaped at this layer for
            # the same reason `connector_read` is: what actually governs it is
            # enforced inside the tool — the `mcp_connector_runtime` gate, the
            # decision mode (default `ask` withholds), containment, and the
            # server's own advertised tool list. Its arguments are opaque
            # server-defined values, never workspace paths, so the path check
            # below does not apply to them.
            return PolicyDecision(
                decision_id=new_id("pol_"),
                action_id=action.action_id,
                decision="allow",
                reasons=["mcp_tool_call_governed_inside_tool"],
                requires_user_approval=False,
                policy_version=self.config.policy_version,
                risk_level=action.risk_level,
                timestamp=utc_now(),
            )
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
                reasons=[
                    "governed_document_creation_allowed"
                    if action.tool_name == "create_document"
                    else "session_command_grant_required"
                    if action.tool_name == "run_command"
                    else "workspace_read_allowed"
                ],
                requires_user_approval=False,
                policy_version=self.config.policy_version,
                risk_level=action.risk_level,
                timestamp=utc_now(),
            )
        if action.tool_name in self.config.approval_required_actions:
            # The decision records the action's *own* band, not "high".
            #
            # This branch used to assert `high` for everything that parks, which
            # made the word mean "this needs approval" rather than "this is
            # dangerous". Two different facts wearing one name is how an approval
            # queue stops being read: an owner who learns that "high risk" is
            # what a routine workspace write looks like has been taught to click
            # through the ones that are not routine. Parking is decided here;
            # how dangerous the action is was decided by its declared signals in
            # `raiker.policy.risk`, and this carries that through unchanged.
            # The reasons list is matched *exactly* by
            # `ToolBroker._is_ordinary_approval_decision`, which is how a
            # composer mode tells an ordinary action-bound pause from a hook
            # request, a managed-policy refusal, or anything it does not
            # recognise. Appending the assessment's reasons here is therefore not
            # free: it silently stopped `auto` from recognising an ordinary file
            # write, which is the narrowness working as designed. The band is
            # carried and the reasons are left alone; the signals behind the band
            # are in the tool's own declaration, so the assessment is still
            # recomputable from the record without widening this list.
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
                risk_level=assess(declared=action.risk_level).band,
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
