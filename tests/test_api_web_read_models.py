"""Contract and safety tests for the web workbench read models.

These endpoints exist so the browser never has to infer readiness, provenance,
or restore impact from metadata it holds locally. The tests below hold them to
that promise: four independent extension facts, a metadata-only restore
preflight, a file explorer that serves no file content and cannot escape the
workspace, and a support bundle with no secret in it.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.redaction import assert_no_secrets_in_body
from raiker.checkpoints.capture import STATUS_CAPTURED, CheckpointCaptureService
from raiker.checkpoints.service import CheckpointService
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control.web_read_models import WebReadModels
from raiker.storage.sqlite import SQLiteStore

EXTENSION_KEYS = {
    "extension_id", "kind", "display_name", "category", "installed", "connected",
    "enabled", "usable", "blocked_reason", "detail", "capability", "gate_state",
    "decision_mode", "egress_host", "egress_allowed", "transport", "monitor_state",
    "tool_count", "last_activity_at",
}
EXTENSIONS_VIEW_KEYS = {
    "extensions", "counts", "vault_configured", "connector_egress_allowlist_configured", "deferred",
}
PROJECT_FILES_KEYS = {
    "project_id", "root_subpath", "root_exists", "files", "truncated", "provenance", "note",
}
PROJECT_FILE_KEYS = {"workspace_path", "name", "is_directory", "size_bytes", "modified_at", "depth"}
RESTORE_PLAN_KEYS = {
    "status", "checkpoint_id", "session_id", "checkpoint_created_at", "can_execute",
    "requires_approval", "files", "restore_content_count", "delete_count", "skip_count",
    "changed_count", "touches_other_principal",
}


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
    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _create_project(client: TestClient, headers: dict[str, str], name: str) -> str:
    body = client.post("/api/projects", json={"name": name}, headers=headers).json()
    assert body["ok"], body
    return str(body["project_id"])


class TestExtensionsOverview:
    def test_reports_four_independent_lifecycle_facts(
        self, client: TestClient
    ) -> None:
        response = client.get("/api/extensions", headers=_headers(client))
        assert response.status_code == 200
        body = response.json()
        assert set(body) >= EXTENSIONS_VIEW_KEYS
        assert body["extensions"], "the connector catalog should yield at least one extension"
        for extension in body["extensions"]:
            assert set(extension) >= EXTENSION_KEYS
            # Usable is a conclusion, never an independent claim: an extension
            # cannot be usable while any earlier condition is unmet.
            if extension["usable"]:
                assert extension["installed"] and extension["connected"] and extension["enabled"]
                assert extension["blocked_reason"] is None
            else:
                assert extension["blocked_reason"] is not None

    def test_fresh_workspace_has_nothing_usable_and_says_why(self, client: TestClient) -> None:
        body = client.get("/api/extensions", headers=_headers(client)).json()
        assert body["counts"]["usable"] == 0
        assert {e["blocked_reason"] for e in body["extensions"]} == {"not_installed"}

    def test_installing_advances_only_the_installed_fact(self, client: TestClient) -> None:
        headers = _headers(client)
        catalog = client.get("/api/connector-store", headers=headers).json()["connectors"]
        connector_id = catalog[0]["connector_id"]
        assert client.post(
            f"/api/connector-store/{connector_id}/install", headers=headers
        ).status_code == 200

        row = next(
            e
            for e in client.get("/api/extensions", headers=headers).json()["extensions"]
            if e["extension_id"] == f"connector:{connector_id}"
        )
        assert row["installed"] is True
        assert row["connected"] is False
        assert row["enabled"] is False
        assert row["usable"] is False
        assert row["blocked_reason"] == "account_not_connected"

    def test_deferred_surfaces_are_named_rather_than_hidden(self, client: TestClient) -> None:
        body = client.get("/api/extensions", headers=_headers(client)).json()
        kinds = {entry["kind"]: entry["status"] for entry in body["deferred"]}
        assert kinds == {"plugin": "not_available", "channel": "not_available"}

    def test_response_carries_no_secret(self, client: TestClient) -> None:
        assert_no_secrets_in_body(client.get("/api/extensions", headers=_headers(client)).json())


class TestModelReasoningMetadata:
    def test_models_expose_only_provider_declared_reasoning_effort_capabilities(
        self, client: TestClient
    ) -> None:
        response = client.get("/api/models", headers=_headers(client))

        assert response.status_code == 200
        profile = next(
            item for item in response.json()["profiles"] if item["profile_id"] == "openai-hosted"
        )
        assert profile["supports_reasoning"] is True
        assert profile["supports_reasoning_effort"] is True
        assert profile["reasoning_effort_values"] == ["low", "medium", "high"]


class TestCheckpointRestorePlan:
    def _seed_checkpoint(self, workspace: Path) -> str:
        """A checkpoint, then a captured post-checkpoint write to one file.

        The capture is what makes a restore plan non-empty: it holds the file's
        state *at* the checkpoint, which is what a restore would rewind to.
        """
        store = SQLiteStore(workspace)
        store.create_session("sess_restore", str(workspace))
        target = workspace / "notes.txt"
        target.write_text("state at the checkpoint", encoding="utf-8")
        checkpoint, _path = CheckpointService(store).write_turn_checkpoint(
            session_id="sess_restore",
            turn_id="turn_1",
            runtime_state="",
            summary="before the edit",
            last_event_id="evt_1",
        )
        capture = CheckpointCaptureService(store)
        pre_image = capture.snapshot_path("notes.txt", "filesystem_write")
        assert pre_image is not None and pre_image.data is not None
        # Checkpoint timestamps have second resolution and a plan only rewinds
        # writes recorded strictly *after* the checkpoint, so the seeded capture
        # is stamped a second later rather than racing the same clock tick.
        store.insert_checkpoint_capture_entry(
            manifest_id="ckcap_seed",
            session_id="sess_restore",
            turn_id="turn_2",
            action_id="act_2",
            capability="filesystem_write",
            principal_id="principal_owner",
            workspace_path="notes.txt",
            pre_image_sha256=hashlib.sha256(pre_image.data).hexdigest(),
            pre_image_size=pre_image.size,
            existed_before=True,
            capture_status=STATUS_CAPTURED,
            created_at=_one_second_after(str(checkpoint.created_at)),
        )
        target.write_text("after the edit", encoding="utf-8")
        return str(checkpoint.checkpoint_id)

    def test_preflight_is_metadata_only_and_names_affected_files(
        self, client: TestClient, workspace: Path
    ) -> None:
        checkpoint_id = self._seed_checkpoint(workspace)
        response = client.get(
            f"/api/checkpoints/{checkpoint_id}/restore-plan", headers=_headers(client)
        )
        assert response.status_code == 200
        plan = response.json()
        assert set(plan) >= RESTORE_PLAN_KEYS
        assert plan["requires_approval"] is True
        assert [f["workspace_path"] for f in plan["files"]] == ["notes.txt"]
        # A preflight reports content addresses, never content.
        for entry in plan["files"]:
            assert "content" not in entry
            assert "text" not in entry

    def test_preflight_changes_nothing_on_disk(
        self, client: TestClient, workspace: Path
    ) -> None:
        checkpoint_id = self._seed_checkpoint(workspace)
        before = (workspace / "notes.txt").read_text(encoding="utf-8")
        client.get(f"/api/checkpoints/{checkpoint_id}/restore-plan", headers=_headers(client))
        assert (workspace / "notes.txt").read_text(encoding="utf-8") == before

    def test_unknown_checkpoint_is_not_found(self, client: TestClient) -> None:
        response = client.get(
            "/api/checkpoints/ckpt_missing/restore-plan", headers=_headers(client)
        )
        assert response.status_code == 404


class TestProjectFiles:
    def test_lists_metadata_and_never_content(
        self, client: TestClient, workspace: Path
    ) -> None:
        headers = _headers(client)
        project_id = _create_project(client, headers, "Field notes")
        detail = client.get(f"/api/projects/{project_id}", headers=headers).json()
        root = workspace / detail["project"]["root_subpath"]
        root.mkdir(parents=True, exist_ok=True)
        (root / "brief.md").write_text("classified draft body", encoding="utf-8")
        (root / "drafts").mkdir(exist_ok=True)

        body = client.get(f"/api/projects/{project_id}/files", headers=headers).json()
        assert set(body) >= PROJECT_FILES_KEYS
        assert body["root_exists"] is True
        names = {entry["name"] for entry in body["files"]}
        assert {"brief.md", "drafts"} <= names
        for entry in body["files"]:
            assert set(entry) >= PROJECT_FILE_KEYS
        assert "classified draft body" not in response_text(body)

    def test_missing_root_is_reported_rather_than_failing(
        self, client: TestClient
    ) -> None:
        headers = _headers(client)
        project_id = _create_project(client, headers, "Empty scope")
        body = client.get(f"/api/projects/{project_id}/files", headers=headers).json()
        assert body["files"] == []
        assert body["truncated"] is False

    def test_unknown_project_is_not_found(self, client: TestClient) -> None:
        response = client.get("/api/projects/proj_missing/files", headers=_headers(client))
        assert response.status_code == 404

    def test_path_outside_the_workspace_is_refused(self, workspace: Path) -> None:
        models = WebReadModels(workspace)
        assert models._contained_path("../escape") is None  # noqa: SLF001
        assert models._contained_path("") is None  # noqa: SLF001
        assert models._contained_path("inside") is not None  # noqa: SLF001


class TestDiagnosticsExport:
    def test_bundle_is_redacted_and_scoped(self, client: TestClient) -> None:
        response = client.get("/api/diagnostics/export", headers=_headers(client))
        assert response.status_code == 200
        body = response.json()
        assert body["scope"] == "local single-user runtime"
        assert {"generated_at", "counts", "readiness", "gates", "note"} <= set(body)
        assert_no_secrets_in_body(body)

    def test_bundle_reports_gate_state_without_claiming_readiness(
        self, client: TestClient
    ) -> None:
        body = client.get("/api/diagnostics/export", headers=_headers(client)).json()
        assert isinstance(body["gates"], list) and body["gates"]
        for gate in body["gates"]:
            assert {"capability", "state", "decision_mode", "runtime_enabled"} == set(gate)


def response_text(body: object) -> str:
    import json

    return json.dumps(body)


def _one_second_after(timestamp: str) -> str:
    moment = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    return (moment + timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")


# BUG-11 — "the gate is closed" was told to owners whose gate was already open.
#
# A surface that needs `runtime_enabled` has three distinct ways of being shut,
# and each needs a different action. Naming them apart is the whole fix: an
# owner who has enabled a capability to `enabled_policy_gated` and is told to
# "enable it in Capabilities" follows that advice and nothing changes, because
# what they actually need is a runtime-enablement mode.
class TestBlockedReasonNamesTheRealBlocker:
    def _reason(self, **overrides: object) -> str | None:
        from raiker.control.web_read_models import _connector_block_reason

        base: dict[str, object] = {
            "installed": True,
            "connected": True,
            "enabled": True,
            "auth_status": "connected",
            "gate_open": False,
            "egress_ok": True,
            "gate_state": "disabled",
            "decision_mode": "ask",
        }
        base.update(overrides)
        return _connector_block_reason(**base)  # type: ignore[arg-type]

    def test_an_off_gate_still_says_the_gate_is_off(self) -> None:
        assert self._reason(gate_state="disabled") == "capability_gate_closed"

    def test_an_enabled_but_below_runtime_gate_says_so(self) -> None:
        assert self._reason(gate_state="enabled_policy_gated") == "capability_below_runtime_level"
        assert self._reason(gate_state="enabled_read_only") == "capability_below_runtime_level"

    def test_a_deny_decision_mode_is_named_as_itself(self) -> None:
        assert (
            self._reason(gate_state="enabled_runtime", decision_mode="deny")
            == "capability_decision_mode_deny"
        )

    def test_an_open_gate_is_not_blocked_by_the_gate(self) -> None:
        assert self._reason(gate_open=True, gate_state="enabled_runtime") is None

    def test_earlier_unmet_conditions_still_win(self) -> None:
        # Order matters: an owner cannot act on a gate before the connector is
        # installed and authenticated.
        assert self._reason(installed=False) == "not_installed"
        assert self._reason(connected=False, auth_status="not_connected") == "account_not_connected"
