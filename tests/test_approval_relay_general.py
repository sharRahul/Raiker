"""Workstream A / Slice A1 — immutable approval intent for the execution relay.

These tests pin the two A1 guarantees the relay must honour before it executes
an approved action:

* the arguments hash captured at approval time is re-verified at execution time
  (TOCTOU defense); a drifted payload is refused, never run;
* an approval carries a bounded TTL (default 24h); once past it, the approval
  resolves to ``expired`` and can never execute.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id
from raiker.contracts.models import ToolAction
from raiker.runtime.authority.models import Principal, RiskLevelValue
from raiker.runtime.authority.router import GovernedAction
from raiker.runtime.executors.tier1_approval import ApprovalExecutionRelay
from raiker.storage.sqlite import SQLiteStore


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


def _human(store: SQLiteStore) -> Principal:
    raw = store.get_principal("principal_owner")
    assert raw is not None
    return Principal(**raw)


def _pending(
    store: SQLiteStore,
    *,
    approval_id: str,
    action_id: str,
    arguments: dict[str, object],
    ttl_hours: float | None = 24.0,
) -> None:
    store.create_session("sess_a", "ws")
    store.insert_tool_action(
        ToolAction(
            action_id=action_id,
            tool_name="write_file",
            arguments=arguments,
            risk_level="low",
            requires_approval=True,
            proposed_by="principal_owner",
        ),
        session_id="sess_a",
        turn_id=None,
        status="approval_required",
    )
    store.insert_approval(approval_id, action_id, ttl_hours=ttl_hours)


def _relay_action(approval_id: str) -> GovernedAction:
    return GovernedAction(
        action_id=new_id("act_"),
        principal_id="principal_owner",
        action_type="approval_execution_relay",
        tool_or_service_name="approval_execution_relay",
        arguments={"approval_id": approval_id},
        risk_level=RiskLevelValue.LOW,
    )


# ── TTL is captured on creation ──────────────────────────────────────────────


def test_insert_approval_sets_default_ttl(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    _pending(store, approval_id="appr_1", action_id="act_1", arguments={"path": "a.txt", "text": "x"})

    approval = store.load_approval("appr_1")
    assert approval is not None
    expires_at = approval["expires_at"]
    assert expires_at is not None
    parsed = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
    # Default TTL is 24h; allow generous slack for clock/rounding.
    delta = parsed - datetime.now(UTC)
    assert timedelta(hours=23) < delta <= timedelta(hours=24, minutes=1)


def test_insert_approval_ttl_none_has_no_expiry(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    _pending(
        store,
        approval_id="appr_1",
        action_id="act_1",
        arguments={"path": "a.txt", "text": "x"},
        ttl_hours=None,
    )
    approval = store.load_approval("appr_1")
    assert approval is not None
    assert approval["expires_at"] is None


# ── TOCTOU: tampered payload is refused, not executed ────────────────────────


def test_relay_refuses_tampered_payload(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    _pending(store, approval_id="appr_1", action_id="act_1", arguments={"path": "safe.txt", "text": "safe"})

    # Mutate the stored action payload after the approval hash was recorded.
    with store.connect() as connection:
        connection.execute(
            "UPDATE tool_actions SET arguments_json = ? WHERE action_id = ?",
            ('{"path": "evil.txt", "text": "pwned"}', "act_1"),
        )

    relay = ApprovalExecutionRelay(ws, store)
    result = relay.execute(_relay_action("appr_1"), _human(store))

    assert result.ok is False
    assert result.reason_code == "approval_payload_tampered"
    # Nothing is written, and the approval is left pending (not silently approved).
    assert not (ws / "safe.txt").exists()
    assert not (ws / "evil.txt").exists()
    assert store.load_approval("appr_1")["status"] == "pending"  # type: ignore[index]


# ── TTL: expired approvals resolve `expired` and never execute ───────────────


def test_relay_refuses_and_expires_stale_approval(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    _pending(store, approval_id="appr_1", action_id="act_1", arguments={"path": "late.txt", "text": "late"})

    # Force the approval into the past.
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    with store.connect() as connection:
        connection.execute(
            "UPDATE approvals SET expires_at = ? WHERE approval_id = ?", (past, "appr_1")
        )

    relay = ApprovalExecutionRelay(ws, store)
    result = relay.execute(_relay_action("appr_1"), _human(store))

    assert result.ok is False
    assert result.reason_code == "approval_expired"
    assert not (ws / "late.txt").exists()
    assert store.load_approval("appr_1")["status"] == "expired"  # type: ignore[index]


# ── Happy path is unaffected by A1 ───────────────────────────────────────────


def test_relay_executes_untampered_in_ttl(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    _pending(store, approval_id="appr_1", action_id="act_1", arguments={"path": "ok.txt", "text": "content"})

    relay = ApprovalExecutionRelay(ws, store)
    result = relay.execute(_relay_action("appr_1"), _human(store))

    assert result.ok is True
    assert (ws / "ok.txt").read_text(encoding="utf-8") == "content"
    assert store.load_approval("appr_1")["status"] == "approved"  # type: ignore[index]


# ── expire_approval only transitions a still-pending approval ────────────────


def test_expire_approval_is_noop_once_resolved(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    _pending(store, approval_id="appr_1", action_id="act_1", arguments={"path": "a.txt", "text": "x"})

    store.resolve_approval("appr_1", status="approved", resolved_by="principal_owner", resolved_at="2026-07-19T00:00:00Z")
    assert store.expire_approval("appr_1") is False
    assert store.load_approval("appr_1")["status"] == "approved"  # type: ignore[index]
