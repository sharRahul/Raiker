# SPDX-License-Identifier: Apache-2.0
"""Raiker's built-in embedding model: nomic-embed-text, on this computer.

Semantic recall needs an embedding model, and until now a default install had
none, so Memory searched with the labelled hashing fallback and a paraphrase
("where should backups go") missed the memory it meant ("the owner prefers the
encrypted NAS target"). Choosing a hosted embedding sent memories off the
machine for the sake of search.

``nomic-embed-text`` (v1.5, Apache-2.0, 137M parameters, 768 dimensions,
8,192-token context) is small enough to run beside a chat model on a laptop
processor and good enough to be the default. Raiker reaches it through the
owner's local Ollama, which verifies the model's digests itself, so nothing
here downloads a file on a hope:

* :func:`task_text` adds the task prefixes the model was trained with —
  ``search_document:`` for what is stored, ``search_query:`` for a search.
  Without them the same model ranks noticeably worse, and a vector stored
  without a prefix cannot be compared with a query embedded with one.
* :func:`local_status` says whether Ollama is running and holds the model.
* :func:`pull` asks Ollama to fetch it, the way ``ollama pull`` does.

The background indexer (:mod:`raiker.memory.background_index`) uses these to
keep the recall space current without the owner pressing anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import httpx

#: The model as Ollama names it.
MODEL = "nomic-embed-text"
PROVIDER = "ollama"
PROFILE_ID = "ollama-local-openai-compatible"
DIMENSIONS = 768
CONTEXT_TOKENS = 8192
LICENCE = "Apache-2.0"
#: The space label stored with every vector, as `index_memories` names it.
EMBEDDING_SPACE = f"{PROVIDER}:{MODEL}"
OLLAMA_ORIGIN = "http://127.0.0.1:11434"

Role = Literal["document", "query"]
_PREFIX: dict[str, str] = {"document": "search_document: ", "query": "search_query: "}


def is_nomic(model: str | None) -> bool:
    return bool(model) and "nomic-embed" in str(model).lower()


def task_text(model: str | None, text: str, role: Role) -> str:
    """``text`` with the task prefix ``model`` expects, once; others unchanged."""
    if not is_nomic(model):
        return text
    prefix = _PREFIX[role]
    if text.startswith(tuple(_PREFIX.values())):
        return text
    return prefix + text


@dataclass(frozen=True)
class LocalEmbeddingStatus:
    """Whether the built-in embedding model can answer right now."""

    #: ``ready`` · ``model_missing`` · ``ollama_unreachable``
    state: str
    model: str = MODEL
    dimensions: int = DIMENSIONS

    @property
    def ready(self) -> bool:
        return self.state == "ready"


def _client(timeout: float) -> httpx.Client:
    # Loopback only, and never through an ambient proxy.
    return httpx.Client(timeout=timeout, trust_env=False)


def local_status(origin: str = OLLAMA_ORIGIN, *, client: Any = None) -> LocalEmbeddingStatus:
    """Ask the local Ollama whether it holds ``nomic-embed-text``."""
    owned = client is None
    http = client or _client(2.0)
    try:
        answer = http.get(f"{origin}/api/tags")
        if answer.status_code != 200:
            return LocalEmbeddingStatus("ollama_unreachable")
        names = {
            str(item.get("name") or item.get("model") or "")
            for item in (answer.json().get("models") or [])
            if isinstance(item, dict)
        }
    except (httpx.HTTPError, ValueError, AttributeError):
        return LocalEmbeddingStatus("ollama_unreachable")
    finally:
        if owned:
            http.close()
    held = any(name == MODEL or name.startswith(f"{MODEL}:") for name in names)
    return LocalEmbeddingStatus("ready" if held else "model_missing")


def pull(origin: str = OLLAMA_ORIGIN, *, client: Any = None, timeout: float = 900.0) -> bool:
    """Ask the local Ollama to fetch ``nomic-embed-text``. True when it succeeded."""
    owned = client is None
    http = client or _client(timeout)
    try:
        answer = http.post(f"{origin}/api/pull", json={"model": MODEL, "stream": False})
        return answer.status_code == 200 and str(answer.json().get("status", "")) == "success"
    except (httpx.HTTPError, ValueError, AttributeError):
        return False
    finally:
        if owned:
            http.close()
