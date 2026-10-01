"""A mounted instance is a workspace, not only a route.

GCR-07, GCR-08 and GCR-09. Three defects that all live in the same half-page of
``raiker/api/app.py``: a second Raiker user's background work never started, a
failed first-account registration left an instance that blocked its own retry,
and the registry that says which instances exist was written non-atomically from
whichever threadpool worker happened to be serving the request.
"""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from raiker.api.app import (
    _read_instance_registry,
    _stored_instance_names,
    _write_instance_names,
    create_app,
)
from raiker.auth.accounts import AuthError
from raiker.cli.principal_resolver import bootstrap_owner


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "ws"
    root.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=root)
    return root


@pytest.fixture
def app(workspace: Path) -> FastAPI:
    return create_app(workspace)


def _create(client: TestClient, name: str, **extra: object) -> object:
    return client.post("/api/instances", json={"name": name, **extra})


# ── GCR-07 ───────────────────────────────────────────────────────────────────


def test_a_mounted_instance_gets_its_own_background_services(app: FastAPI, workspace: Path) -> None:
    """Starlette never enters a mounted app's lifespan, so this one owns it."""
    with TestClient(app) as client:
        assert _create(client, "alex").status_code == 200  # type: ignore[attr-defined]
        instance = app.state.instance_apps["alex"]
        runtime = app.state.instance_runtimes["alex"]

        assert runtime.app is instance
        assert runtime.workspace_root == instance.state.workspace_root
        assert runtime.workspace_root != app.state.workspace_root
        # The attached-root watcher is the one service that leaves a handle
        # behind, so it is the one that can be read back as proof the set ran.
        assert instance.state.attached_root_watcher is not None
        assert app.state.instance_runtimes[""].app is app

    # Leaving the lifespan stops everything it started, the instance included.
    assert app.state.instance_runtimes == {}


def test_an_instance_present_at_boot_is_started_by_the_root_lifespan(
    app: FastAPI, workspace: Path
) -> None:
    """The common case: the host restarts and its instances come back with it."""
    with TestClient(app) as client:
        assert _create(client, "alex").status_code == 200  # type: ignore[attr-defined]

    rebooted = create_app(workspace)
    assert "alex" in rebooted.state.instance_apps
    with TestClient(rebooted):
        assert "alex" in rebooted.state.instance_runtimes
        assert rebooted.state.instance_apps["alex"].state.attached_root_watcher is not None


# ── GCR-08 ───────────────────────────────────────────────────────────────────


def test_a_failed_first_account_leaves_nothing_behind_and_the_retry_works(
    app: FastAPI, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An instance exists completely or does not exist at all."""
    from raiker.auth import accounts

    calls: list[str] = []

    def refuse(self: object, username: str, password: str) -> None:
        calls.append(username)
        raise AuthError("weak_password")

    monkeypatch.setattr(accounts.AccountService, "register", refuse)
    with TestClient(app) as client:
        failed = _create(client, "alex", username="alex", password="short")
        assert failed.status_code == 422  # type: ignore[attr-defined]
        assert failed.json()["detail"]["reason_code"] == "account_creation_failed"  # type: ignore[attr-defined]
        assert calls == ["alex"]

        # None of the three things a half-made instance used to leave behind.
        assert not (workspace / ".raiker" / "instances" / "alex").exists()
        assert _stored_instance_names(workspace) == []
        assert "alex" not in app.state.instance_apps
        assert client.get("/instances/alex/api/health").status_code == 404

        # Which is the whole point: the retry the error invites can be made.
        monkeypatch.undo()
        retried = _create(client, "alex", username="alex", password="correct horse battery staple")
        assert retried.status_code == 200, retried.text  # type: ignore[attr-defined]
        assert client.get("/instances/alex/api/health").status_code == 200


# ── GCR-09 ───────────────────────────────────────────────────────────────────


def test_the_registry_is_published_atomically(workspace: Path) -> None:
    """A reader sees the old list or the new one, never a truncated file."""
    _write_instance_names(workspace, ["alex"])
    registry = workspace / ".raiker" / "instances.json"
    seen: list[str] = []
    stop = threading.Event()

    def read_forever() -> None:
        # Through the product's own reader: on Windows a raw open is refused
        # for a moment around each replace, and the reader waits that out
        # (BUG-310) rather than reporting the registry missing.
        while not stop.is_set():
            try:
                seen.append(_read_instance_registry(workspace))
            except OSError:
                seen.append("<missing>")

    reader = threading.Thread(target=read_forever, daemon=True)
    reader.start()
    try:
        for index in range(50):
            _write_instance_names(workspace, [f"instance-{number}" for number in range(index + 1)])
    finally:
        stop.set()
        reader.join(timeout=5)

    assert seen, "the reader never ran"
    for body in seen:
        # Every observation parses. Before the atomic replace, a read landing
        # inside `write_text` returned `""` or half a document.
        assert isinstance(json.loads(body), list)
    # And the staging file is not left lying beside the registry.
    assert [path.name for path in registry.parent.glob("instances.json.*")] == []


def test_two_concurrent_creates_both_survive(app: FastAPI, workspace: Path) -> None:
    """Read-modify-write lost a name; the create path is serialized now."""
    with TestClient(app) as client:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [
                future.result()
                for future in [
                    pool.submit(_create, client, "alex"),
                    pool.submit(_create, client, "sam"),
                ]
            ]
        assert sorted(response.status_code for response in results) == [200, 200]  # type: ignore[attr-defined]
        assert sorted(_stored_instance_names(workspace)) == ["alex", "sam"]
        assert sorted(app.state.instance_apps) == ["alex", "sam"]


def test_the_same_name_twice_is_refused_once(app: FastAPI) -> None:
    with TestClient(app) as client:
        assert _create(client, "alex").status_code == 200  # type: ignore[attr-defined]
        assert _create(client, "alex").status_code == 409  # type: ignore[attr-defined]


# ── BUG-310 ──────────────────────────────────────────────────────────────────
#
# Windows refuses two things Linux allows: replacing a file another handle has
# open, and removing a directory a handle is open in. Neither can be produced on
# the CI runner, so each is simulated at the call that refuses.


def test_a_registry_replace_waits_out_a_reader(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import raiker.api.app as app_module

    real_replace = app_module.os.replace
    refusals = {"left": 3}

    def sharing_violation(source: object, target: object) -> None:
        if refusals["left"] > 0:
            refusals["left"] -= 1
            raise PermissionError(32, "The process cannot access the file")
        real_replace(source, target)  # type: ignore[arg-type]

    monkeypatch.setattr(app_module.os, "replace", sharing_violation)
    monkeypatch.setattr(app_module, "_SHARING_RETRY_SECONDS", 0.0)
    _write_instance_names(workspace, ["alex"])
    assert refusals["left"] == 0
    assert _stored_instance_names(workspace) == ["alex"]
    registry = workspace / ".raiker" / "instances.json"
    assert [path.name for path in registry.parent.glob("instances.json.*")] == []


def test_a_registry_replace_that_never_succeeds_is_an_error(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import raiker.api.app as app_module

    def always_held(source: object, target: object) -> None:
        raise PermissionError(32, "held")

    monkeypatch.setattr(app_module.os, "replace", always_held)
    monkeypatch.setattr(app_module, "_SHARING_RETRY_SECONDS", 0.0)
    with pytest.raises(PermissionError):
        _write_instance_names(workspace, ["alex"])


def test_a_rollback_releases_the_staged_databases_handles_before_removing_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import raiker.api.app as app_module
    from raiker.storage import sqlite as sqlite_module
    from raiker.storage.sqlite import SQLiteStore

    staged = tmp_path / "staged"
    staged.mkdir()
    SQLiteStore(staged).connect()  # a cached handle, as a registration leaves one
    root = staged.resolve()
    assert any(key[0] == root for key in sqlite_module._CONNECTIONS)  # noqa: SLF001

    # Two refused removals first, as Windows refuses while a handle is open.
    real_rmtree = app_module.shutil.rmtree
    refusals = {"left": 2}

    def held_rmtree(path: Path, ignore_errors: bool = False) -> None:
        if refusals["left"] > 0:
            refusals["left"] -= 1
            return
        real_rmtree(path, ignore_errors=ignore_errors)

    monkeypatch.setattr(app_module.shutil, "rmtree", held_rmtree)
    monkeypatch.setattr(app_module, "_SHARING_RETRY_SECONDS", 0.0)
    app_module._remove_staged_workspace(staged, staged)  # noqa: SLF001

    assert not any(key[0] == root for key in sqlite_module._CONNECTIONS)  # noqa: SLF001
    assert not staged.exists()
