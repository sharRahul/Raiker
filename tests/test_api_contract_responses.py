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
import types
import typing
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter
from typing_extensions import is_typeddict

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.memory.store import MemoryGovernance, write_memory
from raiker.storage.sqlite import SQLiteStore
from scripts.api_contract import VERIFIED, build_app, contracts
from tests.factories import tool_action

#: Where to send the request: a path, or a path and the JSON body to send.
Call = str | tuple[str, Any]
Seed = Callable[[Path, TestClient, dict[str, str]], Call]


def _plain(path: str, body: Any = None) -> Seed:
    return lambda _ws, _client, _h: path if body is None else (path, body)


def _first(client: TestClient, h: dict[str, str], path: str, key: str) -> str:
    """The ``key`` of the first row a list route answers — an id to address."""
    rows = client.get(path, headers=h).json()
    assert rows, f"{path} answered nothing to address"
    return str(rows[0][key])


def _then(seed: Seed, build: Callable[[TestClient, dict[str, str]], Call]) -> Seed:
    """Run ``seed`` for its state, then address what it made."""

    def run(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
        seed(ws, client, h)
        return build(client, h)

    return run


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


def _finding(ws: Path, _client: TestClient, _h: dict[str, str]) -> str:
    store = SQLiteStore(ws)
    finding_id = store.insert_security_finding(
        principal_id="principal_owner", source="mcp_monitor", severity="medium", code="probe",
        summary="A probe finding", redacted_detail={"count": 1}, subject_id="mcp_contract",
    )
    store.insert_notification(
        principal_id="principal_owner", kind="security_finding", title="Probe",
        body="A probe finding", finding_id=finding_id, subject_id="mcp_contract",
    )
    return finding_id


def _credential(ws: Path, client: TestClient, h: dict[str, str]) -> str:
    from raiker.runtime.connector_ecosystem import ConnectorVault
    from raiker.security.credentials import CredentialLifecycle

    store = SQLiteStore(ws)
    ConnectorVault(store).put("principal_owner", "github", {"token": "ghp_contract"})
    CredentialLifecycle(store).record_verified("principal_owner", "github")
    return "github"


def _created_task(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    return "/api/tasks", {"title": "Contract", "description": "Check the contract"}


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
    ("GET", "/api/approvals/{approval_id}"): _then(_approval, lambda c, h: "/api/approvals/appr_c"),
    ("GET", "/api/capability-gates/{capability}"): lambda _ws, c, h: (
        "/api/capability-gates/" + _first(c, h, "/api/capability-gates", "capability")
    ),
    ("GET", "/api/chat-search"): _with_turn("/api/chat-search?q=hello"),
    ("GET", "/api/checkpoints/{checkpoint_id}"): _then(
        _with_turn(""), lambda c, h: "/api/checkpoints/" + _first(c, h, "/api/checkpoints", "checkpoint_id")
    ),
    ("GET", "/api/diagnostics"): _plain("/api/diagnostics"),
    ("GET", "/api/mcp/servers/{server_id}/findings"): _then(
        lambda ws, c, h: (_mcp("")(ws, c, h), _finding(ws, c, h)),
        lambda c, h: "/api/mcp/servers/mcp_contract/findings",
    ),
    ("GET", "/api/memory/settings"): _plain("/api/memory/settings"),
    ("GET", "/api/notifications"): _then(_finding, lambda c, h: "/api/notifications"),
    ("GET", "/api/projects/{project_id}"): _then(
        _project,
        lambda c, h: "/api/projects/" + c.get("/api/projects", headers=h).json()["projects"][0]["project_id"],
    ),
    ("POST", "/api/security/breach-check"): _then(
        _finding, lambda c, h: ("/api/security/breach-check", {"password": "x", "enabled": False})
    ),
    ("GET", "/api/security/credentials"): _then(_credential, lambda c, h: "/api/security/credentials"),
    ("POST", "/api/security/credentials/{provider}/verify"): _then(
        _credential, lambda c, h: "/api/security/credentials/github/verify"
    ),
    ("GET", "/api/security/findings"): _then(_finding, lambda c, h: "/api/security/findings"),
    ("POST", "/api/security/scan"): _then(_finding, lambda c, h: "/api/security/scan"),
    ("GET", "/api/sessions/{session_id}/context-usage"): _then(
        _with_turn(""),
        lambda c, h: f"/api/sessions/{_first(c, h, '/api/sessions', 'session_id')}/context-usage",
    ),
    ("POST", "/api/tasks"): _created_task,
    ("GET", "/api/tasks/{task_id}"): _then(
        _task, lambda c, h: "/api/tasks/" + _first(c, h, "/api/tasks", "task_id")
    ),
    ("POST", "/api/tasks/{task_id}/run"): _then(
        _task, lambda c, h: f"/api/tasks/{_first(c, h, '/api/tasks', 'task_id')}/run"
    ),
    ("GET", "/api/turns/{turn_id}"): _then(
        _with_turn(""),
        lambda c, h: "/api/turns/" + str(SQLiteStore(Path(c.app.state.workspace_root)).list_turns(
            _first(c, h, "/api/sessions", "session_id"))[0]["turn_id"]),
    ),
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
    if is_typeddict(annotation):
        assert isinstance(value, dict), f"{where}: expected an object"
        hints = typing.get_type_hints(annotation)
        required = set(annotation.__required_keys__)
        assert required <= set(value) <= set(hints), (
            f"{where}: keys differ — missing {sorted(required - set(value))}, "
            f"extra {sorted(set(value) - set(hints))}"
        )
        for name in value:
            _check(hints[name], value[name], f"{where}.{name}")
        return
    members = [arg for arg in typing.get_args(annotation) if arg is not type(None)]
    if typing.get_origin(annotation) in (typing.Union, types.UnionType) and value is not None:
        structured = [m for m in members if is_typeddict(m) or dataclasses.is_dataclass(m)]
        if len(members) == 1 and structured:
            _check(members[0], value, where)
            return
    if typing.get_origin(annotation) in (list, tuple) and isinstance(value, list):
        inner = [arg for arg in typing.get_args(annotation) if arg is not Ellipsis]
        if len(inner) == 1 and is_typeddict(inner[0]):
            for index, item in enumerate(value):
                _check(inner[0], item, f"{where}[{index}]")
            return
    if typing.get_origin(annotation) is dict and isinstance(value, dict):
        args = typing.get_args(annotation)
        if len(args) == 2 and (is_typeddict(args[1]) or dataclasses.is_dataclass(args[1])):
            for key, item in value.items():
                _check(args[1], item, f"{where}[{key!r}]")
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
    call = CASES[operation](workspace, client, headers)
    url, payload = call if isinstance(call, tuple) else (call, None)
    response = client.request(operation[0], url, headers=headers, json=payload)
    contract = next(
        item for item in contracts(client.app) if (item.method, item.path) == operation  # type: ignore[arg-type]
    )
    assert str(response.status_code) == contract.code, response.text
    body = response.json()
    view = contract.response
    if isinstance(body, list):
        assert body, f"{operation}: an empty list verifies nothing — seed it"
    _check(view, body, f"{operation[0]} {operation[1]}")


def test_the_matcher_refuses_a_key_the_view_does_not_declare() -> None:
    """A matcher that passes everything would make every claim above free."""
    from raiker.control.dtos import RuntimeModeView

    good = {field.name: None for field in dataclasses.fields(RuntimeModeView)}
    with pytest.raises(AssertionError, match="extra"):
        _check(RuntimeModeView, {**good, "surplus": 1}, "probe")
