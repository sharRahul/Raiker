"""The task receipt (Quiet UI 06, QUI-F16): read from a turn's own records.

Every field comes from the audit events the runtime wrote for the turn. A call
that failed or was refused is not on the receipt, because it did not happen;
the approval time is the time the owner's decision was recorded.
"""

from __future__ import annotations

from typing import Any

from raiker.control.turn_receipt import build_turn_receipt

LOCAL = frozenset({"ollama"})


def _proposed(action_id: str, tool: str, **arguments: Any) -> dict[str, Any]:
    return {"event_type": "action_proposed", "payload": {"action": {"action_id": action_id, "tool_name": tool, "arguments": arguments}}}


def _done(action_id: str, status: str = "success") -> dict[str, Any]:
    return {"event_type": "tool_completed", "payload": {"action_id": action_id, "status": status, "output": {"status": status}}}


def _model(provider: str = "anthropic", model: str = "claude-haiku-4-5", **usage: int) -> list[dict[str, Any]]:
    return [
        {"event_type": "model_request_started", "payload": {"model": model, "provider": provider}},
        {"event_type": "model_request_completed", "payload": {"usage": usage}},
    ]


def test_a_read_only_turn_counts_its_reads_and_sends_nothing_else() -> None:
    events = [
        *_model(input_tokens=300, output_tokens=60),
        _proposed("a1", "read_file", path="notes.txt"), _done("a1"),
        _proposed("a2", "read_file", path="plan.md"), _done("a2"),
        *_model(input_tokens=400, output_tokens=50, cache_read_tokens=8000),
    ]
    receipt = build_turn_receipt("turn_1", events, local_providers=LOCAL)
    assert receipt["model"] == "claude-haiku-4-5"
    assert receipt["local"] is False
    assert receipt["reads"] == {"file": 2}
    assert receipt["changes"] == []
    assert receipt["left_computer"] == []
    assert receipt["_usage"] == {"input_tokens": 700, "output_tokens": 110, "cache_read_tokens": 8000, "cache_write_tokens": 0}


def test_a_change_carries_its_approval_time_and_a_failure_is_not_listed() -> None:
    events = [
        *_model(),
        _proposed("w1", "write_file", path="reply.md"),
        {"event_type": "approval_received", "timestamp": "2026-10-24T10:41:00Z", "payload": {"action_id": "w1"}},
        {"event_type": "approval_executed", "payload": {"action_id": "w1", "status": "success"}},
        _proposed("w2", "write_file", path="other.md"), _done("w2", "failed"),
        _proposed("s1", "web_search", query="flights"), _done("s1"),
    ]
    receipt = build_turn_receipt("turn_2", events, local_providers=LOCAL)
    assert receipt["changes"] == [{"label": "Write file", "approved_at": "2026-10-24T10:41:00Z"}]
    assert receipt["reads"] == {"web page": 1}
    assert receipt["left_computer"] == ["the web"]


def test_a_local_model_is_said_to_be_local_and_bookkeeping_is_not_a_read() -> None:
    events = [*_model(provider="ollama", model="llama3"), _proposed("p1", "update_plan"), _done("p1")]
    receipt = build_turn_receipt("turn_3", events, local_providers=LOCAL)
    assert receipt["local"] is True
    assert receipt["reads"] == {}


def test_a_connector_read_names_its_service() -> None:
    events = [*_model(), _proposed("g1", "gmail_read", query="from:anna"), _done("g1")]
    receipt = build_turn_receipt("turn_4", events, local_providers=LOCAL)
    assert receipt["reads"] == {"message": 1}
    assert receipt["left_computer"] == ["Gmail"]


def test_a_task_receipt_sums_its_own_conversation(tmp_path: Any, monkeypatch: Any) -> None:
    """A routine's receipt adds up its turns; one unpriced billable turn makes the cost unknown."""
    from fastapi.testclient import TestClient

    from raiker.api.app import create_app
    from raiker.control.dashboard import DashboardService
    from raiker.storage.sqlite import SQLiteStore

    client = TestClient(create_app(tmp_path))
    token = client.post("/api/auth/register", json={"username": "owner", "password": "a-long-password-1"}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    store = SQLiteStore(tmp_path)
    principal = client.get("/api/auth/whoami", headers=h).json()["principal_id"]
    user_id = store.principal_user_id(principal)
    from raiker.contracts.models import TaskRecord

    store.create_session("sess_run", str(tmp_path), title="Morning brief", user_id=user_id)
    store.insert_task(TaskRecord(
        task_id="task_brief", session_id="sess_run", title="Morning brief", objective="Brief me.",
        status="completed", created_at="2026-10-26T00:00:00Z", updated_at="2026-10-26T00:00:00Z",
        thread_session_id="sess_run",
    ))
    for turn_id in ("turn_a", "turn_b"):
        store.insert_turn("sess_run", turn_id, "Brief me.")
        store.complete_turn(turn_id, "completed", "Done.")
    receipts = {
        "turn_a": {"model": "claude-haiku-4-5", "local": False, "reads": {"web page": 2}, "changes": [],
                   "left_computer": ["the web"], "cost_usd": 0.01, "cost_basis": "priced"},
        "turn_b": {"model": "claude-haiku-4-5", "local": False, "reads": {"web page": 1, "file": 1},
                   "changes": [{"label": "Send email", "approved_at": "2026-10-26T08:00:00Z"}],
                   "left_computer": ["Gmail", "the web"], "cost_usd": 0.02, "cost_basis": "priced"},
    }
    monkeypatch.setattr(
        DashboardService, "turn_receipt",
        lambda _self, _session, turn_id, **_kw: {"turn_id": turn_id, **receipts[turn_id]},
    )
    answer = client.get("/api/tasks/task_brief/receipt", headers=h)
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["turns"] == 2
    assert body["models"] == ["claude-haiku-4-5"]
    assert body["reads"] == {"web page": 3, "file": 1}
    assert body["changes"] == [{"label": "Send email", "approved_at": "2026-10-26T08:00:00Z"}]
    assert sorted(body["left_computer"]) == ["Gmail", "the web"]
    assert body["cost_basis"] == "priced"
    assert abs(body["cost_usd"] - 0.03) < 1e-9
    receipts["turn_b"]["cost_basis"] = "unknown"
    receipts["turn_b"]["cost_usd"] = None
    assert client.get("/api/tasks/task_brief/receipt", headers=h).json()["cost_basis"] == "unknown"
    assert client.get("/api/tasks/task_nope/receipt", headers=h).status_code == 404
