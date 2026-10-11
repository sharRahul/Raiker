"""DEC-22 steps 1–2 — "serialize control decisions per session and reject stale commands."

A tab's stop and steer were applied in whatever order they reached the host, so
a steer delayed behind a later stop — or a retransmission of one already
applied — was applied again as though it were new. Each command now carries the
sending client's id and its own count; an older one arriving late is refused
with nothing applied, and the same command sent twice is applied once.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.storage.sqlite import SQLiteStore

OWNER = "principal_owner"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    SQLiteStore(ws).create_session("sess_live", str(ws))
    return ws


def _post(workspace: Path, **body: object) -> object:
    raw, _ = ApiSessionStore(workspace).create_session(OWNER)
    client = TestClient(create_app(workspace))
    return client.post(
        "/api/interrupts",
        json={"session_id": "sess_live", "all": True, **body},
        headers={"Authorization": f"Bearer {raw}"},
    )


def test_a_late_older_steer_is_refused_and_nothing_is_queued(workspace: Path) -> None:
    stop = _post(workspace, action_type="cancel", client_id="tab-a", client_sequence=2)
    late = _post(
        workspace, action_type="steer", steer_text="use the changelog",
        client_id="tab-a", client_sequence=1,
    )

    assert stop.status_code == 200  # type: ignore[attr-defined]
    assert late.status_code == 409  # type: ignore[attr-defined]
    assert late.json()["detail"]["reason_code"] == "control_command_stale"  # type: ignore[attr-defined]
    control = SQLiteStore(workspace).take_turn_control("sess_live", OWNER)
    assert control["stop_requested"] is True and control["steer_texts"] == []


def test_the_same_command_sent_twice_is_applied_once(workspace: Path) -> None:
    body = {"action_type": "steer", "steer_text": "shorter please", "client_id": "tab-a", "client_sequence": 5}
    first = _post(workspace, **body)
    again = _post(workspace, **body)

    assert first.json()["turn_control"] == {"action": "steer", "queued": 1}  # type: ignore[attr-defined]
    assert again.status_code == 200 and again.json()["duplicate"] is True  # type: ignore[attr-defined]
    control = SQLiteStore(workspace).take_turn_control("sess_live", OWNER)
    assert control["steer_texts"] == ["shorter please"]


def test_a_different_command_reusing_a_number_is_stale(workspace: Path) -> None:
    assert _post(workspace, action_type="steer", steer_text="a", client_id="tab-a", client_sequence=3).status_code == 200  # type: ignore[attr-defined]
    reused = _post(workspace, action_type="steer", steer_text="b", client_id="tab-a", client_sequence=3)
    assert reused.status_code == 409  # type: ignore[attr-defined]


def test_each_client_counts_for_itself(workspace: Path) -> None:
    assert _post(workspace, action_type="cancel", client_id="tab-a", client_sequence=9).status_code == 200  # type: ignore[attr-defined]
    other = _post(workspace, action_type="steer", steer_text="x", client_id="tab-b", client_sequence=1)
    assert other.status_code == 200  # type: ignore[attr-defined]


def test_a_command_without_a_sequence_is_ordered_by_arrival_as_before(workspace: Path) -> None:
    assert _post(workspace, action_type="cancel", client_id="tab-a", client_sequence=9).status_code == 200  # type: ignore[attr-defined]
    assert _post(workspace, action_type="cancel").status_code == 200  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "extra",
    [
        {"client_id": "tab-a"},
        {"client_sequence": 1},
        {"client_id": "tab a!", "client_sequence": 1},
        {"client_id": "tab-a", "client_sequence": -1},
    ],
)
def test_a_half_or_malformed_sequence_is_refused(workspace: Path, extra: dict[str, object]) -> None:
    answer = _post(workspace, action_type="cancel", **extra)
    assert answer.status_code == 422  # type: ignore[attr-defined]
    assert answer.json()["detail"]["reason_code"] == "control_command_sequence_invalid"  # type: ignore[attr-defined]
