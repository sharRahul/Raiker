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
from pathlib import Path
from typing import Any, NotRequired, Required

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter
from typing_extensions import is_typeddict

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from scripts.api_contract import VERIFIED, build_app, contracts
from tests.contract_cases import CASES
from tests.contract_cases.base import is_fresh, patch_of


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
        # Evaluated hints, not `__required_keys__`: under postponed annotations
        # the class cannot see `NotRequired[...]` inside a string.
        extras = typing.get_type_hints(annotation, include_extras=True)
        required = {
            name for name, hint in extras.items()
            if typing.get_origin(hint) is not NotRequired
            and (annotation.__total__ or typing.get_origin(hint) is Required)
        }
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
        if structured and len(structured) == len(members):
            # One of several declared shapes: it must be exactly one of them.
            failures = []
            for member in members:
                try:
                    _check(member, value, where)
                except (AssertionError, ValueError) as exc:
                    failures.append(str(exc))
                else:
                    return
            raise AssertionError(f"{where}: matches none of its shapes — " + " / ".join(failures))
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


@pytest.fixture(scope="module")
def described() -> dict[tuple[str, str], Any]:
    """The contract each operation claims, read before any case patches a helper.

    The resolver evaluates helper annotations from the route modules, so a case
    that swaps one for a stub would otherwise change the claim it is testing.
    """
    return {(item.method, item.path): item for item in contracts(build_app())}


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
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
    operation: tuple[str, str],
    workspace: Path,
    described: dict[tuple[str, str], Any],
    offline_default_model: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = CASES[operation]
    patch = patch_of(seed)
    if patch is not None:
        patch(monkeypatch)
    headers: dict[str, str] = {}
    if not is_fresh(seed):
        bootstrap_owner("owner", "Owner", workspace_root=workspace)
    client = TestClient(create_app(workspace))
    if not is_fresh(seed):
        token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
    call = seed(workspace, client, headers)
    url, payload, sent = (call, None, headers) if isinstance(call, str) else (*call, headers)[:3]
    response = client.request(operation[0], url, headers=sent, json=payload)
    contract = described[operation]
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
