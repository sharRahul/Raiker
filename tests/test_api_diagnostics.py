from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


def _headers(workspace: Path) -> dict[str, str]:
    raw, _ = ApiSessionStore(workspace).create_session("principal_owner")
    return {"Authorization": f"Bearer {raw}"}


class TestDiagnostics:
    def test_requires_auth(self, client: TestClient) -> None:
        assert client.get("/api/diagnostics").status_code == 401

    def test_schema_has_m6_sections(self, workspace: Path, client: TestClient) -> None:
        resp = client.get("/api/diagnostics", headers=_headers(workspace))
        assert resp.status_code == 200
        body = resp.json()
        for key in ("readiness", "disabled_capabilities", "missing_config", "provider_health"):
            assert key in body, f"missing diagnostics section: {key}"
        assert isinstance(body["readiness"], dict)
        assert isinstance(body["missing_config"], list)
        assert isinstance(body["provider_health"], list)
        assert "local single-user runtime" in body["scope_note"]

    def test_readiness_matches_runtime_readiness(self, workspace: Path, client: TestClient) -> None:
        headers = _headers(workspace)
        diag = client.get("/api/diagnostics", headers=headers).json()
        readiness = client.get("/api/runtime-readiness", headers=headers).json()
        # The diagnostics readiness block is derived from the same runtime-readiness summary.
        assert diag["readiness"] == readiness["summary"]
        assert diag["runtime_mode"] == readiness["mode"]["mode_name"]

    def test_provider_health_is_config_derived_not_probed(
        self, workspace: Path, client: TestClient
    ) -> None:
        body = client.get("/api/diagnostics", headers=_headers(workspace)).json()
        assert len(body["provider_health"]) > 0
        for entry in body["provider_health"]:
            # Honest: status is config-derived; reachability is explicitly not probed here.
            assert entry["status"] in {"selected", "configured"}
            assert "not probed" in entry["detail"]
            assert {"profile_id", "provider", "requires_network", "local_only"} <= set(entry)

    def test_fresh_workspace_has_a_shipped_default_model(self, workspace: Path, client: TestClient) -> None:
        # Ollama gemma4:31b-cloud is the usable local default, so a fresh
        # workspace must not claim that model selection is missing.
        body = client.get("/api/diagnostics", headers=_headers(workspace)).json()
        assert not any("model profile" in gap.lower() for gap in body["missing_config"])
