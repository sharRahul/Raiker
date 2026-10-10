from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import utc_now
from raiker.control.service import RuntimeControlService
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority import GovernedAction, RuntimeAuthority
from raiker.runtime.authority.models import Principal, RiskLevelValue
from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES, build_default_executor_registry
from raiker.runtime.executors.tier4_plugins import PluginInstallExecutor
from raiker.storage.sqlite import SQLiteStore
from tests.factories import governed_action, human

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
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    store = SQLiteStore(ws)
    with store.connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref) VALUES (?, ?, ?, ?)",
            (_CAP, "principal_owner", utc_now(), _DOC),
        )
    result = svc.set_capability_state(_CAP, "enabled_runtime", None, "test", confirmation_token="confirm")
    assert result.ok is True, result.reason_code


def _authority(ws: Path) -> tuple[RuntimeAuthority, Principal]:
    store = SQLiteStore(ws)
    authority = RuntimeAuthority(
        store, EventLogWriter(store), executor_registry=build_default_executor_registry(ws, store)
    )
    raw = store.get_principal("principal_owner")
    assert raw is not None
    return authority, Principal(**raw)


def _action(principal_id: str, **args: object) -> GovernedAction:
    return governed_action(
        _CAP,
        principal_id=principal_id,
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
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    # Default gates are enabled for integrated capabilities; disable this one to test the fail-closed path.
    RuntimeControlService(ws).disable_capability("plugin_install", None, "test")
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action(principal.principal_id, manifest_path=str(manifest_path.relative_to(ws))),
        principal,
    )
    assert result.decision == "disabled_by_capability_gate"
    assert SQLiteStore(ws).list_plugin_install_records() == []


def test_plugin_install_requires_threat_model_ack(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("owner", "Owner", workspace_root=ws)
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
        _action("principal_owner", manifest_path=str(outside)),
        human("principal_owner", role_ids=()),
    )
    assert result.ok is False
    assert result.reason_code == "outside_workspace:manifest_path"


# ── DEC-15 step 10: an update that grows authority waits for the owner ───────


def _install(ws: Path, manifest: dict[str, Any], name: str, **extra: object) -> Any:
    _write_manifest(ws, manifest, name)
    authority, principal = _authority(ws)
    return authority.route_action(
        _action(principal.principal_id, manifest_path=name, **extra), principal
    )


def test_an_update_asking_for_more_is_held_until_the_exact_set_is_accepted(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    first = _install(ws, _manifest(), "v1.json")
    assert first.message == "executed"
    assert first.artifacts["previous_version"] is None

    grown = _manifest({"version": "1.1.0", "permissions": ["tool:read_file", "tool:list_directory", "tool:grep"]})
    held = _install(ws, grown, "v2.json")
    assert held.error == "plugin_permissions_grew_unreviewed"
    assert held.artifacts["permissions_added"] == ["tool:grep"]
    assert held.artifacts["previous_version"] == "1.0.0"
    assert [r["version"] for r in SQLiteStore(ws).list_plugin_install_records()] == ["1.0.0"]

    # Accepting a different set than the manifest asks for is not accepting it.
    wrong = _install(ws, grown, "v2.json", accepted_permissions=["tool:read_file", "tool:grep"])
    assert wrong.error == "plugin_permissions_grew_unreviewed"

    accepted = _install(
        ws, grown, "v2.json",
        accepted_permissions=["tool:grep", "tool:list_directory", "tool:read_file"],
    )
    assert accepted.message == "executed"
    assert accepted.artifacts["permissions_added"] == ["tool:grep"]
    assert accepted.artifacts["previous_version"] == "1.0.0"


def test_an_update_that_asks_for_less_or_the_same_installs_without_a_second_question(
    tmp_path: Path,
) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    assert _install(ws, _manifest(), "v1.json").message == "executed"
    narrower = _manifest({"version": "1.0.1", "permissions": ["tool:read_file"]})
    result = _install(ws, narrower, "v2.json")
    assert result.message == "executed"
    assert result.artifacts["permissions_removed"] == ["tool:list_directory"]
    assert result.artifacts["permissions_added"] == []


def test_the_plan_reads_an_update_against_what_is_installed(tmp_path: Path) -> None:
    from raiker.cli.commands import handle_plugin_plan

    ws = _ws(tmp_path)
    _enable(ws)
    assert _install(ws, _manifest(), "v1.json").message == "executed"
    grown = _manifest({"version": "1.1.0", "permissions": ["tool:read_file", "tool:list_directory", "tool:grep"]})
    path = _write_manifest(ws, grown, "v2.json")

    shown = handle_plugin_plan(f"/plugin-plan {path}", workspace_root=ws)
    assert "updates_installed_version: 1.0.0" in shown
    assert "permissions_added: tool:grep" in shown
    assert "--accept-permissions" in shown

    held = handle_plugin_plan(f"/plugin-plan {path} --install", workspace_root=ws)
    assert "Install held: this update asks for tool:grep" in held

    installed = handle_plugin_plan(f"/plugin-plan {path} --install --accept-permissions", workspace_root=ws)
    assert "Installed:" in installed
