from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.checkpoints.capture import STATUS_CAPTURED, CheckpointCaptureService
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.models import ToolAction
from raiker.events.query import EventViewer
from raiker.storage.internal_paths import display_path, internal_io_path
from raiker.storage.sqlite import SQLiteStore


def test_internal_io_path_rejects_relative_input() -> None:
    with pytest.raises(ValueError, match="internal_path_must_be_absolute"):
        internal_io_path(Path(".raiker") / "events")


def test_internal_io_path_round_trips_an_absolute_path(tmp_path: Path) -> None:
    source = (tmp_path / ".raiker" / "events").resolve()
    converted = internal_io_path(source)
    assert display_path(converted) == str(source)
    if sys.platform == "win32":
        assert str(converted).startswith("\\\\?\\")
    else:
        assert converted == source


@pytest.mark.skipif(sys.platform != "win32", reason="Windows path namespaces")
@pytest.mark.parametrize(
    "source, expected_display",
    [
        (r"\\?\C:\deep\workspace\.raiker", r"C:\deep\workspace\.raiker"),
        (r"\\server\share\deep\.raiker", r"\\server\share\deep\.raiker"),
        (r"\\?\UNC\server\share\deep\.raiker", r"\\server\share\deep\.raiker"),
    ],
)
def test_extended_and_unc_paths_are_idempotent(source: str, expected_display: str) -> None:
    converted = internal_io_path(source)
    assert internal_io_path(converted) == converted
    assert display_path(converted) == expected_display


@pytest.mark.skipif(sys.platform != "win32", reason="Windows path namespaces")
@pytest.mark.parametrize(
    "source",
    [
        r"\\.\C:\workspace\.raiker",
        r"\??\C:\workspace\.raiker",
        r"\\?\GLOBALROOT\Device\HarddiskVolumeShadowCopy1",
        r"\\?\UNC\server",
    ],
)
def test_internal_io_path_rejects_malformed_or_unsafe_device_paths(source: str) -> None:
    with pytest.raises(ValueError, match="internal_path_invalid"):
        internal_io_path(source)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows MAX_PATH regression")
def test_deep_workspace_bootstraps_all_runtime_directories(tmp_path: Path) -> None:
    root = tmp_path
    for index in range(4):
        root = root / (f"segment-{index}-" + "a" * 55)
    internal_io_path(root.absolute()).mkdir(parents=True)

    store = SQLiteStore(root)

    assert store.db_path.is_file()
    assert store.paths.events_dir.is_dir()
    assert store.paths.checkpoints_dir.is_dir()
    assert display_path(store.db_path).endswith(r"\.raiker\raiker.db")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows MAX_PATH regression")
def test_deep_workspace_approved_overwrite_captures_a_pre_image(tmp_path: Path) -> None:
    root = tmp_path
    for index in range(4):
        root = root / (f"segment-{index}-" + "b" * 55)
    internal_io_path(root.absolute()).mkdir(parents=True)
    workspace = Path(display_path(internal_io_path(root.absolute())))
    internal_io_path(workspace / "notes.md").write_bytes(b"before\n")
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    raw, _ = ApiSessionStore(workspace).create_session("principal_owner")
    headers = {"Authorization": f"Bearer {raw}"}
    store = SQLiteStore(workspace)
    store.create_session("sess_deep", str(workspace))
    action = ToolAction(
        action_id="act_deep",
        tool_name="write_file",
        arguments={"path": "notes.md", "text": "after\n"},
        risk_level="high",
        requires_approval=True,
    )
    store.insert_tool_action(
        action, session_id="sess_deep", turn_id="turn_deep", status="approval_required"
    )
    store.insert_approval("appr_deep", action)
    pre_image = CheckpointCaptureService(store).snapshot_pre_image(
        "file_write_execution", {"path": "notes.md"}
    )
    assert pre_image is not None and not isinstance(pre_image, list)
    assert pre_image.status == STATUS_CAPTURED

    response = TestClient(create_app(workspace)).post(
        "/api/approvals/appr_deep/resolve",
        json={"approve": True, "reason": "deep path regression"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "executed"
    assert internal_io_path(workspace / "notes.md").read_text(encoding="utf-8") == "after\n"
    captured = store.list_checkpoint_capture_entries()
    failures = EventViewer(store).list_events(
        session_id="sess_deep", event_type="checkpoint_capture_failed"
    )
    failure_payloads = [EventViewer(store).read_event_payload(row["event_id"]) for row in failures]
    assert len(captured) == 1, {
        "failures": failure_payloads,
        "events": [row["event_type"] for row in store.list_event_index(limit=100)],
    }
    digest = str(captured[0]["pre_image_sha256"])
    blob = store.paths.checkpoints_dir / "objects" / digest[:2] / digest
    assert blob.read_bytes() == b"before\n"
