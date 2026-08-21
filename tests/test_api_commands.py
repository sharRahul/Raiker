from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.execution.commands.service import CommandService


def test_credential_delta_api_is_owner_scoped_secret_free_and_discardable(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    bootstrap_owner("rahul", "Rahul", workspace_root=workspace)
    app = create_app(workspace)
    client = TestClient(app)
    session = client.post("/api/auth/session", json={"as_principal": None}).json()
    token = session["token"]
    owner = session["principal_id"]
    headers = {"Authorization": f"Bearer {token}"}
    service = CommandService.for_workspace(workspace)
    service.store.create_credential_delta(
        owner_principal_id=owner,
        run_id="cmd_delta",
        environment_profile_id="container_a",
        state="quarantined",
        snapshot_handle=b"secret staging path",
        cleanup_scan_bundle=b"credential bytes",
        safe_manifest_json='{"files":[{"kind":"file","path":"result.txt","size":4}]}',
        delta_digest="a" * 64,
        scan_digest="b" * 64,
    )

    listed = client.get(
        "/api/credential-deltas?environment_profile_id=container_a", headers=headers
    )
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["deltas"][0]["manifest"]["files"][0]["path"] == "result.txt"
    assert "secret staging path" not in listed.text
    assert "credential bytes" not in listed.text

    discarded = client.post(
        "/api/credential-deltas/cmd_delta/discard",
        headers=headers,
        json={"decision_id": "decision_owner"},
    )
    assert discarded.status_code == 200
    assert discarded.json()["receipt"]["resolution"] == "discarded"
    assert discarded.json()["receipt"]["cleanup_status"] == "metadata_erased"


def test_quarantined_delta_can_never_be_merged(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    service = CommandService.for_workspace(workspace)
    service.store.create_credential_delta(
        owner_principal_id="owner_a",
        run_id="cmd_delta",
        environment_profile_id="container_a",
        state="quarantined",
        snapshot_handle=b"snapshot",
        cleanup_scan_bundle=b"bundle",
        safe_manifest_json='{"files":[]}',
        delta_digest="a" * 64,
        scan_digest="b" * 64,
    )
    try:
        service.store.resolve_credential_delta(
            "owner_a",
            "cmd_delta",
            decision_id="decision_a",
            resolution="merged",
            second_scan_digest="b" * 64,
        )
    except ValueError as exc:
        assert str(exc) == "credential_delta_quarantined_discard_only"
    else:
        raise AssertionError("quarantined delta merged")
