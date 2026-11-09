"""QUI-P03, QUI-P05, QUI-P09 — **Allow with limits** made from an approval, and suggested.

Three routes, all owner-scoped and human-only to change anything:

* ``GET /api/approvals/{approval_id}/limit-rule`` — the limits a rule made from
  this approval would start with: where it applies, the recipients or sites the
  action itself reaches, how many uses and for how long. A draft; it grants
  nothing.
* ``POST /api/approvals/{approval_id}/limit-rule`` — **Allow for this task**:
  the rule, derived on the server from the approval's own stored action (its
  tool, risk and conversation). The request names only limits, never the shape,
  so a client cannot widen a rule beyond the action the owner was looking at.
* ``GET /api/limit-rules/suggestions`` — QUI-P09: the same narrow action the
  owner keeps allowing, offered as a rule. Raiker never creates one silently.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from fastapi import APIRouter, Request, status

from raiker.api.dependencies import authenticate, refusal, require_human
from raiker.api.dependencies import workspace_root as _ws
from raiker.api.routes_control import _get_service
from raiker.api.schemas import LimitRuleRequest, serialize_dto
from raiker.api.wire.control import (
    LimitRuleCreated,
    LimitRuleDraft,
    LimitRuleSuggestion,
    LimitRuleSuggestions,
    standing_grant,
)
from raiker.approvals.execution import approval_arguments
from raiker.contracts.models import OWNER_QUESTION_TOOL
from raiker.runtime.authority import grant_limits
from raiker.runtime.authority.critical import classify_critical
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()

#: The decisions that count as "the owner allowed it" for a suggestion.
_ALLOWED = ("approved", "executing", "executed", "execution_failed")
#: How many identical allows, inside the window, before a rule is offered.
SUGGEST_AFTER = 3
SUGGEST_WINDOW_DAYS = 7
_RISKS = ("low", "medium", "high")


def _approval(request: Request, approval_id: str, *, human: bool = False) -> tuple[SQLiteStore, dict[str, Any], str]:
    _session, principal = authenticate(request)
    if human:
        require_human(principal)
    store = SQLiteStore(_ws(request))
    row = store.load_approval(approval_id, user_id=store.principal_user_id(principal.principal_id))
    if row is None:
        raise refusal(status.HTTP_404_NOT_FOUND, "approval_not_found")
    tool = str(row.get("tool_name") or "")
    # A question is answered, never allowed; a critical action is decided live,
    # every time, and no rule may cover it.
    if tool == OWNER_QUESTION_TOOL:
        raise refusal(status.HTTP_409_CONFLICT, "approval_is_a_question")
    risk = str(row.get("risk_level") or "")
    if row.get("critical") or risk not in _RISKS or classify_critical(tool, tool, approval_arguments(row)) is not None:
        raise refusal(status.HTTP_409_CONFLICT, "grant_target_is_critical")
    return store, row, principal.principal_id


def _session_project(store: SQLiteStore, session_id: str) -> str | None:
    row = store._row("SELECT project_id FROM sessions WHERE session_id = ?", (session_id,))
    return str(row["project_id"]) if row is not None and row["project_id"] else None


@router.get("/api/approvals/{approval_id}/limit-rule")
async def limit_rule_draft(approval_id: str, request: Request) -> dict[str, Any]:
    """The limits **Allow for this task** starts from. Nothing is created."""
    store, row, _owner = _approval(request, approval_id)
    session_id = str(row.get("session_id") or "")
    targets = list(dict.fromkeys(grant_limits.known_targets(approval_arguments(row))))
    answer: LimitRuleDraft = {
        "approval_id": approval_id,
        "tool_name": str(row.get("tool_name") or ""),
        "risk_level": str(row.get("risk_level") or ""),
        "project_id": _session_project(store, session_id),
        "limits": {
            "scope": "conversation",
            "targets": targets[: grant_limits.MAX_TARGETS],
            "max_uses": grant_limits.DEFAULT_USES,
            "expires_hours": grant_limits.DEFAULT_HOURS["conversation"],
            "attachments": False,
            "sensitive_asks": True,
        },
    }
    return serialize_dto(answer)


@router.post("/api/approvals/{approval_id}/limit-rule")
async def create_limit_rule(approval_id: str, body: LimitRuleRequest, request: Request) -> dict[str, Any]:
    """**Allow for this task**: a rule shaped exactly like this approval's action."""
    store, row, owner = _approval(request, approval_id, human=True)
    session_id = str(row.get("session_id") or "")
    tool = str(row.get("tool_name") or "")
    limits = dict(body.limits)
    service = _get_service(request)
    result = service.create_standing_grant(
        owner,
        action_type=tool,
        tool_name=tool,
        risk_ceiling=str(row.get("risk_level")),
        scope_pattern="*",
        reason=f"Allowed with limits from approval {approval_id}",
        limits=limits,
        session_id=session_id or None,
        project_id=_session_project(store, session_id) if limits.get("scope") == "project" else None,
    )
    if not result.ok:
        raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, result.reason_code or "grant_limits_invalid")
    created: LimitRuleCreated = {"ok": True, "grant": standing_grant(result.data["grant"])}
    return serialize_dto(created)


@router.get("/api/limit-rules/suggestions")
async def limit_rule_suggestions(request: Request) -> dict[str, Any]:
    """QUI-P09 — narrow actions the owner keeps allowing, offered as rules.

    Three or more allows of the same tool to the same recipients or sites in a
    week, none declined, no active rule already covering them, and nothing
    critical. Actions with no target are never suggested: a rule beyond one
    conversation has to name where it may reach.
    """
    _session, principal = authenticate(request)
    store = SQLiteStore(_ws(request))
    user_id = store.principal_user_id(principal.principal_id)
    since = (datetime.now(UTC) - timedelta(days=SUGGEST_WINDOW_DAYS)).isoformat().replace("+00:00", "Z")
    rows = store._rows(
        """
        SELECT approvals.approval_id, approvals.status, approvals.created_at,
               tool_actions.tool_name, tool_actions.arguments_json, tool_actions.risk_level
        FROM approvals
        JOIN tool_actions ON tool_actions.action_id = approvals.action_id
        JOIN sessions ON sessions.session_id = tool_actions.session_id AND sessions.user_id = ?
        WHERE approvals.created_at >= ? AND COALESCE(approvals.critical, 0) = 0
        ORDER BY approvals.created_at DESC
        """,
        (user_id, since),
    )
    allowed: Counter[tuple[str, tuple[str, ...]]] = Counter()
    declined: set[tuple[str, tuple[str, ...]]] = set()
    risk: dict[tuple[str, tuple[str, ...]], str] = {}
    latest: dict[tuple[str, tuple[str, ...]], str] = {}
    for item in rows:
        tool = str(item["tool_name"])
        level = str(item["risk_level"] or "")
        if tool == OWNER_QUESTION_TOOL or level not in _RISKS:
            continue
        arguments = approval_arguments(dict(item))
        if classify_critical(tool, tool, arguments) is not None:
            continue
        targets = tuple(sorted(set(grant_limits.known_targets(arguments))))
        if not targets:
            continue
        key = (tool, targets)
        if item["status"] == "denied":
            declined.add(key)
        elif item["status"] in _ALLOWED:
            allowed[key] += 1
            latest.setdefault(key, str(item["approval_id"]))
            if _RISKS.index(level) > _RISKS.index(risk.get(key, "low")):
                risk[key] = level
            risk.setdefault(key, level)
    active = [
        grant
        for grant in store.list_standing_grants(granted_by=principal.principal_id, include_inactive=False)
        if grant_limits.load(grant) is not None
    ]

    def covered(tool: str, targets: tuple[str, ...]) -> bool:
        for grant in active:
            limits = grant_limits.load(grant)
            if limits is None or grant.get("tool_name") != tool:
                continue
            if limits.get("targets") and all(
                grant_limits._within(target, limits["targets"]) for target in targets
            ):
                return True
        return False

    suggestions: list[LimitRuleSuggestion] = []
    for (tool, targets), count in allowed.most_common():
        if count < SUGGEST_AFTER or (tool, targets) in declined or covered(tool, targets):
            continue
        suggestions.append({
            "tool_name": tool,
            "targets": list(targets),
            "count": count,
            "risk_level": risk[(tool, targets)],
            "approval_id": latest[(tool, targets)],
            "limits": cast(Any, {
                "scope": "future",
                "targets": list(targets),
                "max_uses": grant_limits.DEFAULT_USES,
                "expires_hours": grant_limits.DEFAULT_HOURS["future"],
                "attachments": False,
                "sensitive_asks": True,
            }),
        })
    answer: LimitRuleSuggestions = {"suggestions": suggestions[:5]}
    return serialize_dto(answer)
