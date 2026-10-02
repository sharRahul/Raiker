"""How each verified API operation is reached with a non-empty answer.

``tests/test_api_contract_responses.py`` calls every operation in :data:`CASES`
and matches its real response to the view the OpenAPI document attaches. Each
domain keeps its cases in its own module; this one merges them, and refuses an
operation claimed twice.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

#: Where to send the request: a path; a path and the JSON body; or those and the
#: headers to send instead of the bootstrap owner's.
Call = str | tuple[str, Any] | tuple[str, Any, dict[str, str]]
Seed = Callable[[Path, TestClient, dict[str, str]], Call]
Cases = dict[tuple[str, str], Seed]


def plain(path: str, body: Any = None) -> Seed:
    return lambda _ws, _client, _h: path if body is None else (path, body)


def first(client: TestClient, h: dict[str, str], path: str, key: str) -> str:
    """The ``key`` of the first row a list route answers — an id to address."""
    rows = client.get(path, headers=h).json()
    assert rows, f"{path} answered nothing to address"
    return str(rows[0][key])


def then(seed: Seed, build: Callable[[TestClient, dict[str, str]], Call]) -> Seed:
    """Run ``seed`` for its state, then address what it made."""

    def run(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
        seed(ws, client, h)
        return build(client, h)

    return run


def with_turn(path: str) -> Seed:
    def seed(_ws: Path, client: TestClient, h: dict[str, str]) -> str:
        client.post("/api/prompts", json={"text": "hello"}, headers=h)
        return path

    return seed




def fresh(seed: Seed) -> Seed:
    """Mark ``seed`` as needing a workspace with no owner yet — one it will register."""
    seed.fresh = True  # type: ignore[attr-defined]
    return seed


def patched(seed: Seed, patch: Callable[[Any], None]) -> Seed:
    """Run ``patch(monkeypatch)`` before ``seed`` — a provider the case must not reach."""
    seed.patch = patch  # type: ignore[attr-defined]
    return seed


def patch_of(seed: Seed) -> Callable[[Any], None] | None:
    return getattr(seed, "patch", None)


def is_fresh(seed: Seed) -> bool:
    return bool(getattr(seed, "fresh", False))


def merge(*groups: Cases) -> Cases:
    merged: Cases = {}
    for group in groups:
        overlap = set(merged) & set(group)
        assert not overlap, f"claimed twice: {sorted(overlap)}"
        merged.update(group)
    return merged
