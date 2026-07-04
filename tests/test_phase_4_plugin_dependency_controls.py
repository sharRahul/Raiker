from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id, utc_now
from raiker.control.service import RuntimeControlService
from raiker.events.writer import EventLogWriter
from raiker.plugins.dependencies import (
    PLUGIN_DEPENDENCY_ALLOWLIST_ENV,
    plugin_dependency_allowlist,
    validate_plugin_dependencies,
)
from raiker.plugins.policy import plan_plugin_registration
from raiker.runtime.authority import GovernedAction, RuntimeAuthority
from raiker.runtime.authority.models import Principal, RiskLevelValue
from raiker.runtime.executors import build_default_executor_registry
from raiker.storage.sqlite import SQLiteStore

_ALLOW = frozenset({"dep.one", "dep.two"})


def _manifest(dependencies: object) -> dict[str, object]:
    manifest: dict[str, object] = {
        "plugin_id": "local.readonly",
        "name": "Local Read Only",
        "version": "1.0.0",
        "trust_level": "local_dev",
        "permissions": ["tool:read_file"],
        "dependencies": dependencies,
    }
    clean = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    manifest["supply_chain"] = {
        "checksum": hashlib.sha256(clean.encode("utf-8")).hexdigest(),
        "signature": "sig-marker",
    }
    return manifest


# ── Pure validator ───────────────────────────────────────────────────────────


def test_empty_or_missing_dependencies_accepted() -> None:
    assert validate_plugin_dependencies(_manifest([]), allowlist=frozenset()) == []
    manifest = _manifest([])
    del manifest["dependencies"]
    assert validate_plugin_dependencies(manifest, allowlist=frozenset()) == []


def test_pinned_and_allowlisted_dependency_accepted() -> None:
    manifest = _manifest([{"plugin_id": "dep.one", "version": "1.2.3"}, "dep.two==4.5.6"])
    assert validate_plugin_dependencies(manifest, allowlist=_ALLOW) == []


def test_unpinned_dependency_rejected() -> None:
    for version in (">=1.0.0", "^1.0.0", "~1.2", "1.*", "latest", ""):
        manifest = _manifest([{"plugin_id": "dep.one", "version": version}])
        reasons = validate_plugin_dependencies(manifest, allowlist=_ALLOW)
        assert reasons == ["dependency_unpinned:dep.one"], version


def test_bare_string_dependency_without_version_is_unpinned() -> None:
    manifest = _manifest(["dep.one"])
    assert validate_plugin_dependencies(manifest, allowlist=_ALLOW) == [
        "dependency_unpinned:dep.one"
    ]


def test_dependency_not_on_allowlist_rejected() -> None:
    manifest = _manifest([{"plugin_id": "dep.evil", "version": "1.0.0"}])
    assert validate_plugin_dependencies(manifest, allowlist=_ALLOW) == [
        "dependency_not_allowlisted:dep.evil"
    ]


def test_pinned_but_not_allowlisted_when_allowlist_empty() -> None:
    manifest = _manifest([{"plugin_id": "dep.one", "version": "1.0.0"}])
    assert validate_plugin_dependencies(manifest, allowlist=frozenset()) == [
        "dependency_not_allowlisted:dep.one"
    ]


def test_malformed_dependency_entry_rejected() -> None:
    for entry in (123, {"version": "1.0.0"}, {"plugin_id": "  "}):
        manifest = _manifest([entry])
        assert validate_plugin_dependencies(manifest, allowlist=_ALLOW) == [
            "invalid_dependency_entry"
        ]


def test_non_list_dependencies_rejected() -> None:
    assert validate_plugin_dependencies(_manifest("dep.one"), allowlist=_ALLOW) == [
        "invalid_dependencies"
    ]


def test_allowlist_env_defaults_empty_and_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(PLUGIN_DEPENDENCY_ALLOWLIST_ENV, raising=False)
    assert plugin_dependency_allowlist() == frozenset()
    monkeypatch.setenv(PLUGIN_DEPENDENCY_ALLOWLIST_ENV, "dep.one, dep.two ,")
    assert plugin_dependency_allowlist() == frozenset({"dep.one", "dep.two"})


# ── Enforcement through the install plan ─────────────────────────────────────


def test_plan_denies_manifest_with_unallowlisted_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(PLUGIN_DEPENDENCY_ALLOWLIST_ENV, raising=False)
    plan = plan_plugin_registration(_manifest([{"plugin_id": "dep.one", "version": "1.0.0"}]))
    assert plan.status == "denied"
    assert "dependency_not_allowlisted:dep.one" in plan.reasons


def test_plan_accepts_allowlisted_pinned_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PLUGIN_DEPENDENCY_ALLOWLIST_ENV, "dep.one")
    plan = plan_plugin_registration(_manifest([{"plugin_id": "dep.one", "version": "1.0.0"}]))
    assert plan.status == "planned"
    assert not any(r.startswith("dependency_") for r in plan.reasons)


# ── Enforcement through the governed plugin_install executor ─────────────────


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "plugin-deps"
    ws.mkdir()
    return ws


def _enable_install(ws: Path) -> None:
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    store = SQLiteStore(ws)
    with store.connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref) VALUES (?, ?, ?, ?)",
            ("plugin_install", "principal_rahul", utc_now(), "docs/threat-models/plugins.md"),
        )
    result = svc.set_capability_state(
        "plugin_install", "enabled_runtime", None, "test", confirmation_token="confirm"
    )
    assert result.ok is True, result.reason_code


def _install_action(principal_id: str, manifest_path: str) -> GovernedAction:
    return GovernedAction(
        action_id=new_id("act_"),
        principal_id=principal_id,
        action_type="plugin_install",
        tool_or_service_name="plugin_install",
        arguments={"manifest_path": manifest_path},
        risk_level=RiskLevelValue.MEDIUM,
        session_id="sess_plugin_install",
    )


def test_install_fails_closed_on_unallowlisted_dependency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(PLUGIN_DEPENDENCY_ALLOWLIST_ENV, raising=False)
    ws = _ws(tmp_path)
    _enable_install(ws)
    (ws / "manifest.json").write_text(
        json.dumps(_manifest([{"plugin_id": "dep.one", "version": "1.0.0"}])), encoding="utf-8"
    )
    store = SQLiteStore(ws)
    authority = RuntimeAuthority(
        store, EventLogWriter(store),
        executor_registry=build_default_executor_registry(ws, store),
    )
    raw = store.get_principal("principal_rahul")
    assert raw is not None
    result = authority.route_action(
        _install_action("principal_rahul", "manifest.json"), Principal(**raw)
    )
    assert result.error == "plugin_install_plan_not_approved:denied"
    assert store.list_plugin_install_records() == []


def test_install_succeeds_with_allowlisted_pinned_dependency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(PLUGIN_DEPENDENCY_ALLOWLIST_ENV, "dep.one")
    ws = _ws(tmp_path)
    _enable_install(ws)
    (ws / "manifest.json").write_text(
        json.dumps(_manifest([{"plugin_id": "dep.one", "version": "1.0.0"}])), encoding="utf-8"
    )
    store = SQLiteStore(ws)
    authority = RuntimeAuthority(
        store, EventLogWriter(store),
        executor_registry=build_default_executor_registry(ws, store),
    )
    raw = store.get_principal("principal_rahul")
    assert raw is not None
    result = authority.route_action(
        _install_action("principal_rahul", "manifest.json"), Principal(**raw)
    )
    assert result.decision == "allow"
    records = store.list_plugin_install_records(status="installed")
    assert len(records) == 1
    assert records[0]["plugin_id"] == "local.readonly"
