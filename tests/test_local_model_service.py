"""Ollama running on this machine is available, and a chosen model stays checked.

The owner's decision of 2026-10-04: no Ollama model is hard-coded; when Ollama
is running Raiker offers the models it serves, remembers the one chosen, marks
it ready, and keeps checking both the service and that model.

What these hold:

* the liveness probe asks **loopback only**, never through a proxy, and reads
  an answer that is not Ollama's catalogue as not running;
* a running service makes the provider present even with no binary on PATH,
  and offers it without choosing a model;
* choosing a model checks it at once, and the background pass re-checks it so
  Ready follows the service up and down.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.contracts.ids import utc_now
from raiker.models import local_presence, local_service, local_watch
from raiker.models.contracts import ProviderModelInfo
from raiker.models.decision import ModelDecisionService
from raiker.models.exceptions import ProviderConnectionError
from raiker.models.readiness import ModelReadinessState
from raiker.models.router import ModelRouter
from raiker.models.session_state import ModelSessionState
from raiker.storage.sqlite import SQLiteStore

OLLAMA = "ollama-local-openai-compatible"


# ── the probe ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("endpoint", "root"),
    [
        ("http://127.0.0.1:11434/v1", "http://127.0.0.1:11434"),
        ("http://localhost:11434/v1/", "http://localhost:11434"),
        ("http://[::1]:11434", "http://[::1]:11434"),
        ("http://127.0.0.2:9000/v1", "http://127.0.0.2:9000"),
    ],
)
def test_service_root_accepts_this_machine(endpoint: str, root: str) -> None:
    assert local_service.service_root(endpoint) == root


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://192.168.1.20:11434/v1",
        "http://10.0.0.5:11434",
        "https://ollama.com/v1",
        "http://ollama-box:11434",
        "http://0.0.0.0:11434",
        "file:///etc/passwd",
        "",
    ],
)
def test_service_root_refuses_anything_off_this_machine(endpoint: str) -> None:
    assert local_service.service_root(endpoint) is None


class _Recorder:
    def __init__(self, response: httpx.Response | Exception) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def client(self, **kwargs: Any) -> Any:
        recorder = self

        class _Client:
            def __enter__(self) -> _Client:
                return self

            def __exit__(self, *_exc: object) -> None:
                return None

            def get(self, url: str) -> httpx.Response:
                recorder.calls.append((url, kwargs))
                if isinstance(recorder.response, Exception):
                    raise recorder.response
                return recorder.response

        return _Client()


@pytest.fixture
def real_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    """Undo the suite-wide stub so the probe itself can be tested."""
    monkeypatch.setattr(local_service, "probe", _original_probe)


_original_probe = local_service.probe


def test_probe_reads_the_catalogue_over_loopback_without_a_proxy(
    real_probe: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = _Recorder(
        httpx.Response(
            200,
            json={"models": [{"name": "llama3.2:3b"}, {"model": "qwen3:8b"}, {"name": "llama3.2:3b"}]},
        )
    )
    monkeypatch.setattr(local_service.httpx, "Client", recorder.client)
    answer = local_service.probe("ollama", "http://127.0.0.1:11434/v1")
    assert answer.running is True
    assert answer.models == ("llama3.2:3b", "qwen3:8b")
    url, options = recorder.calls[0]
    assert url == "http://127.0.0.1:11434/api/tags"
    assert options["trust_env"] is False
    assert options["follow_redirects"] is False


@pytest.mark.parametrize(
    "response",
    [
        httpx.ConnectError("refused"),
        httpx.ReadTimeout("slow"),
        httpx.Response(200, json={"data": []}),
        httpx.Response(200, text="Ollama is running"),
        httpx.Response(404, json={"models": []}),
    ],
)
def test_anything_but_a_catalogue_is_not_running(
    real_probe: None, monkeypatch: pytest.MonkeyPatch, response: httpx.Response | Exception
) -> None:
    monkeypatch.setattr(local_service.httpx, "Client", _Recorder(response).client)
    assert local_service.probe("ollama", "http://127.0.0.1:11434/v1").running is False


def test_probe_never_contacts_an_off_machine_endpoint(
    real_probe: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = _Recorder(httpx.Response(200, json={"models": [{"name": "x"}]}))
    monkeypatch.setattr(local_service.httpx, "Client", recorder.client)
    assert local_service.probe("ollama", "http://192.168.1.20:11434/v1").running is False
    assert local_service.liveness("ollama", "http://192.168.1.20:11434/v1") is None
    assert recorder.calls == []


def test_liveness_is_cached_for_its_window(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def probe(runtime: str, endpoint: str, *, timeout: float = 0.0) -> local_service.ServiceLiveness:
        calls.append(endpoint)
        return local_service.ServiceLiveness(runtime, endpoint, True, ("m",), utc_now())

    monkeypatch.setattr(local_service, "probe", probe)
    endpoint = "http://127.0.0.1:11434/v1"
    local_service.liveness("ollama", endpoint, now=100.0)
    local_service.liveness("ollama", endpoint, now=105.0)
    assert len(calls) == 1
    local_service.liveness("ollama", endpoint, now=100.0 + local_service.LIVENESS_TTL_SECONDS + 1)
    assert len(calls) == 2
    local_service.liveness("ollama", endpoint, force=True, now=100.0)
    assert len(calls) == 3
    assert local_service.liveness("lm-studio", endpoint) is None


# ── the Models read ──────────────────────────────────────────────────────────


@pytest.fixture
def workspace(tmp_path: Path, seed_account: Any) -> tuple[Path, str]:
    ws = tmp_path / "local_model_service"
    ws.mkdir()
    principal_id, _token = seed_account(ws, "owner", "right-pass-123")
    return ws, principal_id


@pytest.fixture
def client(workspace: tuple[Path, str]) -> TestClient:
    return TestClient(create_app(workspace[0]))


@pytest.fixture
def token(workspace: tuple[Path, str]) -> str:
    raw, _ = ApiSessionStore(workspace[0]).create_session(workspace[1])
    return raw


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _serving(monkeypatch: pytest.MonkeyPatch, *models: str, running: bool = True) -> None:
    def probe(runtime: str, endpoint: str, *, timeout: float = 0.0) -> local_service.ServiceLiveness:
        return local_service.ServiceLiveness(runtime, endpoint, running, models, utc_now())

    local_service.forget()
    monkeypatch.setattr(local_service, "probe", probe)

    async def catalogue(_router: ModelRouter, _profile: object) -> list[ProviderModelInfo]:
        if not running:
            raise ProviderConnectionError("provider_connection_failed")
        return [ProviderModelInfo(id=model, owned_by="library") for model in models]

    monkeypatch.setattr(ModelRouter, "alist_models_for_profile", catalogue)


def _ollama(body: dict[str, Any]) -> dict[str, Any]:
    return next(p for p in body["profiles"] if p["profile_id"] == OLLAMA)


def test_running_ollama_is_present_with_no_binary_and_chooses_nothing(
    client: TestClient, token: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(local_presence.shutil, "which", lambda _name: None)
    _serving(monkeypatch, "llama3.2:3b", "qwen3:8b")
    body = client.get("/api/models", headers=_auth(token)).json()
    ollama = _ollama(body)
    assert ollama["provider_running"] is True
    assert ollama["provider_detected"] is True
    assert ollama["model"] == "<model>"
    assert ollama["selected"] is False
    assert body["current_profile_id"] is None
    assert "gemma" not in str(body)


def test_stopped_ollama_reads_as_not_running(
    client: TestClient, token: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(local_presence.shutil, "which", lambda _name: None)
    _serving(monkeypatch, running=False)
    ollama = _ollama(client.get("/api/models", headers=_auth(token)).json())
    assert ollama["provider_running"] is False
    assert ollama["provider_detected"] is False


def test_readiness_line_offers_a_choice_when_only_ollama_is_running(
    workspace: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _serving(monkeypatch, "llama3.2:3b")
    root, principal_id = workspace
    decision = ModelDecisionService(SQLiteStore(root)).decide(principal_id, "chat")
    steps = {step["id"]: step["state"] for step in decision.steps}
    assert steps["connect"] == "done"
    assert steps["choose"] == "blocked"
    assert decision.next_action == {"label": "Choose a model", "target": "models"}


def test_choosing_an_ollama_model_is_remembered_and_ready_at_once(
    client: TestClient, token: str, workspace: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _serving(monkeypatch, "llama3.2:3b", "qwen3:8b")
    chosen = client.put(
        "/api/model-selection",
        headers=_auth(token),
        json={"profile_id": OLLAMA, "model": "qwen3:8b"},
    )
    assert chosen.status_code == 200, chosen.text
    body = client.get("/api/models", headers=_auth(token)).json()
    ollama = _ollama(body)
    assert body["current_profile_id"] == OLLAMA
    assert body["current_model"] == "qwen3:8b"
    assert ollama["selected"] is True
    assert ollama["ready"] is True
    # Remembered: a new app on the same workspace reads the same choice.
    fresh = TestClient(create_app(workspace[0]))
    again = fresh.get("/api/models", headers=_auth(token)).json()
    assert again["current_model"] == "qwen3:8b"


# ── the background pass ──────────────────────────────────────────────────────


def _choose(root: Path, principal_id: str, model: str) -> SQLiteStore:
    store = SQLiteStore(root)
    store.save_principal_model_state(
        principal_id, ModelSessionState(session_id=principal_id, profile_id=OLLAMA, model=model)
    )
    store.save_configured_model(principal_id, OLLAMA, model)
    return store


def _state(store: SQLiteStore, principal_id: str, model: str) -> ModelReadinessState:
    rows = {
        row.key.model: row for row in store.list_model_readiness(principal_id, OLLAMA)
    }
    return rows[model].state


def test_the_watch_follows_the_service_down_and_back_up(
    workspace: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, principal_id = workspace
    store = _choose(root, principal_id, "llama3.2:3b")

    _serving(monkeypatch, "llama3.2:3b")
    assert asyncio.run(local_watch.recheck_local_selections(store)) == 1
    assert _state(store, principal_id, "llama3.2:3b") is ModelReadinessState.READY

    _serving(monkeypatch, running=False)
    asyncio.run(local_watch.recheck_local_selections(store))
    assert _state(store, principal_id, "llama3.2:3b") is ModelReadinessState.RUNTIME_STOPPED

    _serving(monkeypatch, "qwen3:8b")
    asyncio.run(local_watch.recheck_local_selections(store))
    assert _state(store, principal_id, "llama3.2:3b") is ModelReadinessState.MODEL_MISSING

    _serving(monkeypatch, "llama3.2:3b", "qwen3:8b")
    asyncio.run(local_watch.recheck_local_selections(store))
    assert _state(store, principal_id, "llama3.2:3b") is ModelReadinessState.READY


def test_the_watch_checks_nothing_nobody_chose(
    workspace: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, principal_id = workspace
    _serving(monkeypatch, "llama3.2:3b")
    store = SQLiteStore(root)
    assert asyncio.run(local_watch.recheck_local_selections(store)) == 0
    assert store.list_model_readiness(principal_id, OLLAMA) == []


def test_the_watch_only_reads_watched_local_profiles(
    workspace: tuple[Path, str]
) -> None:
    root, principal_id = workspace
    store = SQLiteStore(root)
    store.save_configured_model(principal_id, "anthropic-hosted", "claude-haiku-4-5")
    store.save_configured_model(principal_id, OLLAMA, "llama3.2:3b")
    assert local_watch.owner_targets(store, principal_id) == [(OLLAMA, "llama3.2:3b")]
