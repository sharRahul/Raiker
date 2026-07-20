"""Workstream F / Slice F3 (ZT-5) — scoped standing approval grants.

Covers the grant model invariants and its router integration:

* invariants — human-created only, sub-critical ceiling, mandatory expiry;
* creating a grant is itself a critical, human-decided action (F6 (d));
* an active matching grant satisfies an AI-proposed action's approval
  requirement without a fresh prompt (the "frictionless" mechanism), and every
  such use is logged with the grant id;
* an expired, revoked, out-of-scope, or over-ceiling grant matches nothing —
  the resting state is deny.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id
from raiker.events.query import EventViewer
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority.grants import GrantValidationError, build_grant_record, grant_covers
from raiker.runtime.authority.models import Principal, PrincipalType, RiskLevelValue
from raiker.runtime.authority.router import GovernedAction, RuntimeAuthority
from raiker.runtime.executors import build_default_executor_registry
from raiker.storage.sqlite import SQLiteStore


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    return _ws(tmp_path)


@pytest.fixture
def store(ws: Path) -> SQLiteStore:
    return SQLiteStore(ws)


@pytest.fixture
def authority(ws: Path, store: SQLiteStore) -> RuntimeAuthority:
    registry = build_default_executor_registry(ws, store)
    return RuntimeAuthority(store, EventLogWriter(store), executor_registry=registry)


def _human(store: SQLiteStore) -> Principal:
    raw = store.get_principal("principal_owner")
    assert raw is not None
    if isinstance(raw.get("principal_type"), str):
        raw["principal_type"] = PrincipalType(raw["principal_type"])
    return Principal(**raw)


def _ai() -> Principal:
    return Principal(
        principal_id="ai_worker",
        principal_type=PrincipalType.AI_AGENT,
        display_name="AI",
        role_ids=("rl_assistant",),
        is_active=True,
    )


def _write_action(principal_id: str, name: str = "notes.txt") -> GovernedAction:
    # No `requires_approval`: the approval requirement comes from the default
    # `ask` decision mode on the file-write capability, which is how an
    # AI-proposed write is parked in production (setting requires_approval on an
    # AI's own action would instead trip the self-approval guard).
    return GovernedAction(
        action_id=new_id("act_"),
        principal_id=principal_id,
        action_type="write_file",
        tool_or_service_name="write_file",
        arguments={"path": name, "text": "hello"},
        risk_level=RiskLevelValue.LOW,
    )


# ── model invariants ─────────────────────────────────────────────────────────


def test_only_human_may_create_grant() -> None:
    with pytest.raises(GrantValidationError, match="only_human_may_create_grant"):
        build_grant_record(
            principal_id="ai_worker",
            granted_by=_ai(),
            action_type="write_file",
            risk_ceiling=RiskLevelValue.LOW,
        )


def test_grant_ceiling_cannot_be_critical(store: SQLiteStore) -> None:
    with pytest.raises(GrantValidationError, match="grant_ceiling_cannot_be_critical"):
        build_grant_record(
            principal_id="ai_worker",
            granted_by=_human(store),
            action_type="write_file",
            risk_ceiling=RiskLevelValue.CRITICAL,
        )


def test_grant_has_mandatory_expiry(store: SQLiteStore) -> None:
    record = build_grant_record(
        principal_id="ai_worker",
        granted_by=_human(store),
        action_type="write_file",
        risk_ceiling=RiskLevelValue.MEDIUM,
    )
    assert record["expires_at"] > record["created_at"]


def test_grant_covers_respects_ceiling_scope_and_expiry() -> None:
    row = {
        "action_type": "write_file",
        "tool_name": "",
        "scope_pattern": "coding",
        "risk_ceiling": RiskLevelValue.MEDIUM,
        "expires_at": "2999-01-01T00:00:00Z",
        "revoked": 0,
    }
    assert grant_covers(row, action_type="write_file", tool_name="write_file",
                        scope="coding", risk_level=RiskLevelValue.LOW)
    # over ceiling
    assert not grant_covers(row, action_type="write_file", tool_name="write_file",
                            scope="coding", risk_level=RiskLevelValue.HIGH)
    # out of scope
    assert not grant_covers(row, action_type="write_file", tool_name="write_file",
                            scope="email", risk_level=RiskLevelValue.LOW)
    # critical is never covered
    assert not grant_covers(row, action_type="write_file", tool_name="write_file",
                            scope="coding", risk_level=RiskLevelValue.CRITICAL)
    # expired
    expired = {**row, "expires_at": "2000-01-01T00:00:00Z"}
    assert not grant_covers(expired, action_type="write_file", tool_name="write_file",
                            scope="coding", risk_level=RiskLevelValue.LOW)
    # revoked
    revoked = {**row, "revoked": 1}
    assert not grant_covers(revoked, action_type="write_file", tool_name="write_file",
                            scope="coding", risk_level=RiskLevelValue.LOW)


# ── engine + router integration ──────────────────────────────────────────────


def test_ai_write_needs_approval_without_grant(authority: RuntimeAuthority) -> None:
    result = authority.route_action(_write_action("ai_worker"), _ai())
    assert result.decision == "needs_approval"


def test_active_grant_satisfies_approval_and_executes(
    authority: RuntimeAuthority, store: SQLiteStore, ws: Path
) -> None:
    outcome = authority.create_standing_grant(
        granted_by=_human(store),
        principal_id="ai_worker",
        action_type="write_file",
        risk_ceiling=RiskLevelValue.MEDIUM,
    )
    assert isinstance(outcome, dict)

    result = authority.route_action(_write_action("ai_worker"), _ai())
    assert result.decision == "allow"
    assert (ws / "notes.txt").read_text() == "hello"

    # the grant's use is logged with its id
    applied = EventViewer(store).list_events(event_type="standing_grant_applied", limit=10)
    assert applied and applied[0]["event_type"] == "standing_grant_applied"
    row = store.load_standing_grant(outcome["grant_id"])
    assert row is not None and row["use_count"] == 1


def test_grant_creation_is_classified_critical(
    authority: RuntimeAuthority, store: SQLiteStore
) -> None:
    # An AI proposing to create a grant is denied at the critical floor.
    action = GovernedAction(
        action_id=new_id("act_"),
        principal_id="ai_worker",
        action_type="standing_grant_create",
        tool_or_service_name="standing_grant_create",
        arguments={},
        risk_level=RiskLevelValue.LOW,
    )
    result = authority.route_action(action, _ai())
    assert result.decision == "deny"
    assert result.message == "critical_action_requires_human_confirmation"


def test_grant_for_critical_action_type_refused(
    authority: RuntimeAuthority, store: SQLiteStore
) -> None:
    # A grant can never be minted for an action shape that itself classifies as
    # critical — that would attempt to pre-authorize a critical action.
    outcome = authority.create_standing_grant(
        granted_by=_human(store),
        principal_id="ai_worker",
        action_type="credential_rotate",
        risk_ceiling=RiskLevelValue.HIGH,
    )
    assert outcome == "grant_target_is_critical"


def test_revoked_grant_no_longer_satisfies(
    authority: RuntimeAuthority, store: SQLiteStore
) -> None:
    outcome = authority.create_standing_grant(
        granted_by=_human(store),
        principal_id="ai_worker",
        action_type="write_file",
        risk_ceiling=RiskLevelValue.MEDIUM,
    )
    assert isinstance(outcome, dict)
    assert authority.revoke_standing_grant(outcome["grant_id"], _human(store),
                                           granted_by="principal_owner") is None

    result = authority.route_action(_write_action("ai_worker"), _ai())
    assert result.decision == "needs_approval"


def test_ai_cannot_revoke_grant(authority: RuntimeAuthority, store: SQLiteStore) -> None:
    outcome = authority.create_standing_grant(
        granted_by=_human(store),
        principal_id="ai_worker",
        action_type="write_file",
        risk_ceiling=RiskLevelValue.LOW,
    )
    assert isinstance(outcome, dict)
    denial = authority.revoke_standing_grant(outcome["grant_id"], _ai())
    assert denial == "only_human_may_revoke_grant"


def test_grants_listed_for_owner(authority: RuntimeAuthority, store: SQLiteStore) -> None:
    authority.create_standing_grant(
        granted_by=_human(store),
        principal_id="ai_worker",
        action_type="write_file",
        risk_ceiling=RiskLevelValue.LOW,
    )
    listed = authority.list_standing_grants(granted_by="principal_owner")
    assert len(listed) == 1 and listed[0]["action_type"] == "write_file"
