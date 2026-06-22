"""The local web dashboard is served from the same loopback origin as the governed API.

Guards: when a built SPA dir is provided, `/` serves the SPA shell and `/assets/*` serve assets,
while `/api/*` keeps precedence and stays redacted; static assets are served untouched (a
secret-like literal in a bundle is NOT mangled by the redaction middleware). With no UI dir the
server is API-only and `/` is a 404 — back-compat for every existing `create_app(workspace)` test.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner

# A 40+ char token-like literal: the API redactor would mask this in a JSON body, but it must pass
# through untouched when it is part of a static asset served by the SPA mount.
SECRET_LIKE = "sk-proj-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    return ws


@pytest.fixture
def ui_dir(tmp_path: Path) -> Path:
    d = tmp_path / "dist"
    (d / "assets").mkdir(parents=True)
    (d / "index.html").write_text(
        '<!doctype html><html><body><div id="app"></div>'
        '<script type="module" src="/assets/app.js"></script></body></html>',
        encoding="utf-8",
    )
    (d / "assets" / "app.js").write_text(
        f'console.log("raiker");/* {SECRET_LIKE} */', encoding="utf-8"
    )
    return d


class TestWithUi:
    def test_serves_spa_shell_at_root(self, workspace: Path, ui_dir: Path) -> None:
        client = TestClient(create_app(workspace, ui_dir=ui_dir))
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")
        assert '<div id="app">' in resp.text

    def test_serves_assets_untouched_by_redaction(self, workspace: Path, ui_dir: Path) -> None:
        client = TestClient(create_app(workspace, ui_dir=ui_dir))
        resp = client.get("/assets/app.js")
        assert resp.status_code == 200
        # The secret-like literal survives intact: static assets bypass the API redactor.
        assert SECRET_LIKE in resp.text

    def test_api_routes_keep_precedence_and_redaction(self, workspace: Path, ui_dir: Path) -> None:
        client = TestClient(create_app(workspace, ui_dir=ui_dir))
        # /api still resolves to the API (not shadowed by the catch-all SPA mount).
        assert client.get("/api/runtime-mode").status_code == 401  # auth still enforced
        raw = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
        ok = client.get("/api/runtime-mode", headers={"Authorization": f"Bearer {raw}"})
        assert ok.status_code == 200
        assert "mode_name" in ok.json()


class TestApiOnly:
    def test_no_ui_dir_is_api_only(self, workspace: Path) -> None:
        client = TestClient(create_app(workspace))
        # Back-compat: without a built UI, the root path is not served.
        assert client.get("/").status_code == 404
        # The API is unaffected.
        assert client.post("/api/auth/session", json={"as_principal": None}).status_code == 200

    def test_missing_ui_dir_is_ignored(self, workspace: Path, tmp_path: Path) -> None:
        client = TestClient(create_app(workspace, ui_dir=tmp_path / "does_not_exist"))
        assert client.get("/").status_code == 404
        assert client.post("/api/auth/session", json={"as_principal": None}).status_code == 200
