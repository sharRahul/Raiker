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


def _ws(tmp_path: Path, name: str) -> Path:
    ws = tmp_path / name
    ws.mkdir()
    return ws


def _enable(ws: Path, cap: str, doc: str) -> None:
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    store = SQLiteStore(ws)
    with store.connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref) VALUES (?, ?, ?, ?)",
            (cap, "principal_rahul", utc_now(), doc),
        )
    result = svc.set_capability_state(cap, "enabled_runtime", None, "test", confirmation_token="confirm")
    assert result.ok is True, result.reason_code


def _authority(ws: Path) -> tuple[RuntimeAuthority, Principal]:
    store = SQLiteStore(ws)
    authority = RuntimeAuthority(
        store, EventLogWriter(store), executor_registry=build_default_executor_registry(ws, store)
    )
    raw = store.get_principal("principal_rahul")
    assert raw is not None
    return authority, Principal(**raw)


def _action(cap: str, principal_id: str, **args: object) -> GovernedAction:
    return GovernedAction(
        action_id=new_id("act_"),
        principal_id=principal_id,
        action_type=cap,
        tool_or_service_name=cap,
        arguments=dict(args),
        risk_level=RiskLevelValue.MEDIUM,
        session_id="sess_local_tier6",
    )


# ── Calendar ─────────────────────────────────────────────────────────────────


def test_calendar_is_real_executor(tmp_path: Path) -> None:
    ws = _ws(tmp_path, "cal-real")
    registry = build_default_executor_registry(ws, SQLiteStore(ws))
    assert "calendar_runtime" in REAL_EXECUTOR_CAPABILITIES
    assert registry.has("calendar_runtime")


def test_calendar_gate_disabled_blocks(tmp_path: Path) -> None:
    ws = _ws(tmp_path, "cal-gate")
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    authority, principal = _authority(ws)
    result = authority.route_action(_action("calendar_runtime", principal.principal_id, title="Standup"), principal)
    assert result.decision == "disabled_by_capability_gate"


def test_calendar_create_and_no_content_leak(tmp_path: Path) -> None:
    ws = _ws(tmp_path, "cal-create")
    _enable(ws, "calendar_runtime", "docs/threat-models/calendar.md")
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action("calendar_runtime", principal.principal_id, title="SECRETMEETING", starts_at="2026-08-01T10:00", location="SECRETPLACE"),
        principal,
    )
    assert result.message == "executed"
    store = SQLiteStore(ws)
    assert store.list_calendar_events()[0]["title"] == "SECRETMEETING"
    events = EventViewer(store).list_events(event_type="action_executed")
    dumped = json.dumps(EventViewer(store).read_event_payload(events[0]["event_id"]))
    assert "SECRETMEETING" not in dumped and "SECRETPLACE" not in dumped


def test_calendar_missing_title_and_unknown_action(tmp_path: Path) -> None:
    ws = _ws(tmp_path, "cal-fail")
    _enable(ws, "calendar_runtime", "docs/threat-models/calendar.md")
    authority, principal = _authority(ws)
    assert authority.route_action(_action("calendar_runtime", principal.principal_id, starts_at="x"), principal).error == "missing_argument:title"
    assert authority.route_action(_action("calendar_runtime", principal.principal_id, action="delete", title="x"), principal).error == "unknown_action:delete"


# ── Email ────────────────────────────────────────────────────────────────────


def test_email_is_real_executor(tmp_path: Path) -> None:
    ws = _ws(tmp_path, "eml-real")
    registry = build_default_executor_registry(ws, SQLiteStore(ws))
    assert "email_runtime" in REAL_EXECUTOR_CAPABILITIES
    assert registry.has("email_runtime")


def test_email_drafts_locally_never_sends(tmp_path: Path) -> None:
    ws = _ws(tmp_path, "eml-draft")
    _enable(ws, "email_runtime", "docs/threat-models/email.md")
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action("email_runtime", principal.principal_id, subject="SECRETSUBJ", recipients="a@b.com", body="SECRETBODY"),
        principal,
    )
    assert result.message == "executed"
    store = SQLiteStore(ws)
    drafts = store.list_email_drafts()
    assert len(drafts) == 1 and drafts[0]["status"] == "draft"
    events = EventViewer(store).list_events(event_type="action_executed")
    dumped = json.dumps(EventViewer(store).read_event_payload(events[0]["event_id"]))
    assert "SECRETSUBJ" not in dumped and "SECRETBODY" not in dumped


def test_email_send_is_refused(tmp_path: Path) -> None:
    ws = _ws(tmp_path, "eml-send")
    _enable(ws, "email_runtime", "docs/threat-models/email.md")
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action("email_runtime", principal.principal_id, action="send", subject="hi"),
        principal,
    )
    assert result.error == "send_not_supported:local_draft_only"


def test_email_missing_subject_fails_closed(tmp_path: Path) -> None:
    ws = _ws(tmp_path, "eml-fail")
    _enable(ws, "email_runtime", "docs/threat-models/email.md")
    authority, principal = _authority(ws)
    assert authority.route_action(_action("email_runtime", principal.principal_id, body="no subject"), principal).error == "missing_argument:subject"
    assert SQLiteStore(ws).list_email_drafts() == []
