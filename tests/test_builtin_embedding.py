"""Raiker's built-in embedding model and the worker that keeps recall current.

nomic-embed-text runs on the owner's local Ollama. These tests pin the three
things that make it correct and safe: the task prefixes the model was trained
with, Ollama's own answer about whether the model is there, and a background
worker that indexes only where the owner already lets model work run without
asking.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from raiker.memory import background_index
from raiker.models import builtin_embedding
from raiker.models.builtin_embedding import LocalEmbeddingStatus, task_text


def test_task_prefixes_are_added_once_and_only_for_nomic() -> None:
    assert task_text("nomic-embed-text", "backups go to the NAS", "document") == (
        "search_document: backups go to the NAS"
    )
    assert task_text("nomic-embed-text:latest", "where do backups go", "query") == (
        "search_query: where do backups go"
    )
    assert task_text("nomic-embed-text", "search_query: already", "query") == "search_query: already"
    assert task_text("text-embedding-3-small", "unchanged", "query") == "unchanged"


def _transport(handler: Any) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_local_status_reads_ollamas_own_model_list() -> None:
    def held(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": "nomic-embed-text:latest"}, {"name": "qwen3:8b"}]})

    assert builtin_embedding.local_status(client=_transport(held)).state == "ready"

    def missing(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": "qwen3:8b"}]})

    assert builtin_embedding.local_status(client=_transport(missing)).state == "model_missing"

    def down(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    assert builtin_embedding.local_status(client=_transport(down)).state == "ollama_unreachable"


def test_pull_asks_ollama_for_the_model_by_name() -> None:
    sent: list[dict[str, Any]] = []

    def pull(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"status": "success"})

    assert builtin_embedding.pull(client=_transport(pull)) is True
    assert sent == [{"model": "nomic-embed-text", "stream": False}]


def test_the_ollama_profile_declares_its_embedding_model() -> None:
    from raiker.vector.backends import embedding_capable_profiles

    offered = {row["space"] for row in embedding_capable_profiles() if row["local_only"]}
    assert builtin_embedding.EMBEDDING_SPACE in offered


@pytest.fixture
def owned_workspace(tmp_path: Path) -> Path:
    from raiker.auth.accounts import AccountService
    from raiker.storage.sqlite import SQLiteStore

    SQLiteStore(tmp_path).bootstrap()
    AccountService(tmp_path).register("owner", "a-long-password-1")
    return tmp_path


def test_the_worker_waits_for_permission_and_never_asks(
    owned_workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    routed: list[str] = []

    def route(_store: Any, owner: str) -> tuple[bool, int, str | None]:
        routed.append(owner)
        return True, 1, None

    monkeypatch.setattr(background_index, "_may_run", lambda _store, _owner: False)
    outcome = background_index.run_once(
        owned_workspace,
        status=lambda: LocalEmbeddingStatus("ready"),
        pull=lambda: True,
        route=route,
    )
    assert outcome.state == "waiting_for_permission"
    assert routed == []
    assert background_index.read_status(owned_workspace)["state"] == "waiting_for_permission"  # type: ignore[index]


def test_the_worker_fetches_a_missing_model_then_indexes(
    owned_workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(background_index, "_may_run", lambda _store, _owner: True)
    states = iter(["model_missing", "ready"])
    pulls: list[bool] = []

    def pull() -> bool:
        pulls.append(True)
        return True

    outcome = background_index.run_once(
        owned_workspace,
        status=lambda: LocalEmbeddingStatus(next(states)),
        pull=pull,
        route=lambda _store, _owner: (True, 3, None),
    )
    assert pulls == [True]
    assert outcome.state == "indexed" and outcome.indexed == 3


def test_nothing_new_reads_as_up_to_date_and_ollama_down_as_itself(
    owned_workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(background_index, "_may_run", lambda _store, _owner: True)
    current = background_index.run_once(
        owned_workspace,
        status=lambda: LocalEmbeddingStatus("ready"),
        pull=lambda: False,
        route=lambda _store, _owner: (False, 0, "no_memories_to_index"),
    )
    assert current.state == "up_to_date"
    down = background_index.run_once(
        owned_workspace,
        status=lambda: LocalEmbeddingStatus("ollama_unreachable"),
        pull=lambda: False,
        route=lambda _store, _owner: (True, 0, None),
    )
    assert down.state == "ollama_unreachable"


def test_the_worker_can_be_turned_off(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(background_index.DISABLE_ENV, "off")
    assert background_index.start(tmp_path) is None
