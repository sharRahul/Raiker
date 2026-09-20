"""Keeping an indexed attached root current, and saying when it cannot.

The reconcile pass is the floor; this worker only makes it prompt. That makes
one property load-bearing above all the others: a watcher that quietly stopped
would leave recall answering from a stale index with nothing to notice. So every
outcome — including failure — lands in `WatchState`, and the interface reads it
rather than assuming freshness.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control.dashboard import DashboardService
from raiker.knowledge.reconcile import reconcile_attached_root
from raiker.knowledge.watcher import (
    MAX_BACKOFF_SECONDS,
    REFRESH_SECONDS,
    WATCH_PASS_NAME,
    AttachedRootWatcher,
)
from raiker.storage.sqlite import SQLiteStore

OWNER = "principal_owner"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


def _attach(workspace: Path, external: Path) -> tuple[DashboardService, str]:
    external.mkdir(parents=True, exist_ok=True)
    service = DashboardService(workspace)
    created = service.create_project("Alpha", OWNER)
    attached = service.attach_project_folder(
        created.data["project_id"], str(external), OWNER
    )
    assert attached.ok, attached.reason_code
    return service, created.data["project_id"]


class TestState:
    def test_state_defaults_to_not_watching_before_the_first_pass(
        self, workspace: Path
    ) -> None:
        state = AttachedRootWatcher(workspace).state("proj_a")

        assert state.watching is False
        assert state.reason == "not_started"
        assert state.last_scanned_at == ""

    def test_a_watch_failure_is_reported_not_swallowed(self, workspace: Path) -> None:
        watcher = AttachedRootWatcher(workspace)

        watcher.record_failure("proj_a", "watch_limit_reached")

        state = watcher.state("proj_a")
        assert state.watching is False
        assert state.reason == "watch_limit_reached"

    def test_a_failure_keeps_the_last_scan_it_did_manage(self, workspace: Path) -> None:
        # The index is not empty because watching stopped -- it is as fresh as
        # the last pass. Losing that timestamp would make a degraded watcher
        # indistinguishable from one that never ran.
        watcher = AttachedRootWatcher(workspace)
        watcher.record_scan("proj_a", "2026-08-25T10:00:00Z")

        watcher.record_failure("proj_a", "watch_failed:OSError")

        state = watcher.state("proj_a")
        assert state.watching is False
        assert state.last_scanned_at == "2026-08-25T10:00:00Z"

    def test_a_scan_marks_the_project_watched_and_fresh(self, workspace: Path) -> None:
        watcher = AttachedRootWatcher(workspace)

        watcher.record_scan("proj_a", "2026-08-25T10:00:00Z")

        state = watcher.state("proj_a")
        assert state.watching is True
        assert state.reason == "watching"
        assert state.last_scanned_at == "2026-08-25T10:00:00Z"


class TestRoots:
    def test_an_indexed_attached_root_is_watched(
        self, tmp_path: Path, workspace: Path
    ) -> None:
        service, project_id = _attach(workspace, tmp_path / "repo")
        root = tmp_path / "repo"
        (root / "a.md").write_text("alpha", encoding="utf-8")
        reconcile_attached_root(workspace, service.store, service.store.load_project(project_id), OWNER)

        roots = AttachedRootWatcher(workspace).indexed_attached_roots()

        assert roots == {root.resolve(): project_id}

    def test_an_unindexed_attached_root_is_not_watched(
        self, tmp_path: Path, workspace: Path
    ) -> None:
        # Watching a folder nobody asked to index would read the owner's disk
        # continuously for an index that does not exist.
        _attach(workspace, tmp_path / "repo")

        assert AttachedRootWatcher(workspace).indexed_attached_roots() == {}

    def test_a_managed_project_is_never_watched(self, workspace: Path) -> None:
        DashboardService(workspace).create_project("Alpha", OWNER)

        assert AttachedRootWatcher(workspace).indexed_attached_roots() == {}


class TestWorker:
    @pytest.mark.anyio
    async def test_the_worker_stops_when_asked(self, workspace: Path) -> None:
        watcher = AttachedRootWatcher(workspace)
        stop = asyncio.Event()

        task = asyncio.create_task(watcher.run(stop))
        stop.set()

        await asyncio.wait_for(task, timeout=10)

    @pytest.mark.anyio
    async def test_a_change_reaches_the_catalogue(
        self, tmp_path: Path, workspace: Path
    ) -> None:
        service, project_id = _attach(workspace, tmp_path / "repo")
        root = tmp_path / "repo"
        (root / "a.md").write_text("alpha deployment", encoding="utf-8")
        reconcile_attached_root(
            workspace, service.store, service.store.load_project(project_id), OWNER
        )
        watcher = AttachedRootWatcher(workspace)
        stop = asyncio.Event()
        task = asyncio.create_task(watcher.run(stop))
        try:
            await asyncio.sleep(0.3)
            (root / "b.md").write_text("beta rollout", encoding="utf-8")
            for _ in range(80):
                await asyncio.sleep(0.25)
                if service.store.search_managed_file_chunks(
                    "rollout", owner_principal_id=OWNER
                ):
                    break
        finally:
            stop.set()
            task.cancel()
            with pytest.raises((asyncio.CancelledError, TimeoutError)):
                await asyncio.wait_for(task, timeout=10)

        assert service.store.search_managed_file_chunks("rollout", owner_principal_id=OWNER)


class TestWatcherHealth:
    """GCR-47 — the loop's own failures, which used to leave no trace at all.

    `_cycle` was wrapped in `suppress(Exception)`. A failure inside it that
    happened *before* any project was reached — enumerating the indexed roots,
    setting the cycle up — recorded nothing, and every project kept the
    `WatchState` its last good pass had earned. The interface went on saying
    "Watching this folder for changes", with a timestamp, while nothing was.
    """

    @pytest.mark.anyio
    async def test_a_cycle_that_throws_is_recorded_as_a_background_pass(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        watcher = AttachedRootWatcher(workspace)

        async def broken(_stop: asyncio.Event) -> None:
            raise OSError("no watch descriptors left")

        monkeypatch.setattr(watcher, "_cycle", broken)
        stop = asyncio.Event()
        task = asyncio.create_task(watcher.run(stop))
        await asyncio.sleep(0.2)
        stop.set()
        await asyncio.wait_for(task, timeout=10)

        health = watcher.health()
        assert health.healthy is False
        assert health.consecutive_failures >= 1
        assert health.last_error_class == "OSError"

        recorded = {
            row["pass_name"]: row
            for row in SQLiteStore(workspace).list_background_worker_health()
        }
        assert WATCH_PASS_NAME in recorded, "Diagnostics has to be able to see this"
        assert recorded[WATCH_PASS_NAME]["healthy"] is False
        assert recorded[WATCH_PASS_NAME]["last_error_class"] == "OSError"

    @pytest.mark.anyio
    async def test_no_project_is_told_it_is_watched_while_the_loop_is_failing(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        watcher = AttachedRootWatcher(workspace)
        watcher.record_scan("proj_a", "2026-09-18T10:00:00Z")
        assert watcher.state("proj_a").watching is True

        async def broken(_stop: asyncio.Event) -> None:
            raise RuntimeError("the cycle could not start")

        monkeypatch.setattr(watcher, "_cycle", broken)
        stop = asyncio.Event()
        task = asyncio.create_task(watcher.run(stop))
        await asyncio.sleep(0.2)
        stop.set()
        await asyncio.wait_for(task, timeout=10)

        state = watcher.state("proj_a")
        assert state.watching is False
        assert state.reason == "watcher_failed:RuntimeError"
        # The freshness it earned survives: the index is exactly as current as
        # that last good pass left it.
        assert state.last_scanned_at == "2026-09-18T10:00:00Z"

    def test_the_retry_interval_backs_off_and_is_capped(self, workspace: Path) -> None:
        watcher = AttachedRootWatcher(workspace)
        assert watcher.health().retry_seconds == REFRESH_SECONDS

        intervals = []
        for count in range(1, 12):
            watcher._consecutive_failures = count
            intervals.append(watcher.health().retry_seconds)

        assert intervals[0] > REFRESH_SECONDS
        assert intervals == sorted(intervals)
        assert max(intervals) == MAX_BACKOFF_SECONDS

    @pytest.mark.anyio
    async def test_a_cycle_that_gets_through_clears_the_streak(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        watcher = AttachedRootWatcher(workspace)
        watcher._consecutive_failures = 3
        watcher._last_error_class = "OSError"

        async def fine(_stop: asyncio.Event) -> None:
            return None

        monkeypatch.setattr(watcher, "_cycle", fine)
        stop = asyncio.Event()
        task = asyncio.create_task(watcher.run(stop))
        await asyncio.sleep(0.2)
        stop.set()
        await asyncio.wait_for(task, timeout=10)

        assert watcher.health().healthy is True
        recorded = {
            row["pass_name"]: row
            for row in SQLiteStore(workspace).list_background_worker_health()
        }
        assert recorded[WATCH_PASS_NAME]["healthy"] is True
