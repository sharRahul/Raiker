"""BUG-40 — the host control's API: state, pause, and a quit that warns first.

Two routes here stop or restart the process serving them, so the tests that
matter most are the ones that check they *don't*: an unauthenticated caller gets
nothing, a quit with work in flight reports the work instead of stopping, and a
restart on a host nothing would restart is refused with the reason said out loud.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.app.host import HostControl
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


@pytest.fixture
def app(client: TestClient) -> FastAPI:
    """The same app the client is driving, typed so `app.state` is readable."""
    application = client.app
    assert isinstance(application, FastAPI)
    return application


def _headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/session", json={"as_principal": None})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _block_a_run(workspace: Path, status: str = "running") -> None:
    store = SQLiteStore(workspace)
    store.create_session("sess_inbox_principal_owner", str(workspace))
    task = TaskManager(store, EventLogWriter(store)).create_task(
        session_id="sess_inbox_principal_owner", title="Long build", objective="Build",
    )
    store.update_task_status(task.task_id, status)


def test_the_host_view_needs_an_owner_session(client: TestClient) -> None:
    assert client.get("/api/host").status_code == 401


def test_the_host_answering_the_request_is_never_reported_as_stopped(client: TestClient) -> None:
    """A browser loaded *from this process* being told "stopped" is provably wrong."""
    body = client.get("/api/host", headers=_headers(client)).json()
    assert body["state"] == "running"
    assert body["pid"] is not None
    assert body["service"]["mechanism"]


def test_pause_and_resume_move_the_reported_state(client: TestClient, workspace: Path) -> None:
    headers = _headers(client)
    paused = client.post("/api/host/pause", headers=headers, json={"reason": "lunch"}).json()
    assert paused["ok"] and paused["state"] == "paused"
    assert paused["paused_reason"] == "lunch"
    assert HostControl(workspace).is_paused()

    resumed = client.post("/api/host/resume", headers=headers, json={}).json()
    assert resumed["ok"] and resumed["state"] == "running"
    assert not HostControl(workspace).is_paused()


def test_a_blocked_run_makes_the_host_report_needing_attention(
    client: TestClient, workspace: Path
) -> None:
    _block_a_run(workspace, "waiting_for_approval")
    body = client.get("/api/host", headers=_headers(client)).json()
    assert body["state"] == "needs attention"
    assert body["waiting"][0]["kind"] == "blocked_task"


def test_quit_reports_waiting_work_instead_of_stopping(
    client: TestClient, workspace: Path
) -> None:
    _block_a_run(workspace)
    body = client.post("/api/host/quit", headers=_headers(client), json={"confirm": False}).json()
    assert body["ok"] is False
    assert body["reason_code"] == "waiting_work"
    assert body["stopping"] is False
    assert body["waiting"][0]["label"] == "1 background run in flight"


def test_quit_with_nothing_in_flight_stops_without_a_second_press(client: TestClient) -> None:
    body = client.post("/api/host/quit", headers=_headers(client), json={"confirm": False}).json()
    assert body["ok"] is True and body["stopping"] is True
    assert body["waiting"] == []


def test_restart_is_refused_when_nothing_would_start_the_host_again(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from raiker.api import routes_host
    from raiker.app.service import ServiceRegistration

    monkeypatch.setattr(
        routes_host,
        "registration",
        lambda *_args, **_kwargs: ServiceRegistration(
            supported=True,
            registered=False,
            mechanism="Windows Task Scheduler",
            label="Raiker",
            path=str(tmp_path / "Raiker.xml"),
            note="",
        ),
    )
    response = client.post("/api/host/restart", headers=_headers(client), json={"confirm": True})
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["reason_code"] == "not_registered"
    assert "raiker-app service install" in detail["message"]


def test_restart_records_the_exit_status_the_service_manager_restarts_on(
    client: TestClient, app: FastAPI, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from raiker.api import routes_host
    from raiker.app.service import ServiceRegistration

    monkeypatch.setattr(
        routes_host,
        "registration",
        lambda *_args, **_kwargs: ServiceRegistration(
            supported=True,
            registered=True,
            mechanism="systemd --user",
            label="raiker.service",
            path=str(tmp_path / "raiker.service"),
            note="",
        ),
    )
    body = client.post("/api/host/restart", headers=_headers(client), json={"confirm": True}).json()
    assert body["ok"] is True and body["restarting"] is True
    assert app.state.exit_code == routes_host.RESTART_EXIT_CODE


def test_quit_and_pause_both_need_an_owner_session(client: TestClient) -> None:
    assert client.post("/api/host/pause", json={}).status_code == 401
    assert client.post("/api/host/quit", json={"confirm": True}).status_code == 401
    assert client.post("/api/host/restart", json={"confirm": True}).status_code == 401


# --- BUG-251: browsing for a folder instead of typing one ---------------------


def test_the_top_level_offers_somewhere_to_start(client: TestClient) -> None:
    """An empty path is the machine's top: its drives, and where things are kept."""
    response = client.get("/api/host/paths", headers=_headers(client))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["path"] == ""
    assert body["parent"] is None
    assert body["missing"] is False
    assert body["entries"], "the picker has to open somewhere"
    assert all(entry["is_directory"] for entry in body["entries"])
    # The workspace is first because it answers more of these fields than
    # anything else on the machine.
    assert body["entries"][0]["name"] == "Raiker workspace"
    assert body["workspace_root"] == body["entries"][0]["path"]


def test_a_directory_lists_its_folders_and_its_way_back(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "browse"
    (root / "src").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "notes.md").write_text("x", encoding="utf-8")

    response = client.get(
        "/api/host/paths", params={"path": str(root)}, headers=_headers(client)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert [entry["name"] for entry in body["entries"]] == ["docs", "src"]
    # Folders only unless a file is what the field wants: a folder picker that
    # lists files makes the owner scroll past everything they cannot choose.
    assert body["parent"] == str(root.parent)
    assert body["missing"] is False


def test_files_are_listed_only_when_the_field_wants_one(client: TestClient, tmp_path: Path) -> None:
    root = tmp_path / "withfiles"
    (root / "src").mkdir(parents=True)
    (root / "notes.md").write_text("x", encoding="utf-8")

    body = client.get(
        "/api/host/paths",
        params={"path": str(root), "files": "true"},
        headers=_headers(client),
    ).json()
    assert [entry["name"] for entry in body["entries"]] == ["src", "notes.md"]
    assert body["entries"][1]["is_directory"] is False


def test_a_location_that_is_gone_says_so_rather_than_looking_empty(
    client: TestClient, tmp_path: Path
) -> None:
    body = client.get(
        "/api/host/paths",
        params={"path": str(tmp_path / "never-existed")},
        headers=_headers(client),
    ).json()
    assert body["missing"] is True
    assert body["entries"] == []


def test_browsing_needs_the_owner_session_like_everything_else(client: TestClient) -> None:
    assert client.get("/api/host/paths").status_code == 401
