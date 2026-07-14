from __future__ import annotations

import json
from pathlib import Path

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id, utc_now
from raiker.control.service import RuntimeControlService
from raiker.events.query import EventViewer
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority import GovernedAction, RuntimeAuthority
from raiker.runtime.authority.models import Principal, RiskLevelValue
from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES, build_default_executor_registry
from raiker.storage.sqlite import SQLiteStore

_CAP = "reminder_runtime"
_DOC = "docs/threat-models/reminders.md"


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "reminders"
    ws.mkdir()
    return ws


def _enable(ws: Path) -> None:
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    store = SQLiteStore(ws)
    with store.connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref) VALUES (?, ?, ?, ?)",
            (_CAP, "principal_rahul", utc_now(), _DOC),
        )
    result = svc.set_capability_state(_CAP, "enabled_runtime", None, "test", confirmation_token="confirm")
    assert result.ok is True, result.reason_code


def _authority(ws: Path) -> tuple[RuntimeAuthority, Principal]:
    store = SQLiteStore(ws)
    authority = RuntimeAuthority(
        store, EventLogWriter(store), executor_registry=build_default_executor_registry(ws, store)
    )
    raw = store.get_principal("principal_rahul")
    assert raw is not None
    return authority, Principal(**raw)


def _action(principal_id: str, **args: object) -> GovernedAction:
    return GovernedAction(
        action_id=new_id("act_"),
        principal_id=principal_id,
        action_type=_CAP,
        tool_or_service_name=_CAP,
        arguments=dict(args),
        risk_level=RiskLevelValue.MEDIUM,
        session_id="sess_reminders",
    )


def test_reminder_is_real_executor_others_are_not(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    registry = build_default_executor_registry(ws, SQLiteStore(ws))
    assert _CAP in REAL_EXECUTOR_CAPABILITIES
    assert registry.has(_CAP)
    for other in ("finance_runtime", "medical_runtime", "cctv_runtime", "hardware_operator_runtime"):
        assert other not in REAL_EXECUTOR_CAPABILITIES
        assert not registry.has(other)


def test_reminder_gate_disabled_blocks(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    # reminder_runtime is integrated (enabled by default); disable it to test the fail-closed path.
    RuntimeControlService(ws).disable_capability("reminder_runtime", None, "test")
    authority, principal = _authority(ws)
    result = authority.route_action(_action(principal.principal_id, title="Call bank"), principal)
    assert result.decision == "disabled_by_capability_gate"
    assert SQLiteStore(ws).list_reminders() == []


def test_reminder_requires_threat_model_ack(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    result = svc.set_capability_state(_CAP, "enabled_runtime", None, "test", confirmation_token="confirm")
    assert result.ok is False
    assert "no_threat_model_ack" in (result.reason_code or "")


def test_reminder_create_writes_row_without_leaking_content(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action(principal.principal_id, title="Pay SECRETRENT", notes="acct SECRETNOTE", due_at="2026-08-01"),
        principal,
    )
    assert result.decision == "allow"
    assert result.message == "executed"

    store = SQLiteStore(ws)
    rows = store.list_reminders()
    assert len(rows) == 1
    assert rows[0]["title"] == "Pay SECRETRENT"
    assert rows[0]["status"] == "active"

    # Reminder title/notes must never leak into runtime event artifacts.
    events = EventViewer(store).list_events(event_type="action_executed")
    payload = EventViewer(store).read_event_payload(events[0]["event_id"])
    assert payload is not None
    dumped = json.dumps(payload)
    assert "SECRETRENT" not in dumped
    assert "SECRETNOTE" not in dumped
    assert payload["payload"]["artifacts"]["has_due_at"] is True


def test_reminder_missing_title_fails_closed(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    result = authority.route_action(_action(principal.principal_id, notes="no title"), principal)
    assert result.error == "missing_argument:title"
    assert SQLiteStore(ws).list_reminders() == []


def test_reminder_unknown_action_fails_closed(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    result = authority.route_action(_action(principal.principal_id, action="delete", title="x"), principal)
    assert result.error == "unknown_action:delete"


def test_reminder_list_returns_count_only(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    authority.route_action(_action(principal.principal_id, title="one"), principal)
    authority.route_action(_action(principal.principal_id, title="two"), principal)
    result = authority.route_action(_action(principal.principal_id, action="list"), principal)
    assert result.decision == "allow"
    viewer = EventViewer(SQLiteStore(ws))
    list_artifacts = None
    for ev in viewer.list_events(event_type="action_executed"):
        payload = viewer.read_event_payload(ev["event_id"])
        artifacts = (payload or {}).get("payload", {}).get("artifacts", {})
        if "count" in artifacts:
            list_artifacts = artifacts
    assert list_artifacts is not None
    assert list_artifacts["count"] == 2
    assert list_artifacts["content_redacted"] is True


def test_deliver_due_delivers_active_reminders(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    past = "2020-01-01T00:00:00Z"
    future = "2099-01-01T00:00:00Z"
    authority.route_action(_action(principal.principal_id, title="past", due_at=past), principal)
    authority.route_action(_action(principal.principal_id, title="future", due_at=future), principal)
    result = authority.route_action(_action(principal.principal_id, action="deliver_due"), principal)
    assert result.decision == "allow"
    store = SQLiteStore(ws)
    rows = store.list_reminders()
    delivered = [r for r in rows if r.get("delivery_status") == "delivered"]
    active = [r for r in rows if r.get("delivery_status") == "active"]
    assert len(delivered) == 1
    assert len(active) == 1


def test_deliver_due_fail_closed_when_gate_disabled(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    RuntimeControlService(ws).disable_capability("reminder_runtime", None, "test")
    authority, principal = _authority(ws)
    result = authority.route_action(_action(principal.principal_id, action="deliver_due"), principal)
    assert result.decision == "disabled_by_capability_gate"


def test_pause_and_cancel_reminder(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    result = authority.route_action(_action(principal.principal_id, title="test"), principal)
    assert result.decision == "allow"
    store = SQLiteStore(ws)
    rows = store.list_reminders()
    rid = str(rows[0]["reminder_id"])
    pause = authority.route_action(_action(principal.principal_id, action="pause", reminder_id=rid), principal)
    assert pause.decision == "allow"
    rows = store.list_reminders()
    assert rows[0]["delivery_status"] == "paused"
    cancel = authority.route_action(_action(principal.principal_id, action="cancel", reminder_id=rid), principal)
    assert cancel.decision == "allow"
    rows = store.list_reminders()
    assert rows[0]["delivery_status"] == "cancelled"


def test_pause_missing_reminder_id_fails(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    result = authority.route_action(_action(principal.principal_id, action="pause"), principal)
    assert result.error == "missing_argument:reminder_id"


def test_cancel_nonexistent_reminder_fails(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    result = authority.route_action(_action(principal.principal_id, action="cancel", reminder_id="rem_nonexistent"), principal)
    assert result.error == "reminder_not_found"


def test_retry_resets_failed_reminder(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    result = authority.route_action(_action(principal.principal_id, title="retry-me", due_at="2020-01-01T00:00:00Z"), principal)
    assert result.decision == "allow"
    store = SQLiteStore(ws)
    rows = store.list_reminders()
    rid = str(rows[0]["reminder_id"])
    deliver = authority.route_action(_action(principal.principal_id, action="deliver_due"), principal)
    assert deliver.decision == "allow"
    rows = store.list_reminders()
    assert rows[0]["delivery_status"] == "delivered"
    retry_res = authority.route_action(_action(principal.principal_id, action="retry", reminder_id=rid), principal)
    assert retry_res.decision == "allow"
    rows = store.list_reminders()
    assert rows[0]["delivery_status"] == "active"


def test_unknown_action_fails_closed(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    result = authority.route_action(_action(principal.principal_id, action="delete"), principal)
    assert result.error == "unknown_action:delete"
