"""A routine's results to a connected channel (Quiet UI 06, QUI-F06).

Sending a routine's result to Telegram or Slack is an unattended outbound send,
so it needs the owner's consent when the routine is set up and, on every send,
the channel's own gates. What happened to the last send is kept and shown.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control.dtos import ControlResult
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks import routine_delivery

WEBHOOKS = "channel.webhooks"


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir(exist_ok=True)
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    return tmp_path


@pytest.fixture()
def client(workspace: Path, offline_default_model: None) -> TestClient:
    client = TestClient(create_app(workspace))
    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def _paired(client: TestClient) -> None:
    paired = client.post(
        "/api/channels/pairings", json={"connector_id": WEBHOOKS, "display_name": "Ops room", "senders": ["ops"]}
    )
    assert paired.status_code == 200, paired.text


def test_a_channel_delivery_needs_consent_and_a_paired_channel(client: TestClient) -> None:
    refused = client.post("/api/tasks", json={"title": "Morning brief", "deliver_to": WEBHOOKS})
    assert refused.status_code == 422
    assert "routine_delivery_needs_consent" in refused.text
    unknown = client.post("/api/tasks", json={"title": "Morning brief", "description": "Summarise my day.", "deliver_to": WEBHOOKS, "deliver_consent": True})
    assert unknown.status_code == 422
    assert "routine_delivery_channel_unknown" in unknown.text
    # Nothing was created by a refused request.
    assert all(task["title"] != "Morning brief" for task in client.get("/api/tasks").json())


def test_a_consented_delivery_is_listed_and_can_be_stopped(client: TestClient) -> None:
    _paired(client)
    created = client.post("/api/tasks", json={"title": "Morning brief", "description": "Summarise my day.", "deliver_to": WEBHOOKS, "deliver_consent": True})
    assert created.status_code == 201, created.text
    task_id = created.json()["task_id"]
    listed = client.get("/api/routine-deliveries").json()["deliveries"]
    assert [(row["task_id"], row["channel_name"], row["last_status"]) for row in listed] == [(task_id, "Ops room", None)]
    assert client.delete(f"/api/tasks/{task_id}/delivery").status_code == 200
    assert client.get("/api/routine-deliveries").json()["deliveries"] == []
    assert client.delete(f"/api/tasks/{task_id}/delivery").status_code == 404


def test_each_result_goes_through_the_channels_own_path(
    client: TestClient, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _paired(client)
    task_id = client.post(
        "/api/tasks", json={"title": "Morning brief", "description": "Summarise my day.", "deliver_to": WEBHOOKS, "deliver_consent": True}
    ).json()["task_id"]
    store = SQLiteStore(workspace)
    sent: list[tuple[Any, ...]] = []

    def fake(self: Any, principal_id: str, connector_id: str, text: str) -> ControlResult:
        sent.append((connector_id, text))
        return ControlResult(ok=True)

    monkeypatch.setattr("raiker.control.service.RuntimeControlService.deliver_routine_result", fake)
    assert routine_delivery.deliver(workspace, store, task_id=task_id, title="Morning brief", result="Three meetings.") == "delivered"
    assert sent == [(WEBHOOKS, "Morning brief\n\nThree meetings.")]
    assert client.get("/api/routine-deliveries").json()["deliveries"][0]["last_status"] == "delivered"
    assert routine_delivery.deliver(workspace, store, task_id="task_without_delivery", title="x", result="y") is None


def test_a_closed_channel_gate_refuses_the_send_and_says_so(client: TestClient, workspace: Path) -> None:
    _paired(client)
    task_id = client.post(
        "/api/tasks", json={"title": "Morning brief", "description": "Summarise my day.", "deliver_to": WEBHOOKS, "deliver_consent": True}
    ).json()["task_id"]
    store = SQLiteStore(workspace)
    # The pairing is not enabled and the channel gate is off by default: the
    # governed path refuses, and the routine says it was not delivered.
    assert routine_delivery.deliver(workspace, store, task_id=task_id, title="Morning brief", result="Done.") == "not_delivered"
    row = client.get("/api/routine-deliveries").json()["deliveries"][0]
    assert row["last_status"] == "not_delivered"
    assert row["last_reason"]


def test_a_long_result_is_cut_for_the_channel() -> None:
    text = routine_delivery.message("Brief", "x" * 10_000)
    assert len(text) <= routine_delivery.MAX_DELIVERY_CHARS
    assert text.endswith("…")
