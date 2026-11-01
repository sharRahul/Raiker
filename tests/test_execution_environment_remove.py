"""DEC-11 step 6 — removing a configured environment.

"Deletion requires no active references or an explicit migration choice." A
configured SSH, Daytona or container target could be turned off but never
removed, so a target the owner was done with stayed on the page for good. Now
it can be removed when nothing runs there, and when it is where work runs by
default only together with the owner's choice of where work runs instead. What
ran there is kept as evidence.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from raiker.control.dashboard import DashboardService
from tests.test_execution_environment_off import _FakeCommands, _ssh, owner  # noqa: F401


def _commands(monkeypatch: pytest.MonkeyPatch, runs: list[object]) -> _FakeCommands:
    from raiker.execution.commands import service as command_service

    fake = _FakeCommands(runs)  # type: ignore[arg-type]
    monkeypatch.setattr(
        command_service.CommandService, "for_workspace", classmethod(lambda cls, ws: fake)
    )
    return fake


def test_an_environment_nothing_uses_is_removed_and_its_history_kept(
    tmp_path: Path, owner: str, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    service = DashboardService(tmp_path)
    profile_id = _ssh(service, owner)
    _commands(monkeypatch, [SimpleNamespace(run_id="run_old", profile_id=profile_id, state="succeeded")])

    result = service.remove_execution_environment(profile_id, owner)

    assert result.ok, result.reason_code
    assert result.data == {
        "profile_id": profile_id, "removed": True, "name": "Build host", "selected_profile_id": None,
    }
    assert service.store.load_remote_execution_profile(profile_id, owner_principal_id=owner) is None
    assert all(
        item["profile_id"] != profile_id
        for item in service.execution_environments(owner)["environments"]
    )


def test_an_environment_with_commands_running_is_refused_with_the_count(
    tmp_path: Path, owner: str, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    service = DashboardService(tmp_path)
    profile_id = _ssh(service, owner)
    fake = _commands(monkeypatch, [
        SimpleNamespace(run_id="run_live", profile_id=profile_id, state="running"),
        SimpleNamespace(run_id="run_elsewhere", profile_id="local_native", state="running"),
    ])

    result = service.remove_execution_environment(profile_id, owner)

    assert not result.ok and result.reason_code == "execution_environment_in_use"
    assert result.data == {"running_commands": 1}
    assert fake.stopped == []  # removing never stops work; turning off does
    assert service.store.load_remote_execution_profile(profile_id, owner_principal_id=owner)


def test_the_default_environment_needs_somewhere_else_for_work_to_run(
    tmp_path: Path, owner: str, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    service = DashboardService(tmp_path)
    profile_id = _ssh(service, owner)
    service.store.select_execution_environment(owner, profile_id)
    _commands(monkeypatch, [])

    refused = service.remove_execution_environment(profile_id, owner)
    itself = service.remove_execution_environment(profile_id, owner, move_to=profile_id)
    unknown = service.remove_execution_environment(profile_id, owner, move_to="rex_nowhere")

    assert refused.reason_code == "execution_environment_selected"
    assert itself.reason_code == "execution_environment_move_to_itself"
    assert unknown.reason_code == "unknown_execution_environment"
    assert service.store.selected_execution_environment(owner) == profile_id

    moved = service.remove_execution_environment(profile_id, owner, move_to="native_sandbox")

    assert moved.ok, moved.reason_code
    assert moved.data["selected_profile_id"] == "native_sandbox"
    assert service.store.selected_execution_environment(owner) == "native_sandbox"
    assert service.store.load_remote_execution_profile(profile_id, owner_principal_id=owner) is None


def test_another_owner_cannot_remove_it(
    tmp_path: Path, owner: str, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    service = DashboardService(tmp_path)
    profile_id = _ssh(service, owner)
    _commands(monkeypatch, [])
    assert service.remove_execution_environment(profile_id, "principal_other").reason_code == (
        "unknown_execution_environment"
    )
    assert service.store.load_remote_execution_profile(profile_id, owner_principal_id=owner)


def test_the_route_answers_404_for_unknown_and_409_for_in_use(
    tmp_path: Path, owner: str, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    from raiker.api.app import create_app
    from raiker.api.sessions import ApiSessionStore

    service = DashboardService(tmp_path)
    profile_id = _ssh(service, owner)
    _commands(monkeypatch, [SimpleNamespace(run_id="r", profile_id=profile_id, state="running")])
    token, _ = ApiSessionStore(tmp_path).create_session(owner)
    client = TestClient(create_app(workspace_root=tmp_path))
    h = {"Authorization": f"Bearer {token}"}

    assert client.delete("/api/execution-environments/rex_missing", headers=h).status_code == 404
    busy = client.delete(f"/api/execution-environments/{profile_id}", headers=h)
    assert busy.status_code == 409
    assert busy.json()["detail"]["reason_code"] == "execution_environment_in_use"
