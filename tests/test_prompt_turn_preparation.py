"""GCR-12 — one preparation for a turn, two ways of saying it was refused.

``/api/prompts`` and ``/api/prompts/stream`` each carried their own copy of the
preparation sequence, and the copies had begun to differ. They now share
``_prepare_turn``; what stays different is only how each transport reports a
refusal. These tests hold the two to the same decision for the same request —
the *answer* may be a 409 or a final event, the *verdict* may not differ.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from raiker.api import routes_prompts
from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import utc_now
from raiker.contracts.models import User
from raiker.storage.sqlite import SQLiteStore

_MODEL = {"model_profile": "ollama-local-openai-compatible", "model": "gemma4:31b-cloud"}


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "prep"
    root.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=root)
    return root


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


@pytest.fixture
def headers(workspace: Path) -> dict[str, str]:
    token, _ = ApiSessionStore(workspace).create_session("principal_owner")
    return {"Authorization": f"Bearer {token}"}


def _final_frame(text: str) -> dict[str, Any]:
    frames = [json.loads(line.removeprefix("data: ")) for line in text.splitlines() if line.startswith("data: ")]
    assert len(frames) == 1
    return frames[0]


def test_not_ready_is_one_verdict_in_two_shapes(client: TestClient, headers: dict[str, str]) -> None:
    body = {"text": "hello", **_MODEL}
    blocking = client.post("/api/prompts", headers=headers, json=body)
    streamed = client.post("/api/prompts/stream", headers=headers, json=body)

    assert blocking.status_code == 409
    assert streamed.status_code == 200
    frame = _final_frame(streamed.text)
    assert frame["event_type"] == "model_not_ready"
    assert frame["payload"] == blocking.json()["detail"]
    assert frame["response"]["status"] == "failed"


def test_an_invalid_request_is_answered_in_the_body_by_both(
    client: TestClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from raiker.contracts.models import ContractValidationError

    def invalid(*args: Any, **kwargs: Any) -> Any:
        raise ContractValidationError("prompt.text: required")

    monkeypatch.setattr(routes_prompts, "_build_envelope", invalid)
    body = {"text": "hello", **_MODEL}
    blocking = client.post("/api/prompts", headers=headers, json=body)
    streamed = client.post("/api/prompts/stream", headers=headers, json=body)

    assert blocking.status_code == 200
    frame = _final_frame(streamed.text)
    assert frame["response"]["status"] == blocking.json()["status"]
    assert frame["response"]["message"] == blocking.json()["message"]


def test_a_strangers_session_is_404_on_both(
    client: TestClient, headers: dict[str, str], workspace: Path
) -> None:
    store = SQLiteStore(workspace)
    store.insert_user(User("someone_else", "Someone", None, True, utc_now(), utc_now()))
    store.create_session("sess_someone", str(workspace), user_id="someone_else")
    body = {"text": "hello", "session_id": "sess_someone", **_MODEL}
    assert client.post("/api/prompts", headers=headers, json=body).status_code == 404
    assert client.post("/api/prompts/stream", headers=headers, json=body).status_code == 404


def test_a_refused_turn_records_nothing_on_either(
    client: TestClient, headers: dict[str, str], workspace: Path
) -> None:
    store = SQLiteStore(workspace)
    before = (len(store.list_sessions()), store.count_events(), store.count_tasks())
    body = {"text": "hello", **_MODEL}
    client.post("/api/prompts", headers=headers, json=body)
    client.post("/api/prompts/stream", headers=headers, json=body)
    assert (len(store.list_sessions()), store.count_events(), store.count_tasks()) == before
