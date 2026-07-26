"""Build workspace: repository references and recurring agent cadences.

The Build page lets a coding conversation point at a repository and lets a
scheduled agent keep working in the background. Neither is a new authority, and
these tests hold that line:

* A *reference* is not access. A local folder must resolve inside the workspace
  (anything else fails closed), a GitHub coordinate is recorded without any
  network call, and neither stores a credential. Reads against a connected
  GitHub repository still run through the brokered ``github_read`` tool under the
  ``connector_github_runtime`` gate, so the listing reports the gate's real
  posture rather than implying the connection granted anything.
* References are per account, and one account can never see, select, or
  disconnect another's.
* A recurring agent re-arms after each governed cycle instead of closing, and an
  unknown cadence is refused rather than silently degraded to a one-shot — which
  would make a "keep going" schedule stop after its first run.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control.dashboard import DashboardService
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager
from raiker.tasks.scheduler import RECURRING_INTERVALS, TaskScheduler, next_run_after

OWNER = "principal_owner"
REPO_KEYS = {
    "repo_id", "kind", "label", "selected", "created_at", "local_subpath",
    "local_exists", "github_owner", "github_repo", "branch",
}
VIEW_KEYS = {
    "repos", "selected_repo_id", "github_gate_state", "github_decision_mode",
    "github_token_configured", "note",
}


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    (ws / "projects").mkdir()
    (ws / "projects" / "my-app").mkdir()
    return ws


@pytest.fixture
def service(workspace: Path) -> DashboardService:
    return DashboardService(workspace)


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


def _headers(client: TestClient) -> dict[str, str]:
    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


class TestConnectLocalRepository:
    def test_connects_a_workspace_contained_folder(
        self, service: DashboardService
    ) -> None:
        result = service.connect_local_repo("projects/my-app", owner_principal_id=OWNER)
        assert result.ok, result.reason_code
        assert result.data["local_subpath"] == "projects/my-app"

        view = service.list_code_repos(owner_principal_id=OWNER)
        assert [repo.label for repo in view.repos] == ["my-app"]
        assert view.repos[0].local_exists is True

    @pytest.mark.parametrize(
        ("path", "reason"),
        [
            ("../outside", "repo_outside_workspace"),
            ("/etc", "repo_outside_workspace"),
            ("projects/absent", "repo_not_found"),
            ("", "invalid_repo_path"),
        ],
    )
    def test_paths_that_escape_or_do_not_exist_fail_closed(
        self, service: DashboardService, path: str, reason: str
    ) -> None:
        result = service.connect_local_repo(path, owner_principal_id=OWNER)
        assert not result.ok
        assert result.reason_code == reason

    def test_a_file_is_refused_because_a_repository_is_a_folder(
        self, service: DashboardService, workspace: Path
    ) -> None:
        (workspace / "projects" / "notes.md").write_text("hello", encoding="utf-8")
        result = service.connect_local_repo("projects/notes.md", owner_principal_id=OWNER)
        assert not result.ok
        assert result.reason_code == "repo_not_a_directory"

    def test_connecting_the_same_folder_twice_is_refused(
        self, service: DashboardService
    ) -> None:
        assert service.connect_local_repo("projects/my-app", owner_principal_id=OWNER).ok
        second = service.connect_local_repo("projects/my-app", owner_principal_id=OWNER)
        assert not second.ok
        assert second.reason_code == "repo_already_connected"

    def test_a_folder_deleted_after_connecting_reports_itself_missing(
        self, service: DashboardService, workspace: Path
    ) -> None:
        # The reference outlives the folder, so the listing must say so rather
        # than presenting a path that is no longer there.
        service.connect_local_repo("projects/my-app", owner_principal_id=OWNER)
        (workspace / "projects" / "my-app").rmdir()
        view = service.list_code_repos(owner_principal_id=OWNER)
        assert view.repos[0].local_exists is False


class TestConnectGithubRepository:
    def test_records_the_coordinate_without_reaching_the_network(
        self, service: DashboardService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A connect that quietly made an HTTP call would bypass the connector
        # gate entirely, so any outbound attempt must fail the test.
        import httpx

        def _forbidden(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("connecting a repository must not reach the network")

        monkeypatch.setattr(httpx.Client, "request", _forbidden)
        monkeypatch.setattr(httpx.AsyncClient, "request", _forbidden)

        result = service.connect_github_repo("octo", "app", "main", owner_principal_id=OWNER)
        assert result.ok, result.reason_code
        assert result.data["label"] == "octo/app"

        repo = service.list_code_repos(owner_principal_id=OWNER).repos[0]
        assert (repo.github_owner, repo.github_repo, repo.branch) == ("octo", "app", "main")
        assert repo.local_subpath is None

    @pytest.mark.parametrize(
        ("owner", "repo"),
        [
            ("bad owner", "app"),
            ("octo", "app/../etc"),
            ("", "app"),
            ("octo", ""),
            ("-leading", "app"),
            ("octo", "a" * 200),
        ],
    )
    def test_malformed_coordinates_are_refused(
        self, service: DashboardService, owner: str, repo: str
    ) -> None:
        result = service.connect_github_repo(owner, repo, None, owner_principal_id=OWNER)
        assert not result.ok
        assert result.reason_code == "invalid_github_repo"

    def test_a_malformed_branch_is_refused(self, service: DashboardService) -> None:
        result = service.connect_github_repo("octo", "app", "bad branch", owner_principal_id=OWNER)
        assert not result.ok
        assert result.reason_code == "invalid_github_branch"

    def test_the_listing_reports_the_connector_gate_rather_than_implying_access(
        self, service: DashboardService
    ) -> None:
        service.connect_github_repo("octo", "app", None, owner_principal_id=OWNER)
        view = service.list_code_repos(owner_principal_id=OWNER)
        gate = service.control.get_capability_gate("connector_github_runtime", OWNER)
        assert gate is not None
        assert view.github_gate_state == gate.state
        assert view.github_decision_mode == gate.decision_mode
        assert "grants no capability" in view.note
        assert "fails closed" in view.note


class TestSelectionAndRemoval:
    def test_selecting_replaces_the_previous_selection(
        self, service: DashboardService
    ) -> None:
        first = service.connect_local_repo("projects/my-app", owner_principal_id=OWNER).data["repo_id"]
        second = service.connect_github_repo("octo", "app", None, owner_principal_id=OWNER).data["repo_id"]

        service.select_code_repo(first, owner_principal_id=OWNER)
        service.select_code_repo(second, owner_principal_id=OWNER)

        view = service.list_code_repos(owner_principal_id=OWNER)
        assert view.selected_repo_id == second
        assert [repo.repo_id for repo in view.repos if repo.selected] == [second]

    def test_selection_can_be_cleared(self, service: DashboardService) -> None:
        repo_id = service.connect_local_repo("projects/my-app", owner_principal_id=OWNER).data["repo_id"]
        service.select_code_repo(repo_id, owner_principal_id=OWNER)
        assert service.select_code_repo(None, owner_principal_id=OWNER).ok
        assert service.list_code_repos(owner_principal_id=OWNER).selected_repo_id is None

    def test_selecting_an_unknown_repository_is_refused(
        self, service: DashboardService
    ) -> None:
        result = service.select_code_repo("repo_missing", owner_principal_id=OWNER)
        assert not result.ok
        assert result.reason_code == "unknown_repo"

    def test_disconnecting_forgets_the_reference_and_leaves_the_folder(
        self, service: DashboardService, workspace: Path
    ) -> None:
        repo_id = service.connect_local_repo("projects/my-app", owner_principal_id=OWNER).data["repo_id"]
        assert service.disconnect_code_repo(repo_id, owner_principal_id=OWNER).ok
        assert service.list_code_repos(owner_principal_id=OWNER).repos == ()
        assert (workspace / "projects" / "my-app").is_dir()

    def test_connect_and_disconnect_are_audited(self, service: DashboardService) -> None:
        repo_id = service.connect_local_repo("projects/my-app", owner_principal_id=OWNER).data["repo_id"]
        service.disconnect_code_repo(repo_id, owner_principal_id=OWNER)
        recorded = [
            event.event_type
            for event in service.list_events(limit=100)
            if event.event_type.startswith("code_repo_")
        ]
        assert "code_repo_connected" in recorded
        assert "code_repo_disconnected" in recorded


class TestAccountIsolation:
    def test_one_account_cannot_see_or_touch_another_s_references(
        self, service: DashboardService
    ) -> None:
        mine = service.connect_local_repo("projects/my-app", owner_principal_id=OWNER).data["repo_id"]

        assert service.list_code_repos(owner_principal_id="principal_other").repos == ()
        assert service.disconnect_code_repo(mine, owner_principal_id="principal_other").reason_code == (
            "unknown_repo"
        )
        assert service.select_code_repo(mine, owner_principal_id="principal_other").reason_code == (
            "unknown_repo"
        )
        # The other account's failed attempts left the real owner's reference alone.
        assert len(service.list_code_repos(owner_principal_id=OWNER).repos) == 1


class TestRepositoryRoutes:
    def test_the_rest_surface_round_trips_a_reference(self, client: TestClient) -> None:
        headers = _headers(client)

        empty = client.get("/api/code/repos", headers=headers)
        assert empty.status_code == 200
        assert set(empty.json()) == VIEW_KEYS
        assert empty.json()["repos"] == []

        created = client.post(
            "/api/code/repos", json={"kind": "local", "path": "projects/my-app"}, headers=headers
        )
        assert created.status_code == 201, created.text
        repo_id = created.json()["repo_id"]

        listed = client.get("/api/code/repos", headers=headers).json()
        assert set(listed["repos"][0]) == REPO_KEYS

        assert client.put(
            "/api/code/repos/selection", json={"repo_id": repo_id}, headers=headers
        ).status_code == 200
        assert client.get("/api/code/repos", headers=headers).json()["selected_repo_id"] == repo_id

        assert client.delete(f"/api/code/repos/{repo_id}", headers=headers).status_code == 200
        assert client.get("/api/code/repos", headers=headers).json()["repos"] == []

    def test_a_traversal_path_is_refused_with_a_reason_code(self, client: TestClient) -> None:
        response = client.post(
            "/api/code/repos", json={"kind": "local", "path": "../../etc"}, headers=_headers(client)
        )
        assert response.status_code == 422
        assert response.json()["detail"]["reason_code"] == "repo_outside_workspace"

    def test_missing_fields_are_refused_per_kind(self, client: TestClient) -> None:
        headers = _headers(client)
        assert client.post("/api/code/repos", json={"kind": "local"}, headers=headers).json()[
            "detail"
        ]["reason_code"] == "repo_path_required"
        assert client.post("/api/code/repos", json={"kind": "github", "owner": "octo"}, headers=headers).json()[
            "detail"
        ]["reason_code"] == "github_owner_and_repo_required"

    def test_an_unknown_kind_is_rejected_by_the_schema(self, client: TestClient) -> None:
        response = client.post(
            "/api/code/repos", json={"kind": "gitlab", "path": "x"}, headers=_headers(client)
        )
        assert response.status_code == 422

    def test_the_reference_carries_no_credential(self, client: TestClient) -> None:
        headers = _headers(client)
        client.post("/api/code/repos", json={"kind": "github", "owner": "octo", "repo": "app"}, headers=headers)
        body = client.get("/api/code/repos", headers=headers).text.lower()
        for marker in ("token", "secret", "password", "api_key"):
            # `github_token_configured` is a boolean *about* the environment, not
            # a value, and is the only token-shaped key allowed through.
            assert marker not in body.replace("github_token_configured", "")

    def test_the_routes_require_authentication(self, client: TestClient) -> None:
        assert client.get("/api/code/repos").status_code == 401
        assert client.post("/api/code/repos", json={"kind": "local", "path": "x"}).status_code == 401


class TestAgentCadences:
    def test_an_unknown_cadence_is_refused_rather_than_degraded_to_one_shot(
        self, service: DashboardService
    ) -> None:
        with pytest.raises(ValueError, match="invalid_recurrence:fortnightly"):
            service.create_task(
                title="Watch the build",
                objective="Report failures",
                user_id=None,
                principal_id=OWNER,
                recurrence="fortnightly",
            )

    @pytest.mark.parametrize("recurrence", sorted({"background", *RECURRING_INTERVALS}))
    def test_every_offered_cadence_is_accepted(
        self, service: DashboardService, recurrence: str
    ) -> None:
        view = service.create_task(
            title=f"Agent {recurrence}",
            objective="Keep working",
            user_id=None,
            principal_id=OWNER,
            recurrence=recurrence,
        )
        assert view.recurrence == recurrence

    def test_the_route_reports_an_unknown_cadence_as_a_reason_code(
        self, client: TestClient
    ) -> None:
        response = client.post(
            "/api/tasks",
            json={"title": "Agent", "description": "Work", "recurrence": "sometimes"},
            headers=_headers(client),
        )
        assert response.status_code == 422
        assert response.json()["detail"]["reason_code"] == "invalid_recurrence:sometimes"

    def test_the_next_run_skips_every_elapsed_slot(self) -> None:
        # A host that was asleep must not wake up owing a backlog of identical
        # runs, so the next slot is the first one still in the future.
        nxt = next_run_after("2020-01-01T09:00:00Z", timedelta(hours=1))
        assert datetime.fromisoformat(nxt.replace("Z", "+00:00")) > datetime.now(UTC)

    def test_the_next_run_stays_anchored_to_the_chosen_time(self) -> None:
        # Stepping forward from the original slot (rather than from "now") keeps
        # a daily agent at the time the owner picked.
        original = datetime(2020, 1, 1, 9, 30, tzinfo=UTC)
        nxt = datetime.fromisoformat(
            next_run_after(original.isoformat().replace("+00:00", "Z"), timedelta(days=1)).replace(
                "Z", "+00:00"
            )
        )
        assert (nxt.hour, nxt.minute) == (9, 30)


class TestRecurringAgentReArms:
    @pytest.mark.parametrize("recurrence", sorted(RECURRING_INTERVALS))
    def test_a_recurring_agent_is_queued_again_after_its_cycle(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, recurrence: str
    ) -> None:
        bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
        store = SQLiteStore(tmp_path)
        session_id = f"sess_inbox_{OWNER}"
        store.create_session(session_id, str(tmp_path))
        task = TaskManager(store, EventLogWriter(store)).create_task(
            session_id=session_id,
            title="Keep building",
            objective="Improve the site",
            scheduled_at="2020-01-01T09:00:00Z",
            recurrence=recurrence,
        )

        async def completed(*_args: object, **_kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(status="completed", message="One cycle done.")

        monkeypatch.setattr("raiker.tasks.scheduler.AgentGateway.submit_prompt_async", completed)
        assert asyncio.run(TaskScheduler(tmp_path).run_due()) == 1

        saved = store.load_task(task.task_id)
        assert saved is not None
        assert saved.status == "queued", "a recurring agent re-arms instead of closing"
        assert saved.summary == "One cycle done."
        assert saved.scheduled_at is not None
        assert datetime.fromisoformat(saved.scheduled_at.replace("Z", "+00:00")) > datetime.now(UTC)

    def test_stopping_a_recurring_agent_is_never_overwritten_by_its_cycle(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The owner's stop wins: a cancellation recorded while the governed turn
        # was reaching a safe boundary must not be re-queued by the scheduler.
        bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
        store = SQLiteStore(tmp_path)
        session_id = f"sess_inbox_{OWNER}"
        store.create_session(session_id, str(tmp_path))
        manager = TaskManager(store, EventLogWriter(store))
        task = manager.create_task(
            session_id=session_id,
            title="Keep building",
            objective="Improve the site",
            scheduled_at="2020-01-01T09:00:00Z",
            recurrence="continuous",
        )

        async def cancel_midway(*_args: object, **_kwargs: object) -> SimpleNamespace:
            manager.cancel_task(task.task_id, "owner stopped it")
            return SimpleNamespace(status="completed", message="Cycle done.")

        monkeypatch.setattr(
            "raiker.tasks.scheduler.AgentGateway.submit_prompt_async", cancel_midway
        )
        asyncio.run(TaskScheduler(tmp_path).run_due())

        saved = store.load_task(task.task_id)
        assert saved is not None and saved.status == "cancelled"
