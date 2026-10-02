"""A route's OpenAPI response is attached only after its real response is matched.

OPT-01 Stage A. ``scripts/api_contract.py`` finds the routes whose response is a
fields-only read-model view, but a schema in the OpenAPI document is a claim
about the wire, and the scope decision allows it only "where contract tests
establish that they describe the actual serialized response". This is that
test: each case seeds what its route needs, calls the route, and requires a
non-empty answer whose every object has exactly the view's keys and whose every
value validates against the view's field types. ``VERIFIED`` in the script must
be exactly the cases here — a claim with no test, or a test with no claim, fails.
"""

from __future__ import annotations

import dataclasses
import typing
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.memory.store import MemoryGovernance, write_memory
from raiker.storage.sqlite import SQLiteStore
from scripts.api_contract import VERIFIED, build_app, contracts
from tests.factories import tool_action

Seed = Callable[[Path, TestClient, dict[str, str]], str]


def _plain(path: str) -> Seed:
    return lambda _ws, _client, _h: path


def _with_turn(path: str) -> Seed:
    def seed(_ws: Path, client: TestClient, h: dict[str, str]) -> str:
        client.post("/api/prompts", json={"text": "hello"}, headers=h)
        return path

    return seed


def _approval(_ws: Path, _client: TestClient, _h: dict[str, str]) -> str:
    store = SQLiteStore(_ws)
    store.create_session("sess_c", str(_ws))
    action = tool_action(
        "write_file", {"path": "c.txt", "text": "hi"}, action_id="act_c",
        risk_level="high", requires_approval=True,
    )
    store.insert_tool_action(action, session_id="sess_c", turn_id="turn_c", status="approval_required")
    store.insert_approval("appr_c", action)
    return "/api/approvals"


def _memory(ws: Path, _client: TestClient, _h: dict[str, str]) -> str:
    write_memory(
        "Remember this", workspace_root=ws, store=SQLiteStore(ws),
        governance=MemoryGovernance(
            "evt_c", "", None, "test", 1.0, 1.0, "until_forget", "approved", "principal_owner"
        ),
    )
    return "/api/memory"


def _task(ws: Path, _client: TestClient, _h: dict[str, str]) -> str:
    from raiker.events.writer import EventLogWriter
    from raiker.tasks.manager import TaskManager

    store = SQLiteStore(ws)
    store.create_session("sess_t", str(ws))
    TaskManager(store, EventLogWriter(store)).create_task(session_id="sess_t", title="t", objective="o")
    return "/api/tasks"


def _project(_ws: Path, client: TestClient, h: dict[str, str]) -> str:
    client.post("/api/projects", json={"name": "Alpha"}, headers=h)
    return "/api/projects"


def _repo(ws: Path, client: TestClient, h: dict[str, str]) -> str:
    (ws / "projects" / "app").mkdir(parents=True)
    client.post("/api/code/repos", json={"kind": "local", "path": "projects/app"}, headers=h)
    return "/api/code/repos"


def _mcp(suffix: str) -> Seed:
    def seed(_ws: Path, _client: TestClient, _h: dict[str, str]) -> str:
        store = SQLiteStore(_ws)
        store.create_mcp_server(
            server_id="mcp_contract", principal_id="principal_owner", name="contract",
            command=["python", "server.py"], template="python-stdio-echo", status="connected",
        )
        store.insert_mcp_session_log(
            server_id="mcp_contract", principal_id="principal_owner", transport="stdio",
            operation="tools/list", hosts=[], tool_calls=0, bytes_in=0, bytes_out=0,
            error_count=0, outcome="ok", started_at="2026-07-18T10:00:00Z",
        )
        return "/api/mcp/servers" + suffix

    return seed


#: (method, path) → how to reach a non-empty answer from it.
CASES: dict[tuple[str, str], Seed] = {
    ("GET", "/api/approvals"): _approval,
    ("GET", "/api/capability-gates"): _plain("/api/capability-gates"),
    ("GET", "/api/checkpoints"): _with_turn("/api/checkpoints"),
    ("GET", "/api/code/repos"): _repo,
    ("GET", "/api/connections"): _plain("/api/connections"),
    ("GET", "/api/events"): _with_turn("/api/events"),
    ("GET", "/api/extensions"): _plain("/api/extensions"),
    ("GET", "/api/mcp/servers"): _mcp(""),
    ("GET", "/api/mcp/servers/{server_id}/sessions"): _mcp("/mcp_contract/sessions"),
    ("GET", "/api/memory"): _memory,
    ("GET", "/api/projects"): _project,
    ("GET", "/api/runtime-mode"): _plain("/api/runtime-mode"),
    ("GET", "/api/runtime-readiness"): _plain("/api/runtime-readiness"),
    ("GET", "/api/sessions"): _with_turn("/api/sessions"),
    ("GET", "/api/tasks"): _task,
    ("GET", "/api/work-threads"): _with_turn("/api/work-threads"),
    ("GET", "/api/work-threads/page"): _with_turn("/api/work-threads/page"),
}


def _check(annotation: Any, value: Any, where: str) -> None:
    """``value`` is exactly what ``annotation`` describes: keys, then types."""
    origin = typing.get_origin(annotation)
    if origin in (list, tuple) and typing.get_args(annotation):
        inner = typing.get_args(annotation)[0]
        if dataclasses.is_dataclass(inner):
            assert isinstance(value, list), f"{where}: expected a list"
            for index, item in enumerate(value):
                _check(inner, item, f"{where}[{index}]")
            return
    if isinstance(annotation, type) and dataclasses.is_dataclass(annotation):
        assert isinstance(value, dict), f"{where}: expected an object"
        hints = typing.get_type_hints(annotation)
        names = [field.name for field in dataclasses.fields(annotation)]
        assert set(value) == set(names), (
            f"{where}: keys differ — missing {sorted(set(names) - set(value))}, "
            f"extra {sorted(set(value) - set(names))}"
        )
        for name in names:
            _check(hints[name], value[name], f"{where}.{name}")
        return
    TypeAdapter(annotation).validate_python(value)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


def test_every_verified_route_has_a_case_and_every_case_is_verified() -> None:
    assert set(CASES) == set(VERIFIED)


def test_a_verified_route_is_one_the_inventory_found_eligible() -> None:
    eligible = {
        (item.method, item.path)
        for item in contracts(build_app())
        if item.status in {"verified", "eligible"}
    }
    assert set(VERIFIED) <= eligible


@pytest.mark.parametrize("operation", sorted(CASES), ids=lambda op: f"{op[0]} {op[1]}")
def test_the_real_response_is_exactly_the_attached_view(
    operation: tuple[str, str], workspace: Path, offline_default_model: None
) -> None:
    client = TestClient(create_app(workspace))
    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    url = CASES[operation](workspace, client, headers)
    response = client.request(operation[0], url, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    view = next(
        item.response for item in contracts(client.app) if (item.method, item.path) == operation  # type: ignore[arg-type]
    )
    if isinstance(body, list):
        assert body, f"{operation}: an empty list verifies nothing — seed it"
    _check(view, body, f"{operation[0]} {operation[1]}")


def test_the_matcher_refuses_a_key_the_view_does_not_declare() -> None:
    """A matcher that passes everything would make every claim above free."""
    from raiker.control.dtos import RuntimeModeView

    good = {field.name: None for field in dataclasses.fields(RuntimeModeView)}
    with pytest.raises(AssertionError, match="extra"):
        _check(RuntimeModeView, {**good, "surplus": 1}, "probe")
