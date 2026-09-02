"""BUG-44 — the update panel's contract: honest, owner-only, and quiet.

Three properties, in the order they matter. An unauthenticated caller learns
nothing about the build. A status read makes no outbound request — opening a
panel must not be a way to cause egress. And a host that was never installed from
a release artifact says exactly that instead of offering an update it could not
verify.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
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


def _headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/session", json={"as_principal": None})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_the_build_is_not_described_to_an_unauthenticated_caller(client: TestClient) -> None:
    assert client.get("/api/host/update").status_code in (401, 403)
    assert client.post("/api/host/update/check").status_code in (401, 403)


def test_status_reports_the_running_build_and_the_release_matrix(client: TestClient) -> None:
    body = client.get("/api/host/update", headers=_headers(client)).json()
    # The suite runs from a checkout, which is exactly the answer under test.
    assert body["state"] == "source_checkout"
    assert body["installation"]["packaged"] is False
    assert body["installation"]["signed"] is False
    assert body["channel"] is None
    assert body["available"] is None
    targets = {target["target_id"]: target for target in body["targets"]}
    assert set(targets) == {"macos-arm64", "windows-x86_64", "linux-x86_64", "linux-arm64"}
    for target in targets.values():
        assert target["signing"]["secrets"], target["target_id"]
        assert target["installer_formats"], target["target_id"]


def test_a_status_read_makes_no_outbound_request(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import raiker.app.updater as updater

    def forbidden(timeout: float = 0.0) -> None:  # pragma: no cover - must not run
        raise AssertionError("a status read must not fetch anything")

    monkeypatch.setattr(updater, "https_fetcher", forbidden)
    assert client.get("/api/host/update", headers=_headers(client)).status_code == 200


def test_checking_from_a_source_checkout_refuses_locally_without_fetching(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import raiker.app.updater as updater

    def forbidden(timeout: float = 0.0) -> None:  # pragma: no cover - must not run
        raise AssertionError("a source checkout must not contact a channel")

    monkeypatch.setattr(updater, "https_fetcher", forbidden)
    body = client.post("/api/host/update/check", headers=_headers(client)).json()
    assert body["ok"] is True
    assert body["state"] == "source_checkout"
    assert body["available"] is None
    # Nothing was checked, so nothing is recorded as having been checked.
    assert body["last_check"] is None


def test_apply_refuses_a_source_checkout_without_starting_a_handoff(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import raiker.api.routes_updates as routes

    def forbidden(*_args: object, **_kwargs: object) -> None:  # pragma: no cover - must not run
        raise AssertionError("a source checkout must not start an update helper")

    monkeypatch.setattr(routes, "start_update_handoff", forbidden)
    response = client.post("/api/host/update/apply", headers=_headers(client), json={"confirm": True})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is False
    assert body["reason_code"] == "update_source_checkout"


def test_a_pinned_channel_is_reported_without_its_key(
    client: TestClient, workspace: Path
) -> None:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from raiker.app.installation import write_channel_config
    from raiker.app.release import public_key_of

    key = Ed25519PrivateKey.generate().private_bytes_raw()
    write_channel_config(
        workspace,
        url="https://releases.example/stable.json",
        public_key=public_key_of(key).hex(),
    )
    body = client.get("/api/host/update", headers=_headers(client)).json()
    assert body["channel"]["url"] == "https://releases.example/stable.json"
    assert body["channel"]["channel"] == "stable"
    assert "public_key" not in body["channel"]
    assert len(body["channel"]["public_key_fingerprint"]) == 16
