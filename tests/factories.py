"""Builders for the objects tests construct most (OPT-17).

A test that routes one action used to spell out the principal and the action
field by field — eight lines each, a hundred times over — so the one field the
test was about sat among seven that were not. These builders fill the fields
nothing depends on and **require** the ones that decide authority: a
principal's roles, an action's principal and risk, a tool call's approval flag.
A test therefore still states, at the call, exactly what posture it is testing.
"""

from __future__ import annotations

from typing import Any

from raiker.contracts.ids import new_id
from raiker.contracts.models import ToolAction
from raiker.runtime.authority.models import Principal, PrincipalType
from raiker.runtime.authority.router import GovernedAction

__all__ = ["ai_agent", "governed_action", "human", "tool_action"]


def human(
    principal_id: str = "principal_owner",
    *,
    role_ids: tuple[str, ...],
    display_name: str = "Owner",
    **fields: Any,
) -> Principal:
    """An active human principal holding exactly ``role_ids``."""
    return Principal(
        principal_id=principal_id,
        principal_type=PrincipalType.HUMAN,
        display_name=display_name,
        role_ids=role_ids,
        **{"is_active": True, **fields},
    )


def ai_agent(
    principal_id: str = "principal_ai",
    *,
    role_ids: tuple[str, ...],
    domain_scopes: tuple[str, ...],
    display_name: str = "AI",
    **fields: Any,
) -> Principal:
    """An active AI principal holding exactly ``role_ids`` in ``domain_scopes``."""
    return Principal(
        principal_id=principal_id,
        principal_type=PrincipalType.AI_AGENT,
        display_name=display_name,
        role_ids=role_ids,
        domain_scopes=domain_scopes,
        **{"is_active": True, **fields},
    )


def governed_action(
    capability: str,
    *,
    principal_id: str,
    risk_level: str,
    arguments: dict[str, Any] | None = None,
    **fields: Any,
) -> GovernedAction:
    """An action on ``capability``, which is both its type and its tool name."""
    return GovernedAction(
        action_id=fields.pop("action_id", None) or new_id("act_"),
        principal_id=principal_id,
        action_type=capability,
        tool_or_service_name=capability,
        arguments=dict(arguments or {}),
        risk_level=risk_level,
        **fields,
    )


def tool_action(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    *,
    risk_level: str,
    requires_approval: bool,
    **fields: Any,
) -> ToolAction:
    """A model-proposed call to ``tool_name``."""
    return ToolAction(
        action_id=fields.pop("action_id", None) or new_id("act_"),
        tool_name=tool_name,
        arguments=dict(arguments or {}),
        risk_level=risk_level,
        requires_approval=requires_approval,
        **fields,
    )
