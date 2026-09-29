"""OPT-04 — request-scoped helpers are shared, not re-declared per route module.

Twenty route modules each carried an ``_auth`` and a ``_ws`` with the same body.
They import :mod:`raiker.api.dependencies` now; this test stops a new module
from quietly growing its own copy again. A helper whose body *differs* — a
host-control scope, a service lookup — is not a copy and is left alone.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi import HTTPException

from raiker.api.dependencies import refusal, require_human
from raiker.runtime.authority.models import Principal, PrincipalType

API = Path(__file__).resolve().parents[1] / "raiker" / "api"

_COPIES = {
    "return request.app.state.workspace_root",
    "return Path(str(request.app.state.workspace_root))",
    "return AuthMiddleware(_ws(request)).authenticate(request)",
    "return AuthMiddleware(request.app.state.workspace_root).authenticate(request)",
}


def test_no_route_module_redeclares_a_shared_dependency() -> None:
    copies: list[str] = []
    for path in sorted(API.glob("routes_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if (
                isinstance(node, ast.FunctionDef)
                and len(node.body) == 1
                and ast.unparse(node.body[0]) in _COPIES
            ):
                copies.append(f"{path.name}:{node.name}")
    assert copies == []


def test_a_non_human_principal_is_refused_with_the_stable_reason() -> None:
    agent = Principal("agent_1", PrincipalType.AI_AGENT, "Raiker agent")
    with pytest.raises(HTTPException) as refused:
        require_human(agent)
    assert refused.value.status_code == 403
    assert refused.value.detail == {"ok": False, "reason_code": "human_principal_required"}
    require_human(Principal("owner", PrincipalType.HUMAN, "Owner"))


def _is_hand_built_refusal(node: ast.AST) -> bool:
    if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "HTTPException"):
        return False
    detail = next((kw.value for kw in node.keywords if kw.arg == "detail"), None)
    return (
        isinstance(detail, ast.Dict)
        and [getattr(key, "value", None) for key in detail.keys] == ["ok", "reason_code"]
        and isinstance(detail.values[0], ast.Constant)
        and detail.values[0].value is False
    )


def test_the_refusal_envelope_is_built_in_one_place() -> None:
    """A hundred and seventy-four route sites spelled the envelope out by hand."""
    hand_built = [
        f"{path.name}:{getattr(node, 'lineno', 0)}"
        for path in sorted(API.glob("*.py"))
        if path.name != "refusals.py"
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if _is_hand_built_refusal(node)
    ]
    assert hand_built == []


def test_a_refusal_keeps_the_routes_status_and_the_shared_body() -> None:
    refused = refusal(409, "approval_already_resolved")
    assert refused.status_code == 409
    assert refused.detail == {"ok": False, "reason_code": "approval_already_resolved"}
