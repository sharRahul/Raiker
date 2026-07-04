from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id, utc_now
from raiker.control.service import RuntimeControlService
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority import GovernedAction, RuntimeAuthority
from raiker.runtime.authority.models import Principal, PrincipalType, RiskLevelValue
from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES, build_default_executor_registry
from raiker.runtime.executors.tier4_plugins import PluginInstallExecutor
from raiker.storage.sqlite import SQLiteStore

_CAP = "plugin_install"
_EXEC_CAP = "plugin_execution_cap"
_DOC = "docs/threat-models/plugins.md"


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "plugins"
    ws.mkdir()
    return ws


def _manifest(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "plugin_id": "local.readonly",
        "name": "Local Readonly",
        "version": "1.0.0",
        "permissions": ["tool:read_file", "tool:list_directory"],
        "trust_level": "local_dev",
    }
    if overrides:
        manifest.update(overrides)
    clean = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    manifest["supply_chain"] = {
        "checksum": hashlib.sha256(clean.encode("utf-8")).hexdigest(),
        "signature": "test-signature-presence-marker",
    }
    return manifest


def _write_manifest(ws: Path, manifest: dict, name: str = "plugin.json") -> Path:
    path = ws / name
    path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    return path


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
    )


def test_plugin_install_and_brokered_execution_are_real_executors(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    registry = build_default_executor_registry(ws, SQLiteStore(ws))
    assert _CAP in REAL_EXECUTOR_CAPABILITIES
    assert registry.has(_CAP)
    assert _EXEC_CAP in REAL_EXECUTOR_CAPABILITIES
    assert registry.has(_EXEC_CAP)


def test_plugin_install_gate_disabled_blocks_before_recording(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    manifest_path = _write_manifest(ws, _manifest())
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action(principal.principal_id, manifest_path=str(manifest_path.relative_to(ws))),
        principal,
    )
    assert result.decision == "disabled_by_capability_gate"
    assert SQLiteStore(ws).list_plugin_install_records() == []


def test_plugin_install_requires_threat_model_ack(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    result = svc.set_capability_state(_CAP, "enabled_runtime", None, "test", confirmation_token="confirm")
    assert result.ok is False
    assert "no_threat_model_ack" in (result.reason_code or "")


def test_plugin_install_records_valid_manifest_without_enabling_execution(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    manifest_path = _write_manifest(ws, _manifest())
    _enable(ws)
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action(principal.principal_id, manifest_path=str(manifest_path.relative_to(ws))),
        principal,
    )
    assert result.decision == "allow"
    assert result.message == "executed"

    records = SQLiteStore(ws).list_plugin_install_records()
    assert len(records) == 1
    assert records[0]["plugin_id"] == "local.readonly"
    assert records[0]["version"] == "1.0.0"
    assert records[0]["status"] == "installed"
    assert records[0]["installed_by"] == principal.principal_id
    assert json.loads(records[0]["permissions_json"]) == ["tool:read_file", "tool:list_directory"]


def test_plugin_install_rejects_risky_permissions(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    manifest_path = _write_manifest(ws, _manifest({"permissions": ["network:https"]}))
    _enable(ws)
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action(principal.principal_id, manifest_path=str(manifest_path.relative_to(ws))),
        principal,
    )
    assert result.decision == "allow"
    assert result.error == "plugin_install_plan_not_approved:pending_approval"
    assert SQLiteStore(ws).list_plugin_install_records() == []


def test_plugin_install_rejects_bad_supply_chain(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    manifest = _manifest()
    manifest["supply_chain"]["checksum"] = "wrong"
    manifest_path = _write_manifest(ws, manifest)
    _enable(ws)
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action(principal.principal_id, manifest_path=str(manifest_path.relative_to(ws))),
        principal,
    )
    assert result.error == "plugin_install_plan_not_approved:denied"
    assert SQLiteStore(ws).list_plugin_install_records() == []


def test_plugin_install_rejects_paths_outside_workspace(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    outside = tmp_path / "outside-plugin.json"
    outside.write_text(json.dumps(_manifest()), encoding="utf-8")
    executor = PluginInstallExecutor(ws, SQLiteStore(ws))
    result = executor.execute(
        _action("principal_rahul", manifest_path=str(outside)),
        Principal(principal_id="principal_rahul", principal_type=PrincipalType.HUMAN, display_name="Rahul"),
    )
    assert result.ok is False
    assert result.reason_code == "outside_workspace:manifest_path"
