"""DEC-02 steps 2, 4 and 5 — one server-backed *Needs your attention* feed.

Home built its attention rail in the browser from approvals, readiness and
blocked tasks, so a proposed memory, a delivery that did not arrive or an MCP
tool held for review waited on its own page and nowhere the owner starts from.
``GET /api/attention`` reads each subsystem's own record: every item has a
stable id, a severity, a title and reason, the record it came from, the one
action that resolves it and when it began; it disappears when the subsystem
says it is resolved; it carries references, never copied content; and a
subsystem that cannot be read is named rather than counted as clear.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id, utc_now
from raiker.control.dashboard import DashboardService
from raiker.memory.candidates import MemoryCandidate
from raiker.storage.sqlite import SQLiteStore

OWNER = "principal_owner"
PRIVATE = "The owner's sister is called Priya"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


def _headers(client: TestClient) -> dict[str, str]:
    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _feed(workspace: Path) -> dict[str, Any]:
    client = TestClient(create_app(workspace))
    answer = client.get("/api/attention", headers=_headers(client))
    assert answer.status_code == 200, answer.text
    return answer.json()


def _propose(store: SQLiteStore) -> str:
    candidate_id = new_id("memcand_")
    store.insert_memory_candidate(
        MemoryCandidate(
            candidate_id=candidate_id, source_event_id="evt", memory_type="project",
            scope="project", text=PRIVATE, sensitivity="personal", confidence=0.9,
            decision="deferred", created_at=utc_now(),
        ),
        owner_principal_id=OWNER,
    )
    return candidate_id


def test_an_idle_workspace_has_nothing_and_says_it_read_everything(workspace: Path) -> None:
    assert _feed(workspace) == {"items": [], "unknown": []}


def test_each_subsystem_raises_its_own_item_by_reference(workspace: Path) -> None:
    store = SQLiteStore(workspace)
    _propose(store)
    store.insert_channel_receipt(
        receipt_id="act_failed", connector_id="channel.webhooks", pairing_id=None,
        direction="outbound", kind="message",
        stages={"queued_at": utc_now(), "failed_at": utc_now()}, reason_code="delivery_failed:URLError",
    )
    server_id = new_id("mcp_")
    store.create_mcp_server(
        server_id=server_id, principal_id=OWNER, name="weather",
        command=["python", "weather.py"], status="connected", tools=["forecast"],
        tool_schemas=[{"name": "forecast", "description": "Forecast.", "inputSchema": {"type": "object"}}],
    )

    feed = _feed(workspace)

    by_kind = {item["origin_kind"]: item for item in feed["items"]}
    assert {"memory_proposals", "channel"} <= set(by_kind)
    proposals = by_kind["memory_proposals"]
    assert proposals["id"] == "memory:proposals" and proposals["severity"] == "waiting"
    assert proposals["href"] == "#/memory?tab=suggestions" and proposals["since"]
    assert by_kind["channel"]["origin_id"] == "channel.webhooks"
    # References and counts, never the proposed words.
    assert PRIVATE not in str(feed)
    for item in feed["items"]:
        assert set(item) == {
            "id", "severity", "title", "reason", "origin_kind", "origin_id", "href",
            "action_label", "since",
        }


def test_an_item_goes_when_its_subsystem_resolves_it(workspace: Path) -> None:
    store = SQLiteStore(workspace)
    candidate_id = _propose(store)
    assert any(item["id"] == "memory:proposals" for item in _feed(workspace)["items"])

    assert DashboardService(workspace).decide_memory_proposal(
        candidate_id, decision="rejected", edited_text=None, reason="not true",
        expected_decision="deferred", acting_principal_id=OWNER,
    ).ok

    assert not any(item["id"] == "memory:proposals" for item in _feed(workspace)["items"])


def test_a_subsystem_that_cannot_be_read_is_named_not_cleared(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("store unavailable")

    monkeypatch.setattr(SQLiteStore, "list_channel_deliveries_to_review", broken)
    assert _feed(workspace)["unknown"] == ["messaging"]


def test_containment_leads_the_feed(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = SQLiteStore(workspace)
    _propose(store)
    monkeypatch.setattr(
        DashboardService,
        "list_security_health",
        lambda self, principal_id: [{
            "source": "mcp_monitor", "subject_id": "mcp_1", "code": "egress_blocked",
            "state": "alerting", "finding_id": None, "updated_at": utc_now(),
        }],
    )
    items = _feed(workspace)["items"]
    assert items[0]["severity"] == "containment"
