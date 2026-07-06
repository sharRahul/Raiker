from __future__ import annotations

from pathlib import Path

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id, utc_now
from raiker.control.service import RuntimeControlService
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority import GovernedAction, RuntimeAuthority
from raiker.runtime.authority.models import Principal, RiskLevelValue
from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES, build_default_executor_registry
from raiker.storage.sqlite import SQLiteStore

_CAP = "scheduled_routines"


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "sched"
    ws.mkdir()
    (ws / "hello.txt").write_text("hi", encoding="utf-8")
    return ws


def _enable(ws: Path) -> None:
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    store = SQLiteStore(ws)
    with store.connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref) VALUES (?, ?, ?, ?)",
            (_CAP, "principal_rahul", utc_now(), "docs/threat-models/scheduled-routines.md"),
        )
    result = svc.set_capability_state(_CAP, "enabled_runtime", None, "test", confirmation_token="confirm")
    assert result.ok is True, result.reason_code


def _authority(ws: Path) -> tuple[RuntimeAuthority, Principal]:
    store = SQLiteStore(ws)
    authority = RuntimeAuthority(store, EventLogWriter(store), executor_registry=build_default_executor_registry(ws, store))
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
    )


_READONLY_PAYLOAD = {"name": "scout", "steps": [{"tool_name": "read_file", "arguments": {"path": "hello.txt"}}]}


def test_scheduled_cap_is_real_executor(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    registry = build_default_executor_registry(ws, SQLiteStore(ws))
    assert _CAP in REAL_EXECUTOR_CAPABILITIES
    assert registry.has(_CAP)


def test_scheduled_fail_closed_when_gate_disabled(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    # Default gates are enabled for integrated capabilities; disable this one to test the fail-closed path.
    RuntimeControlService(ws).disable_capability("scheduled_routines", None, "test")
    authority, principal = _authority(ws)
    result = authority.route_action(_action(principal.principal_id, operation="run_due"), principal)
    assert result.decision == "disabled_by_capability_gate"


def test_define_and_run_due(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    define = authority.route_action(
        _action(principal.principal_id, operation="define", name="scout",
                interval_seconds=60, enabled=True, payload=_READONLY_PAYLOAD),
        principal,
    )
    assert define.decision == "allow" and define.message == "executed"
    routines = SQLiteStore(ws).list_scheduled_routines()
    assert routines and routines[0]["enabled"] == 1

    run = authority.route_action(_action(principal.principal_id, operation="run_due"), principal)
    assert run.decision == "allow" and run.message == "executed"
    # last_run is set after a tick.
    assert SQLiteStore(ws).list_scheduled_routines()[0]["last_run"] is not None


def test_interval_too_small(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action(principal.principal_id, operation="define", name="x", interval_seconds=5, payload=_READONLY_PAYLOAD),
        principal,
    )
    assert result.error is not None and result.error.startswith("interval_too_small")


def test_define_requires_payload(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action(principal.principal_id, operation="define", name="x", interval_seconds=60),
        principal,
    )
    assert result.error == "missing_argument:payload"


def test_run_due_fails_closed_on_mutating_routine(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    mutating = {"name": "bad", "steps": [{"tool_name": "write_file", "arguments": {"path": "x", "text": "no"}}]}
    authority.route_action(
        _action(principal.principal_id, operation="define", name="bad",
                interval_seconds=60, enabled=True, payload=mutating),
        principal,
    )
    run = authority.route_action(_action(principal.principal_id, operation="run_due"), principal)
    # The tick executed, but the routine's subagent fails closed on the mutating tool.
    assert run.error is not None and run.error.startswith("subagent_tool_not_allowed")
    assert not (ws / "x").exists()


def test_unknown_operation(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    result = authority.route_action(_action(principal.principal_id, operation="frobnicate"), principal)
    assert result.error is not None and result.error.startswith("unknown_operation")
