"""DEC-11 step 6 — turning a configured environment off stops what runs there.

There was no way to turn one off at all short of reconfiguring it, and nothing
would have stopped its running commands if there were. Off now means: nothing
new is placed there (resolution already refuses a disabled profile and never
falls back to the host), every command still running there is asked to stop
through the governed stop, and its runs, receipts and settings are kept.
"""

from __future__ import annotations

import base64
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from raiker.cli.principal_resolver import bootstrap_owner, resolve_local_principal
from raiker.control.dashboard import DashboardService


@pytest.fixture()
def owner(tmp_path: Path) -> str:
    (tmp_path / "config").mkdir(exist_ok=True)
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    principal, _ = resolve_local_principal(tmp_path, None)
    assert principal is not None
    return principal.principal_id


def _ssh(service: DashboardService, owner: str) -> str:
    from raiker.execution.commands.known_hosts import host_key_fingerprint

    key = "ssh-ed25519 " + base64.b64encode(b"test execution host key").decode()
    result = service.configure_execution_environment(
        profile_id=None, kind="ssh", name="Build host",
        config={
            "host": "build.example.com", "user": "raiker", "credential_env": "RAIKER_TEST_SSH_KEY",
            "host_public_key": key, "host_key_sha256": host_key_fingerprint(key),
        },
        enabled=True, owner_principal_id=owner,
    )
    assert result.ok, result.reason_code
    return str(result.data["profile_id"])


class _FakeCommands:
    def __init__(self, runs: list[Any]) -> None:
        self.store = SimpleNamespace(list_runs=lambda owner, limit=500: runs)
        self.stopped: list[str] = []

    def stop(self, owner: str, run_id: str) -> None:
        self.stopped.append(run_id)


def test_off_stops_the_commands_running_there_and_only_those(
    tmp_path: Path, owner: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from raiker.execution.commands import service as command_service

    service = DashboardService(tmp_path)
    profile_id = _ssh(service, owner)
    runs = [
        SimpleNamespace(run_id="run_here", profile_id=profile_id, state="running"),
        SimpleNamespace(run_id="run_done", profile_id=profile_id, state="succeeded"),
        SimpleNamespace(run_id="run_elsewhere", profile_id="local_native", state="running"),
    ]
    fake = _FakeCommands(runs)
    monkeypatch.setattr(command_service.CommandService, "for_workspace", classmethod(lambda cls, ws: fake))

    result = service.set_execution_environment_enabled(profile_id, False, owner)

    assert result.ok and result.data == {"profile_id": profile_id, "enabled": False, "stopped_runs": 1}
    assert fake.stopped == ["run_here"]
    environment = next(
        item for item in service.execution_environments(owner)["environments"]
        if item["profile_id"] == profile_id
    )
    assert environment["enabled"] is False and environment["status"] == "off"
    assert environment["available"] is False


def test_on_again_keeps_the_settings_and_stops_nothing(
    tmp_path: Path, owner: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from raiker.execution.commands import service as command_service

    service = DashboardService(tmp_path)
    profile_id = _ssh(service, owner)
    fake = _FakeCommands([])
    monkeypatch.setattr(command_service.CommandService, "for_workspace", classmethod(lambda cls, ws: fake))
    assert service.set_execution_environment_enabled(profile_id, False, owner).ok

    result = service.set_execution_environment_enabled(profile_id, True, owner)

    assert result.ok and result.data["stopped_runs"] == 0
    row = service.store.load_remote_execution_profile(profile_id, owner_principal_id=owner)
    assert row is not None and bool(row["enabled"]) and "build.example.com" in str(row["config_json"])


def test_an_off_environment_is_never_used_for_a_command(tmp_path: Path, owner: str) -> None:
    """Off is not a reason to run on the host instead."""
    from raiker.execution.profiles import resolve_command_environment

    service = DashboardService(tmp_path)
    profile_id = _ssh(service, owner)
    service.store.select_execution_environment(owner, profile_id)
    assert service.set_execution_environment_enabled(profile_id, False, owner).ok

    resolution = resolve_command_environment(service.store, owner, "shell")

    assert resolution.profile is None
    assert resolution.reason_code == "selected_environment_unavailable"


def test_another_owners_or_an_unknown_environment_is_refused(tmp_path: Path, owner: str) -> None:
    service = DashboardService(tmp_path)
    profile_id = _ssh(service, owner)
    assert service.set_execution_environment_enabled(profile_id, False, "principal_other").reason_code == (
        "unknown_execution_environment"
    )
    assert service.set_execution_environment_enabled("rex_missing", False, owner).ok is False
