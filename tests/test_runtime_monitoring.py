from __future__ import annotations

import json
from pathlib import Path

import pytest

from raiker.security.monitoring import SecurityMonitor
from raiker.storage.sqlite import SQLiteStore


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "runtime-monitoring"
    workspace.mkdir()
    return workspace


def test_local_scan_records_only_redacted_pattern_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(tmp_path)
    (workspace / "settings.txt").write_text("api_key=sk-proj-ABCDEF1234567890", encoding="utf-8")
    monkeypatch.setenv("RAIKER_SECURITY_SCAN_PATHS", "settings.txt")
    store = SQLiteStore(workspace)

    findings = SecurityMonitor(store, workspace).scan_configured_paths("principal_owner")

    assert len(findings) == 1
    assert findings[0].code == "local_sensitive_pattern"
    dumped = json.dumps(store.list_security_findings("principal_owner"))
    assert "sk-proj" not in dumped
    assert "settings.txt" in dumped
    assert len(store.list_notifications("principal_owner")) == 1


def test_clean_rescan_resolves_a_prior_local_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(tmp_path)
    path = workspace / "settings.txt"
    path.write_text("api_key=sk-proj-ABCDEF1234567890", encoding="utf-8")
    monkeypatch.setenv("RAIKER_SECURITY_SCAN_PATHS", "settings.txt")
    store = SQLiteStore(workspace)
    monitor = SecurityMonitor(store, workspace)

    monitor.scan_configured_paths("principal_owner")
    path.write_text("feature_flag=true", encoding="utf-8")
    monitor.scan_configured_paths("principal_owner")

    assert store.list_security_findings("principal_owner")[0]["state"] == "resolved"
    assert [row["kind"] for row in store.list_notifications("principal_owner")] == [
        "security_recovered", "security_alert"
    ]


def test_breach_check_sends_only_sha1_prefix_and_offline_skip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(tmp_path)
    store = SQLiteStore(workspace)
    monkeypatch.setenv("RAIKER_SECURITY_BREACH_EGRESS_ALLOWLIST", "api.pwnedpasswords.com")
    urls: list[str] = []
    def http_get(url: str) -> str:
        urls.append(url)
        return "61DDCC5E8A2DABEDE0F3B482CD9AEA9434D:2"

    monitor = SecurityMonitor(store, workspace, http_get=http_get)

    assert monitor.check_password_breach("principal_owner", "hello", enabled=False) is None
    assert urls == []
    finding = monitor.check_password_breach("principal_owner", "hello", enabled=True)

    assert urls == ["https://api.pwnedpasswords.com/range/AAF4C"]
    assert finding is not None and finding.code == "breach_match"
    assert "hello" not in json.dumps(store.list_security_findings("principal_owner"))


def test_health_alert_is_deduplicated_then_recovery_is_recorded(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    store = SQLiteStore(workspace)
    monitor = SecurityMonitor(store, workspace)

    assert monitor.observe_health("principal_owner", "vault", healthy=False) is not None
    assert monitor.observe_health("principal_owner", "vault", healthy=False) is None
    assert monitor.observe_health("principal_owner", "vault", healthy=True) is None

    notifications = store.list_notifications("principal_owner")
    assert [row["kind"] for row in notifications] == ["security_recovered", "security_alert"]
