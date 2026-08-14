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

from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id
from raiker.contracts.models import ToolAction
from raiker.events.query import EventViewer
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority.models import Principal, RiskLevelValue
from raiker.runtime.authority.router import GovernedAction, RuntimeAuthority
from raiker.runtime.executors import build_default_executor_registry
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


def _set_gate(store: SQLiteStore, capability: str, state: str) -> None:
    """Persist a global capability gate state.

    The relay re-governs the approved action at execution time, so the target
    capability's gate state is what decides whether the approved action runs.
    Real-executor gates default enabled, so positive tests need not enable them;
    the disabled-gate test uses this to fail the gate closed.
    """
    now = "2026-07-19T00:00:00Z"
    store.upsert_capability_gate_state({
        "capability": capability,
        "state": state,
        "runtime_mode": "",
        "requested_by": "principal_owner",
        "requested_at": now,
        "activated_by": "principal_owner",
        "activated_at": now,
        "reason": "test",
        "created_at": now,
        "updated_at": now,
    })


def _pending(
    store: SQLiteStore,
    *,
    approval_id: str,
    action_id: str,
    arguments: dict[str, object],
    tool_name: str = "write_file",
    risk_level: str = "low",
    ttl_hours: float | None = 24.0,
) -> None:
    store.create_session("sess_a", "ws")
    store.insert_tool_action(
        ToolAction(
            action_id=action_id,
            tool_name=tool_name,
            arguments=arguments,
            risk_level=risk_level,
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
    _set_gate(store, "file_write_execution", "enabled_runtime")
    _pending(store, approval_id="appr_1", action_id="act_1", arguments={"path": "ok.txt", "text": "content"})

    relay = ApprovalExecutionRelay(ws, store)
    result = relay.execute(_relay_action("appr_1"), _human(store))

    assert result.ok is True
    assert (ws / "ok.txt").read_text(encoding="utf-8") == "content"
    assert store.load_approval("appr_1")["status"] == "executed"  # type: ignore[index]


# ── expire_approval only transitions a still-pending approval ────────────────


def test_expire_approval_is_noop_once_resolved(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    _pending(store, approval_id="appr_1", action_id="act_1", arguments={"path": "a.txt", "text": "x"})

    store.resolve_approval("appr_1", status="approved", resolved_by="principal_owner", resolved_at="2026-07-19T00:00:00Z")
    assert store.expire_approval("appr_1") is False
    assert store.load_approval("appr_1")["status"] == "approved"  # type: ignore[index]


# ── A2/A3 — generalized executor dispatch beyond write_file ──────────────────


def test_relay_dispatches_memory_write_end_to_end(tmp_path: Path) -> None:
    """M1 exit criterion: an approved *non-file* action executes end-to-end
    through the outer RuntimeAuthority + the relay."""
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    _set_gate(store, "approval_execution_relay", "enabled_runtime")
    _set_gate(store, "memory_write_execution", "enabled_runtime")
    _pending(
        store,
        approval_id="appr_1",
        action_id="act_1",
        tool_name="memory_write",
        arguments={"text": "The project persists state in SQLite.", "scope": "project"},
    )

    authority = RuntimeAuthority(
        store, EventLogWriter(store),
        executor_registry=build_default_executor_registry(ws, store),
    )
    relay_action = GovernedAction(
        action_id=new_id("act_"),
        principal_id="principal_owner",
        action_type="approval_execution_relay",
        tool_or_service_name="approval_execution_relay",
        arguments={"approval_id": "appr_1"},
        risk_level=RiskLevelValue.LOW,
        session_id="sess_a",
    )
    result = authority.route_action(relay_action, _human(store))

    assert result.decision == "allow"
    assert result.message == "executed"
    assert store.load_approval("appr_1")["status"] == "executed"  # type: ignore[index]


def test_relay_dispatches_apply_patch(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    (ws / "poem.txt").write_text("roses\n", encoding="utf-8")
    _set_gate(store, "patch_apply_execution", "enabled_runtime")
    _pending(
        store,
        approval_id="appr_1",
        action_id="act_1",
        tool_name="apply_patch",
        arguments={
            "path": "poem.txt",
            "patch": "--- a/poem.txt\n+++ b/poem.txt\n@@ -1 +1 @@\n-roses\n+roses are red\n",
        },
    )

    relay = ApprovalExecutionRelay(ws, store)
    result = relay.execute(_relay_action("appr_1"), _human(store))

    assert result.ok is True, result.reason_code
    assert store.load_approval("appr_1")["status"] == "executed"  # type: ignore[index]
    assert "red" in (ws / "poem.txt").read_text(encoding="utf-8")


def test_relay_dispatches_tier2_shell(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    # Tier-2 gates carry the threat-ack requirement at *enable* time (a separate,
    # already-tested path); here we assert the relay dispatches to the Tier-2
    # executor once the gate is enabled, rather than blocking it as no-executor.
    _set_gate(store, "shell_execution", "enabled_runtime")
    _pending(
        store,
        approval_id="appr_1",
        action_id="act_1",
        tool_name="shell",
        risk_level="medium",
        # `echo` is a shell builtin on Windows, whereas `python` is an
        # explicitly allowed executable on every supported test platform.
        # RAIKER-2023: `python -c` is an interpreter escape and is refused by
        # the command policy, so this relay scenario uses a command that is not.
        arguments={"command": "echo relayed"},
    )

    relay = ApprovalExecutionRelay(ws, store)
    result = relay.execute(_relay_action("appr_1"), _human(store))

    assert result.ok is True, result.reason_code
    assert result.artifacts["capability"] == "shell_execution"
    assert store.load_approval("appr_1")["status"] == "executed"  # type: ignore[index]


# ── A2 — execution-time re-governance: disabled target gate is refused ───────


def test_relay_refuses_disabled_target_gate_and_releases(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    # The target capability's gate is disabled → it fails the gate closed at
    # execution time, proving the relay re-verifies the gate rather than trusting
    # the approval.
    _set_gate(store, "memory_write_execution", "disabled")
    _pending(
        store,
        approval_id="appr_1",
        action_id="act_1",
        tool_name="memory_write",
        arguments={"text": "note", "scope": "project"},
    )

    relay = ApprovalExecutionRelay(ws, store)
    result = relay.execute(_relay_action("appr_1"), _human(store))

    assert result.ok is False
    assert (result.reason_code or "").startswith("target_not_executed:")
    # Nothing ran, so the claim is released back to pending — a retry after the
    # owner enables the gate is safe.
    assert store.load_approval("appr_1")["status"] == "pending"  # type: ignore[index]


# ── A2 — single execution (pending → executing → executed) ───────────────────


def test_relay_executes_at_most_once(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    _set_gate(store, "file_write_execution", "enabled_runtime")
    _pending(store, approval_id="appr_1", action_id="act_1", arguments={"path": "once.txt", "text": "v1"})

    relay = ApprovalExecutionRelay(ws, store)
    first = relay.execute(_relay_action("appr_1"), _human(store))
    second = relay.execute(_relay_action("appr_1"), _human(store))

    assert first.ok is True
    assert second.ok is False
    assert second.reason_code == "approval_already_resolved"
    assert store.load_approval("appr_1")["status"] == "executed"  # type: ignore[index]


def test_relay_rejects_claimed_approval(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    _set_gate(store, "file_write_execution", "enabled_runtime")
    _pending(store, approval_id="appr_1", action_id="act_1", arguments={"path": "x.txt", "text": "v"})
    # Simulate a concurrent claim: the approval is already `executing`.
    assert store.claim_approval_for_execution("appr_1") is True

    relay = ApprovalExecutionRelay(ws, store)
    result = relay.execute(_relay_action("appr_1"), _human(store))
    assert result.ok is False
    assert result.reason_code == "approval_already_resolved"


# ── A2 — a relay may never execute another relay ─────────────────────────────


def test_relay_cannot_target_another_relay(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    _pending(
        store,
        approval_id="appr_1",
        action_id="act_1",
        tool_name="approval_execution_relay",
        arguments={"approval_id": "appr_other"},
    )

    relay = ApprovalExecutionRelay(ws, store)
    result = relay.execute(_relay_action("appr_1"), _human(store))
    assert result.ok is False
    assert result.reason_code == "relay_target_not_permitted"
    # Guard fires before the claim, so the approval is untouched.
    assert store.load_approval("appr_1")["status"] == "pending"  # type: ignore[index]


# ── A4 — posture snapshot on approval_executed + revoked-session denial ──────


def test_relay_emits_approval_executed_with_posture(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    _set_gate(store, "file_write_execution", "enabled_runtime")
    _pending(store, approval_id="appr_1", action_id="act_1", arguments={"path": "p.txt", "text": "c"})

    relay = ApprovalExecutionRelay(ws, store)
    relay.execute(_relay_action("appr_1"), _human(store))

    viewer = EventViewer(store)
    events = viewer.list_events(event_type="approval_executed")
    assert len(events) == 1
    payload = viewer.read_event_payload(events[0]["event_id"])
    assert payload is not None
    posture = payload["payload"]["posture"]
    assert posture["principal_id"] == "principal_owner"
    assert "mfa_enrolled" in posture
    assert posture["session_revoked"] is False


def test_relay_denies_revoked_session(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    _set_gate(store, "file_write_execution", "enabled_runtime")
    _pending(store, approval_id="appr_1", action_id="act_1", arguments={"path": "r.txt", "text": "c"})

    # The approving session is revoked between approval and execution.
    api_sessions = ApiSessionStore(ws)
    _token, session = api_sessions.create_session("principal_owner")
    api_sessions.revoke_session(session.session_id)

    relay = ApprovalExecutionRelay(ws, store)
    action = GovernedAction(
        action_id=new_id("act_"),
        principal_id="principal_owner",
        action_type="approval_execution_relay",
        tool_or_service_name="approval_execution_relay",
        arguments={"approval_id": "appr_1"},
        risk_level=RiskLevelValue.LOW,
        session_id=session.session_id,
    )
    result = relay.execute(action, _human(store))

    assert result.ok is False
    assert result.reason_code == "posture_degraded:session_revoked"
    assert not (ws / "r.txt").exists()
    # Denied before any claim, so the approval is still actionable later.
    assert store.load_approval("appr_1")["status"] == "pending"  # type: ignore[index]
