"""QUI-P03, QUI-P05, QUI-P09 — Allow with limits.

A rule is a standing grant that names its limits. These hold the plan's rules:
the limits are required and validated, every limit fails closed, a rule covers
only an ordinary approval and still runs through the full runtime authority,
Careful still asks, project and future rules need the Within limits profile, a
rule is shaped from the approval on the server, and a repeated narrow action is
suggested — never made — as a rule.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.models.contracts import ModelResponse
from raiker.runtime.authority import grant_limits, grants
from raiker.runtime.authority.models import Principal, PrincipalType
from raiker.storage.sqlite import SQLiteStore
from tests.test_model_tool_call_loop import (
    FakeRouter,
    _envelope,
    _event_record,
    _events,
    _handle,
    _orchestrator,
    _write_call,
)

# ── The limits themselves ───────────────────────────────────────────────────


def test_limits_are_cleaned_and_refused_when_unenforceable() -> None:
    limits, hours = grant_limits.clean(
        {"scope": "future", "targets": ["Bob@Example.com", "https://Docs.Example.org/x", "github.com/Acme/Site.git"]},
    )
    assert limits["targets"] == ["bob@example.com", "docs.example.org", "acme/site"]
    assert (limits["max_uses"], hours, limits["sensitive_asks"], limits["attachments"]) == (10, 168, True, False)
    for raw, reason in (
        ({"scope": "always"}, "grant_limit_scope_invalid"),
        ({"scope": "conversation"}, "grant_limit_needs_conversation"),
        ({"scope": "project"}, "grant_limit_needs_project"),
        ({"scope": "future"}, "grant_limit_needs_targets"),
        ({"scope": "future", "targets": ["not a target!"]}, "grant_limit_target_invalid"),
        ({"scope": "future", "targets": ["a.com"], "max_uses": 0}, "grant_limit_uses_invalid"),
        ({"scope": "future", "targets": ["a.com"], "max_uses": True}, "grant_limit_uses_invalid"),
        ({"scope": "future", "targets": ["a.com"], "expires_hours": 24 * 8}, "grant_limit_expiry_invalid"),
        ({"scope": "future", "targets": ["a.com"], "sensitive_asks": "no"}, "grant_limit_sensitive_asks_invalid"),
    ):
        with pytest.raises(grant_limits.LimitsError, match=reason):
            grant_limits.clean(raw)
    # The conversation and project come from the server, never the request.
    scoped, _ = grant_limits.clean({"scope": "conversation", "session_id": "sess_other"}, session_id="sess_here")
    assert scoped["session_id"] == "sess_here"


def _rule(**overrides: Any) -> grant_limits.GrantLimits:
    base: dict[str, Any] = {
        "scope": "conversation", "session_id": "sess_a", "project_id": None,
        "targets": ["example.com"], "account": None, "max_uses": 2,
        "attachments": False, "sensitive_asks": True,
    }
    return grant_limits.GrantLimits(**{**base, **overrides})  # type: ignore[typeddict-item]


def _why(limits: grant_limits.GrantLimits, arguments: dict[str, Any], **context: Any) -> str | None:
    values: dict[str, Any] = {
        "session_id": "sess_a", "session_project": None, "session_profile": "standard", "use_count": 0,
    }
    values.update(context)
    return grant_limits.uncovered_reason(limits, arguments=arguments, **values)


def test_every_limit_fails_closed() -> None:
    rule = _rule()
    send = {"to": "ann@example.com", "body": "hello"}
    assert _why(rule, send) is None
    assert _why(rule, {"to": "ann@mail.example.com"}) is None  # a subdomain of an allowed domain
    assert _why(rule, send, session_id="sess_b") == "grant_limit_other_conversation"
    assert _why(rule, send, use_count=2) == "grant_limit_uses_spent"
    assert _why(rule, {"to": "ann@example.com, eve@evil.test"}) == "grant_limit_target_outside"
    assert _why(rule, {"to": "ann@example.com.evil.test"}) == "grant_limit_target_outside"
    # A target that cannot be read is outside the limits, never inside.
    assert _why(rule, {"body": "no recipient named"}) == "grant_limit_target_outside"
    assert _why(rule, {**send, "attachments": ["report.pdf"]}) == "grant_limit_attachments_ask"
    assert _why(rule, {**send, "body": "password: hunter2"}) == "grant_limit_sensitive_asks"
    assert _why(_rule(sensitive_asks=False), {**send, "body": "password: hunter2"}) is None
    assert _why(_rule(account="acc_work"), {**send, "account_id": "acc_home"}) == "grant_limit_other_account"


def test_project_and_future_rules_need_the_within_limits_profile() -> None:
    future = _rule(scope="future", session_id=None)
    send = {"to": "ann@example.com"}
    assert _why(future, send) == "grant_limit_profile_not_within_limits"
    assert _why(future, send, session_profile="within_limits") is None
    project = _rule(scope="project", session_id=None, project_id="proj_a")
    assert _why(project, send, session_profile="within_limits", session_project="proj_b") == "grant_limit_other_project"
    assert _why(project, send, session_profile="within_limits", session_project="proj_a") is None


def test_an_unreadable_rule_covers_nothing_and_says_so() -> None:
    unreadable = grant_limits.load({"limits_json": "{not json"})
    assert unreadable is not None
    assert _why(unreadable, {"to": "ann@example.com"}) is not None
    assert grant_limits.load({"limits_json": "{}"}) is None
    assert grant_limits.describe(_rule(), use_count=1)[:3] == [
        "Only in the conversation it was allowed in",
        "Only to example.com",
        "1 of 2 uses left",
    ]


def test_no_grant_outlives_a_week() -> None:
    owner = Principal(principal_id="p_owner", principal_type=PrincipalType.HUMAN, display_name="Owner")
    with pytest.raises(grants.GrantValidationError, match="grant_ttl_too_long"):
        grants.build_grant_record(
            principal_id="p_owner", granted_by=owner, action_type="write_file", risk_ceiling="medium", ttl_days=8
        )


# ── The broker applies a rule, and nothing wider ───────────────────────────


def _owner_rule(store: SQLiteStore, owner_id: str, session_id: str, *, scope: str = "conversation", **limits: Any) -> str:
    owner = Principal(principal_id=owner_id, principal_type=PrincipalType.HUMAN, display_name="Owner")
    cleaned, hours = grant_limits.clean({"scope": scope, **limits}, session_id=session_id)
    record = grants.build_grant_record(
        principal_id=owner_id, granted_by=owner, action_type="write_file", tool_name="write_file",
        risk_ceiling="high", ttl_days=hours / 24, limits_json=json.dumps(cleaned),
    )
    store.insert_standing_grant(record)
    return str(record["grant_id"])


def _two_turns(tmp_path: Path) -> FakeRouter:
    return FakeRouter([
        ModelResponse(text="", tool_calls=[_write_call()], finish_reason="tool_calls"),
        ModelResponse(text="Done.", finish_reason="stop"),
    ])


def test_a_rule_for_this_conversation_runs_the_write_through_the_authority(tmp_path: Path) -> None:
    orchestrator = _orchestrator(tmp_path, _two_turns(tmp_path))
    envelope = _envelope("write the report")
    store = orchestrator.tool_broker.store
    assert store is not None
    store.create_session(envelope.session_id, str(tmp_path), user_id="owner")
    grant_id = _owner_rule(store, orchestrator.tool_broker.principal_id, envelope.session_id, max_uses=1)

    response = _handle(orchestrator, envelope)

    assert response.status == "completed"
    assert (tmp_path / "report.md").read_text(encoding="utf-8") == "# Report\n"
    events = _events(orchestrator, envelope.session_id)
    assert "approval_requested" not in events
    assert _event_record(orchestrator, envelope.session_id, "limit_rule_executed")["payload"]["grant_id"] == grant_id
    # The full authority still decided: the executor ran under its own event.
    assert "action_executed" in events
    assert store.load_standing_grant(grant_id)["use_count"] == 1  # type: ignore[index]


def test_a_spent_or_foreign_rule_leaves_the_approval_to_the_owner(tmp_path: Path) -> None:
    orchestrator = _orchestrator(tmp_path, _two_turns(tmp_path))
    envelope = _envelope("write the report")
    store = orchestrator.tool_broker.store
    assert store is not None
    store.create_session(envelope.session_id, str(tmp_path), user_id="owner")
    # A rule for another conversation covers nothing here.
    _owner_rule(store, orchestrator.tool_broker.principal_id, "sess_elsewhere")
    response = _handle(orchestrator, envelope)
    assert response.status == "needs_approval"
    assert "limit_rule_executed" not in _events(orchestrator, envelope.session_id)


def test_careful_still_asks_under_a_rule(tmp_path: Path) -> None:
    orchestrator = _orchestrator(tmp_path, _two_turns(tmp_path))
    envelope = _envelope("write the report")
    envelope = dataclasses.replace(
        envelope, options=dataclasses.replace(envelope.options, capability_modes={"file_write_execution": "ask"})
    )
    store = orchestrator.tool_broker.store
    assert store is not None
    store.create_session(envelope.session_id, str(tmp_path), user_id="owner")
    _owner_rule(store, orchestrator.tool_broker.principal_id, envelope.session_id)
    response = _handle(orchestrator, envelope)
    assert response.status == "needs_approval"
    assert not (tmp_path / "report.md").exists()


# ── The API: shaped on the server, suggested, never silent ──────────────────


@pytest.fixture()
def owner(tmp_path: Path) -> tuple[TestClient, dict[str, str], Path]:
    client = TestClient(create_app(tmp_path))
    token = client.post("/api/auth/register", json={"username": "owner", "password": "a-long-password-1"}).json()["token"]
    return client, {"Authorization": f"Bearer {token}"}, tmp_path


def _approval_for_owner(
    ws: Path, tool: str, arguments: dict[str, Any], *, name: str = "", critical: bool = False, status: str = ""
) -> str:
    """A parked approval in the registered owner's own conversation."""
    from tests.factories import tool_action

    store = SQLiteStore(ws)
    row = store._row("SELECT user_id FROM users ORDER BY created_at LIMIT 1")
    assert row is not None
    owner_user = str(row["user_id"])
    key = name or tool
    store.create_session(f"sess_{key}", str(ws), user_id=owner_user)
    store.insert_turn(f"sess_{key}", f"turn_{key}", "do the thing")
    action = tool_action(
        tool, arguments, action_id=f"act_{key}", risk_level="medium", requires_approval=True,
        proposed_by="principal_owner",
    )
    store.insert_tool_action(action, f"sess_{key}", f"turn_{key}", "approval_required")
    store.insert_approval(f"appr_{key}", action)
    if critical:
        store._execute("UPDATE approvals SET critical = 1 WHERE approval_id = ?", (f"appr_{key}",))
    if status:
        store._execute("UPDATE approvals SET status = ? WHERE approval_id = ?", (status, f"appr_{key}"))
    return f"appr_{key}"


def test_allow_for_this_task_is_shaped_from_the_approval(owner: tuple[TestClient, dict[str, str], Path]) -> None:
    client, h, ws = owner
    approval_id = _approval_for_owner(ws, "write_file", {"path": "notes.txt", "text": "hi"})
    draft = client.get(f"/api/approvals/{approval_id}/limit-rule", headers=h)
    assert draft.status_code == 200, draft.text
    assert draft.json()["limits"]["scope"] == "conversation"
    made = client.post(
        f"/api/approvals/{approval_id}/limit-rule",
        json={"limits": {"scope": "conversation", "max_uses": 3, "expires_hours": 2}},
        headers=h,
    )
    assert made.status_code == 200, made.text
    grant = made.json()["grant"]
    # The shape is the approval's own, never the request's.
    assert (grant["tool_name"], grant["risk_ceiling"]) == ("write_file", "medium")
    assert grant["limits"]["session_id"] == "sess_write_file"
    assert grant["limits_words"][0] == "Only in the conversation it was allowed in"
    refused = client.post(
        f"/api/approvals/{approval_id}/limit-rule", json={"limits": {"scope": "future"}}, headers=h
    )
    assert (refused.status_code, refused.json()["detail"]["reason_code"]) == (422, "grant_limit_needs_targets")


def test_a_question_or_a_critical_action_cannot_become_a_rule(owner: tuple[TestClient, dict[str, str], Path]) -> None:
    client, h, ws = owner
    from raiker.contracts.models import OWNER_QUESTION_TOOL

    question = _approval_for_owner(ws, OWNER_QUESTION_TOOL, {"questions": []})
    assert client.get(f"/api/approvals/{question}/limit-rule", headers=h).status_code == 409
    critical = _approval_for_owner(ws, "write_file", {"path": "x"}, name="critical", critical=True)
    refused = client.get(f"/api/approvals/{critical}/limit-rule", headers=h)
    assert (refused.status_code, refused.json()["detail"]["reason_code"]) == (409, "grant_target_is_critical")


def test_a_rule_for_one_conversation_is_never_named_through_standing_grants(
    owner: tuple[TestClient, dict[str, str], Path],
) -> None:
    client, h, _ws = owner
    refused = client.post(
        "/api/standing-grants",
        json={"action_type": "write_file", "risk_ceiling": "medium", "limits": {"scope": "conversation"}},
        headers=h,
    )
    assert refused.status_code == 403
    made = client.post(
        "/api/standing-grants",
        json={
            "action_type": "connector_write", "tool_name": "connector_write", "risk_ceiling": "medium",
            "limits": {"scope": "future", "targets": ["example.com"], "expires_hours": 24},
        },
        headers=h,
    )
    assert made.status_code == 200, made.text
    assert "Only to example.com" in made.json()["grant"]["limits_words"]


def test_the_same_narrow_action_is_suggested_and_never_made(owner: tuple[TestClient, dict[str, str], Path]) -> None:
    client, h, ws = owner
    for index in range(3):
        _approval_for_owner(
            ws, "connector_write", {"channel": "#launch", "text": "hi"}, name=f"send_{index}", status="executed"
        )
    # Two allows elsewhere are not enough, and a declined one is never offered.
    for index in range(2):
        _approval_for_owner(ws, "connector_write", {"channel": "#ops"}, name=f"ops_{index}", status="executed")
    # An address would reach the browser redacted, so it is never offered.
    for index in range(3):
        _approval_for_owner(ws, "connector_write", {"to": "ann@example.com"}, name=f"ann_{index}", status="executed")
    suggestions = client.get("/api/limit-rules/suggestions", headers=h).json()["suggestions"]
    assert [(s["tool_name"], s["targets"], s["count"]) for s in suggestions] == [
        ("connector_write", ["launch"], 3)
    ]
    assert suggestions[0]["limits"]["scope"] == "future"
    # Offered, not made.
    assert client.get("/api/standing-grants", headers=h).json()["grants"] == []
    # Once a rule covers it, it is no longer offered.
    client.post(
        "/api/standing-grants",
        json={
            "action_type": "connector_write", "tool_name": "connector_write", "risk_ceiling": "medium",
            "limits": suggestions[0]["limits"],
        },
        headers=h,
    )
    assert client.get("/api/limit-rules/suggestions", headers=h).json()["suggestions"] == []
