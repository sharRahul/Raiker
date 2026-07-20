"""Workstream F / Slice F7 (ZT-7) — critical approval lifecycle.

F7 replaces the router's old silent flat-deny of AI-proposed critical actions
with a parked approval whose resting state is deny:

    created → notified → (manual human decision) → deny | execute

These tests pin the whole lifecycle and its invariants:

* an AI-proposed critical action is *parked* (not executed) and the owner is
  notified; the parked approval carries the immutable intent + TTL;
* only a live human may resolve it — a non-human resolution attempt denies it;
* a human *reject*, a TTL *expiry*, a *tampered* payload, or a *revoked* session
  all resolve to deny, and never execute;
* a human *approve* (with step-up satisfied) executes the target through the
  Workstream A relay, re-governed at execution time;
* step-up: an MFA-enrolled human must present fresh verification before approval
  can execute — the approval stays pending until they do ("verify harder");
* no confirmation can smuggle a critical action past the floor: the relay alone
  cannot execute a critical approval, and an AI-forged confirmation is rejected.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id
from raiker.events.query import EventViewer
from raiker.events.writer import EventLogWriter
from raiker.notify.approval_notifier import CRITICAL_APPROVAL_PENDING_KIND
from raiker.runtime.authority.models import (
    Principal,
    PrincipalType,
    RiskLevelValue,
)
from raiker.runtime.authority.router import (
    CriticalConfirmation,
    GovernedAction,
    RuntimeAuthority,
)
from raiker.runtime.executors import build_default_executor_registry
from raiker.runtime.executors.tier1_approval import ApprovalExecutionRelay
from raiker.storage.sqlite import SQLiteStore


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    # Bootstrapping an owner account gives us a human principal (`principal_owner`)
    # and an instance owner for the async notification to reach.
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


def _authority(ws: Path, store: SQLiteStore) -> RuntimeAuthority:
    return RuntimeAuthority(
        store, EventLogWriter(store),
        executor_registry=build_default_executor_registry(ws, store),
    )


def _human(store: SQLiteStore) -> Principal:
    raw = store.get_principal("principal_owner")
    assert raw is not None
    return Principal(**raw)


def _ai() -> Principal:
    return Principal(
        principal_id="test_ai",
        principal_type=PrincipalType.AI_AGENT,
        display_name="AI",
        role_ids=("rl_assistant",),
        is_active=True,
    )


def _critical_write(principal_id: str, *, session_id: str = "sess_c") -> GovernedAction:
    """A write_file action declared CRITICAL — has a real executor, so approving
    it proves end-to-end execution (a file appears on disk)."""
    return GovernedAction(
        action_id=new_id("act_"),
        principal_id=principal_id,
        action_type="write_file",
        tool_or_service_name="write_file",
        arguments={"path": "secret.txt", "text": "launched"},
        risk_level=RiskLevelValue.CRITICAL,
        session_id=session_id,
    )


def _enroll_mfa(store: SQLiteStore, principal_id: str) -> None:
    # bootstrap_owner does not create an account_credentials row, so seed a
    # minimal MFA-enrolled credential the posture snapshot reads from. Seeding a
    # credential makes the principal a full account, so its capability gates then
    # resolve per-principal (fail-closed) — the caller must enable what it needs.
    now = "2026-07-20T00:00:00Z"
    with store.connect() as connection:
        connection.execute(
            """INSERT INTO account_credentials
               (principal_id, username, password_hash, hash_algo, mfa_enrolled, created_at, updated_at)
               VALUES (?, ?, ?, ?, 1, ?, ?)
               ON CONFLICT(principal_id) DO UPDATE SET mfa_enrolled = 1""",
            (principal_id, principal_id, "x", "argon2id", now, now),
        )


def _enable_principal_gate(store: SQLiteStore, principal_id: str, capability: str) -> None:
    now = "2026-07-20T00:00:00Z"
    store.upsert_principal_capability_gate_state(principal_id, {
        "capability": capability,
        "state": "enabled_runtime",
        "requested_by": principal_id,
        "requested_at": now,
        "activated_by": principal_id,
        "activated_at": now,
        "reason": "test",
        "readiness_snapshot_json": "",
        "created_at": now,
        "updated_at": now,
    })


# ── park + notify ────────────────────────────────────────────────────────────


def test_ai_critical_action_is_parked_and_owner_notified(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    authority = _authority(ws, store)

    result = authority.route_action(_critical_write("test_ai"), _ai())

    # Parked, not executed.
    assert result.decision == "needs_human_confirmation"
    assert result.message == "critical_action_parked_for_human"
    assert result.approval_id is not None
    assert not (ws / "secret.txt").exists()

    approval = store.load_approval(result.approval_id)
    assert approval is not None
    assert approval["status"] == "pending"
    assert approval["critical"] == 1
    # Immutable intent + bounded TTL captured at park time (A1 reused).
    assert approval["action_payload_sha256"] is not None
    assert approval["expires_at"] is not None

    # The owner got a distinct critical notification.
    notes = store.list_notifications("principal_owner")
    kinds = {n["kind"] for n in notes}
    assert CRITICAL_APPROVAL_PENDING_KIND in kinds

    # Lifecycle audit events: created → notified.
    viewer = EventViewer(store)
    assert len(viewer.list_events(event_type="critical_approval_created")) == 1
    assert len(viewer.list_events(event_type="critical_approval_notified")) == 1


# ── human approve → execute end-to-end ───────────────────────────────────────


def test_human_approve_executes_end_to_end(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    authority = _authority(ws, store)
    parked = authority.route_action(_critical_write("test_ai"), _ai())
    assert parked.approval_id is not None

    # The owner (human, no MFA → step-up vacuously satisfied) approves.
    result = authority.resolve_critical_approval(
        parked.approval_id, _human(store), approve=True
    )

    assert result.decision == "allow"
    assert result.message == "critical_action_executed"
    assert (ws / "secret.txt").read_text(encoding="utf-8") == "launched"
    assert store.load_approval(parked.approval_id)["status"] == "executed"  # type: ignore[index]

    viewer = EventViewer(store)
    resolved = viewer.list_events(event_type="critical_approval_resolved")
    assert len(resolved) == 1
    payload = viewer.read_event_payload(resolved[0]["event_id"])
    assert payload is not None
    body = payload["payload"]
    assert body["outcome"] == "approved"
    assert body["posture"]["principal_id"] == "principal_owner"


# ── only a human may resolve ─────────────────────────────────────────────────


def test_ai_cannot_resolve_critical(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    authority = _authority(ws, store)
    parked = authority.route_action(_critical_write("test_ai"), _ai())
    assert parked.approval_id is not None

    # An AI attempting to resolve resolves the action to deny (its resting state).
    result = authority.resolve_critical_approval(
        parked.approval_id, _ai(), approve=True, step_up_verified=True
    )
    assert result.decision == "deny"
    assert result.message == "only_human_may_resolve_critical"
    assert store.load_approval(parked.approval_id)["status"] == "denied"  # type: ignore[index]
    assert not (ws / "secret.txt").exists()


# ── manual reject → deny ─────────────────────────────────────────────────────


def test_human_reject_denies(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    authority = _authority(ws, store)
    parked = authority.route_action(_critical_write("test_ai"), _ai())
    assert parked.approval_id is not None

    result = authority.resolve_critical_approval(
        parked.approval_id, _human(store), approve=False, reason="not now"
    )
    assert result.decision == "deny"
    assert result.message == "critical_action_rejected"
    assert store.load_approval(parked.approval_id)["status"] == "denied"  # type: ignore[index]
    assert not (ws / "secret.txt").exists()


# ── TTL expiry → deny ────────────────────────────────────────────────────────


def test_expired_critical_approval_denies(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    authority = _authority(ws, store)
    parked = authority.route_action(_critical_write("test_ai"), _ai())
    assert parked.approval_id is not None

    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    with store.connect() as connection:
        connection.execute(
            "UPDATE approvals SET expires_at = ? WHERE approval_id = ?",
            (past, parked.approval_id),
        )

    result = authority.resolve_critical_approval(
        parked.approval_id, _human(store), approve=True
    )
    assert result.decision == "deny"
    assert result.message == "critical_approval_expired"
    assert store.load_approval(parked.approval_id)["status"] == "expired"  # type: ignore[index]
    assert not (ws / "secret.txt").exists()
    assert len(EventViewer(store).list_events(event_type="critical_approval_expired")) == 1


# ── tampered intent → deny ───────────────────────────────────────────────────


def test_tampered_critical_payload_denies(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    authority = _authority(ws, store)
    parked = authority.route_action(_critical_write("test_ai"), _ai())
    assert parked.approval_id is not None
    action_id = store.load_approval(parked.approval_id)["action_id"]  # type: ignore[index]

    # Drift the stored arguments after the approval hash was captured.
    with store.connect() as connection:
        connection.execute(
            "UPDATE tool_actions SET arguments_json = ? WHERE action_id = ?",
            ('{"path": "evil.txt", "text": "pwned"}', action_id),
        )

    result = authority.resolve_critical_approval(
        parked.approval_id, _human(store), approve=True
    )
    assert result.decision == "deny"
    assert result.message == "critical_approval_payload_tampered"
    assert not (ws / "secret.txt").exists()
    assert not (ws / "evil.txt").exists()


# ── revoked approving session → deny ─────────────────────────────────────────


def test_revoked_session_denies_resolution(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    authority = _authority(ws, store)
    parked = authority.route_action(_critical_write("test_ai"), _ai())
    assert parked.approval_id is not None

    api_sessions = ApiSessionStore(ws)
    _token, session = api_sessions.create_session("principal_owner")
    api_sessions.revoke_session(session.session_id)

    result = authority.resolve_critical_approval(
        parked.approval_id, _human(store), approve=True, session_id=session.session_id
    )
    assert result.decision == "deny"
    assert result.message == "posture_degraded:session_revoked"
    assert not (ws / "secret.txt").exists()
    # Denied before execution — the approval is still actionable from a good session.
    assert store.load_approval(parked.approval_id)["status"] == "pending"  # type: ignore[index]


# ── step-up: MFA-enrolled human must verify before approval executes ─────────


def test_step_up_required_for_mfa_enrolled_human(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    _enroll_mfa(store, "principal_owner")
    _enable_principal_gate(store, "principal_owner", "file_write_execution")
    authority = _authority(ws, store)
    parked = authority.route_action(_critical_write("test_ai"), _ai())
    assert parked.approval_id is not None

    # Approving without step-up parks it unchanged — verify harder, not deny.
    result = authority.resolve_critical_approval(
        parked.approval_id, _human(store), approve=True, step_up_verified=False
    )
    assert result.decision == "needs_step_up"
    assert result.message == "critical_approval_step_up_required"
    assert store.load_approval(parked.approval_id)["status"] == "pending"  # type: ignore[index]
    assert not (ws / "secret.txt").exists()

    # With step-up satisfied, the same approval executes.
    result2 = authority.resolve_critical_approval(
        parked.approval_id, _human(store), approve=True, step_up_verified=True
    )
    assert result2.decision == "allow"
    assert (ws / "secret.txt").exists()
    assert store.load_approval(parked.approval_id)["status"] == "executed"  # type: ignore[index]


# ── the relay alone cannot execute a critical approval ───────────────────────


def test_relay_cannot_execute_critical_without_confirmation(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    authority = _authority(ws, store)
    parked = authority.route_action(_critical_write("test_ai"), _ai())
    assert parked.approval_id is not None

    # Drive the relay directly (as a human) with NO critical confirmation: the
    # re-governed target re-classifies as critical and is parked again, never run.
    relay = ApprovalExecutionRelay(ws, store)
    action = GovernedAction(
        action_id=new_id("act_"),
        principal_id="principal_owner",
        action_type="approval_execution_relay",
        tool_or_service_name="approval_execution_relay",
        arguments={"approval_id": parked.approval_id},
        risk_level=RiskLevelValue.LOW,
    )
    result = relay.execute(action, _human(store))

    assert result.ok is False
    assert result.reason_code == "critical_approval_requires_lifecycle"
    assert not (ws / "secret.txt").exists()
    # The relay refused before claiming — the critical approval is untouched.
    assert store.load_approval(parked.approval_id)["status"] == "pending"  # type: ignore[index]


def test_ai_forged_confirmation_is_rejected(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    authority = _authority(ws, store)
    parked = authority.route_action(_critical_write("test_ai"), _ai())
    assert parked.approval_id is not None

    # An AI hand-crafts a confirmation and re-proposes the critical action: the
    # human-principal check fails, so it is parked again — never executed.
    forged = CriticalConfirmation(
        approval_id=parked.approval_id, confirmed_by="test_ai", step_up_verified=True
    )
    forged_action = GovernedAction(
        action_id=new_id("act_"),
        principal_id="test_ai",
        action_type="write_file",
        tool_or_service_name="write_file",
        arguments={"path": "secret.txt", "text": "launched"},
        risk_level=RiskLevelValue.CRITICAL,
        critical_confirmation=forged,
    )
    result = authority.route_action(forged_action, _ai())
    assert result.decision == "needs_human_confirmation"
    assert result.message == "critical_action_parked_for_human"
    assert not (ws / "secret.txt").exists()


# ── double resolution is refused ─────────────────────────────────────────────


def test_already_resolved_critical_is_refused(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    authority = _authority(ws, store)
    parked = authority.route_action(_critical_write("test_ai"), _ai())
    assert parked.approval_id is not None

    first = authority.resolve_critical_approval(parked.approval_id, _human(store), approve=True)
    assert first.decision == "allow"
    second = authority.resolve_critical_approval(parked.approval_id, _human(store), approve=True)
    assert second.decision == "deny"
    assert second.message == "approval_already_resolved"
