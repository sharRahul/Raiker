# SPDX-License-Identifier: Apache-2.0
"""The API contract: which routes OpenAPI can describe, and the files derived from it.

OPT-01/OPT-02 Stage A (see the scope decision in
``docs/plans/CODEBASE_OPTIMIZATION_AND_LOC_REDUCTION_2026-09-05.md``). The routes
annotate ``-> dict[str, Any]``, so FastAPI's OpenAPI document names no response
fields. This module works out, per route, what the response actually is:

* **verified** — the handler returns ``serialize_dto(...)`` of a service call
  whose annotated return is a read-model view (or a list of one) that serialises
  as exactly its fields, *and* ``tests/test_api_contract_responses.py`` has
  called the route and matched the body to that schema key for key;
* **eligible** — the same, not yet exercised by that test, so not attached;
* **deferred** — the body is assembled in the route or projected by a custom
  ``to_dict``; it needs a dedicated response model first (Stage B);
* **special** — a stream, a file, or another non-JSON transport, which stays
  hand-written.

For verified routes only, the view is attached to the OpenAPI document as the
200 response — documentation, not ``response_model``: the route's runtime
serialisation is unchanged, so nothing is coerced or filtered. Three files are
derived, deterministically, and committed:

* ``web/src/lib/generated/openapi.json`` — the document;
* ``web/src/lib/generated/apiContract.ts`` — TypeScript for its schemas and a
  typed wrapper per verified operation, built on ``api/core.ts``;
* ``docs/architecture/API_CONTRACT_INVENTORY.md`` — the route inventory.

``--check`` regenerates them in memory and fails on any difference
(``tests/test_api_contract_generation.py`` runs it in CI).

    python -m scripts.api_contract           # write
    python -m scripts.api_contract --check   # verify
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import inspect
import json
import re
import sys
import tempfile
import textwrap
import typing
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.routing import APIRoute
from pydantic import TypeAdapter

from raiker.contracts.views import View

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATED = REPO_ROOT / "web" / "src" / "lib" / "generated"
OPENAPI_JSON = GENERATED / "openapi.json"
CONTRACT_TS = GENERATED / "apiContract.ts"
INVENTORY_MD = REPO_ROOT / "docs" / "architecture" / "API_CONTRACT_INVENTORY.md"

#: Routes whose response a contract test has matched to the view's schema, key
#: for key, on a seeded workspace. Attaching a schema is a claim about the wire;
#: this set is where the evidence for each claim is recorded.
VERIFIED: frozenset[tuple[str, str]] = frozenset(
    {
        ("GET", "/api/approvals"),
        ("GET", "/api/capability-gates"),
        ("GET", "/api/checkpoints"),
        ("GET", "/api/code/repos"),
        ("GET", "/api/connections"),
        ("GET", "/api/events"),
        ("GET", "/api/extensions"),
        ("GET", "/api/mcp/servers"),
        ("GET", "/api/mcp/servers/{server_id}/sessions"),
        ("GET", "/api/memory"),
        ("GET", "/api/projects"),
        ("GET", "/api/runtime-mode"),
        ("GET", "/api/runtime-readiness"),
        ("GET", "/api/sessions"),
        ("GET", "/api/tasks"),
        ("GET", "/api/work-threads"),
        ("GET", "/api/work-threads/page"),
    }
)

_SPECIAL_MARKERS = ("StreamingResponse", "FileResponse", "EventSourceResponse", "Response(")


# --- route analysis ---------------------------------------------------------


@dataclass(frozen=True)
class RouteContract:
    method: str
    path: str
    name: str
    request_model: str | None
    response: Any  # the annotated view type, for eligible routes
    status: str  # verified | eligible | deferred | special
    reason: str


def _wire_is_fields(view: Any, seen: set[Any] | None = None) -> bool:
    """True when ``view``'s JSON is exactly its declared fields, all the way down."""
    seen = set() if seen is None else seen
    if view in seen:
        return True
    seen.add(view)
    if not (isinstance(view, type) and dataclasses.is_dataclass(view) and issubclass(view, View)):
        return False
    if view.to_dict is not View.to_dict:
        return False
    hints = typing.get_type_hints(view)
    for field in dataclasses.fields(view):
        stack = [hints[field.name]]
        while stack:
            item = stack.pop()
            stack.extend(typing.get_args(item))
            if not isinstance(item, type):
                continue
            if dataclasses.is_dataclass(item):
                if not _wire_is_fields(item, seen):
                    return False
            elif hasattr(item, "to_dict"):
                return False
    return True


def _view_of(annotation: Any) -> Any | None:
    """The annotation itself when it is a fields-only view or a list/tuple of one."""
    origin = typing.get_origin(annotation)
    if origin in (list, tuple):
        args = [arg for arg in typing.get_args(annotation) if arg is not Ellipsis]
        if len(args) == 1 and _wire_is_fields(args[0]):
            return list[args[0]]  # type: ignore[valid-type]
        return None
    return annotation if _wire_is_fields(annotation) else None


def _returned_call(function: Callable[..., Any]) -> tuple[str, str, str] | None:
    """``(helper, method, receiver)`` of ``return serialize_dto(helper(request).method(...))``.

    Follows one local assignment of the argument and one of the receiver, so
    ``view = service.m(...); return serialize_dto(view)`` with
    ``service = _service(request)`` resolves as well.
    """
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    except (OSError, TypeError, SyntaxError):
        return None
    body = tree.body[0]
    assigned: dict[str, ast.expr] = {}
    for node in ast.walk(body):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                assigned[target.id] = node.value
    returns = [node for node in ast.walk(body) if isinstance(node, ast.Return)]
    if len(returns) != 1 or returns[0].value is None:
        return None
    value = returns[0].value
    if not (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id == "serialize_dto"
        and len(value.args) == 1
    ):
        return None
    argument = value.args[0]
    if isinstance(argument, ast.Name):
        argument = assigned.get(argument.id, argument)
    if not (isinstance(argument, ast.Call) and isinstance(argument.func, ast.Attribute)):
        return None
    receiver = argument.func.value
    if isinstance(receiver, ast.Name):
        receiver = assigned.get(receiver.id, receiver)
    if not (
        isinstance(receiver, ast.Call)
        and isinstance(receiver.func, ast.Name)
        and len(receiver.args) == 1
        and isinstance(receiver.args[0], ast.Name)
        and receiver.args[0].id == "request"
    ):
        return None
    return receiver.func.id, argument.func.attr, ast.unparse(receiver)


def _namespace() -> dict[str, Any]:
    """Names an annotation may use that its module imports only for type checking."""
    import importlib

    from scripts.check_api_contract import DTO_MODULES

    names: dict[str, Any] = {}
    for module_name in (*DTO_MODULES, "raiker.control.dashboard"):
        module = importlib.import_module(module_name)
        names.update({k: v for k, v in vars(module).items() if isinstance(v, type)})
    return names


def _hints(target: Any) -> dict[str, Any]:
    try:
        return typing.get_type_hints(target, localns=_namespace())
    except Exception:  # noqa: BLE001 - an unresolvable annotation is "deferred", not a crash
        return {}


def _response_annotation(route: APIRoute) -> tuple[Any | None, str]:
    endpoint = route.endpoint
    try:
        source = inspect.getsource(endpoint)
    except (OSError, TypeError):
        source = ""
    if any(marker in source for marker in _SPECIAL_MARKERS):
        return None, "special"
    found = _returned_call(endpoint)
    if found is None:
        return None, "body assembled in the route"
    helper_name, method, _ = found
    module = sys.modules[endpoint.__module__]
    helper = getattr(module, helper_name, None)
    if helper is None:
        return None, f"helper {helper_name} not found"
    service_type = _hints(helper).get("return")
    target = getattr(service_type, method, None)
    if target is None:
        return None, f"{getattr(service_type, '__name__', service_type)}.{method} not found"
    annotation = _hints(target).get("return")
    view = _view_of(annotation)
    if view is None:
        return None, f"{method} returns {getattr(annotation, '__name__', annotation)}, not a fields-only view"
    return view, f"{getattr(service_type, '__name__', '')}.{method}"


def _request_model(route: APIRoute) -> str | None:
    field = route.body_field
    if field is None:
        return None
    annotation = getattr(field, "type_", None) or getattr(getattr(field, "field_info", None), "annotation", None)
    return getattr(annotation, "__name__", None)


def _api_routes(routes: list[Any]) -> list[APIRoute]:
    """Every ``APIRoute``, through FastAPI's included-router wrappers.

    Raiker's routers carry no prefix (their paths start ``/api/``), so the
    wrapped router's own routes are the routes the app serves.
    """
    found: list[APIRoute] = []
    for route in routes:
        if isinstance(route, APIRoute):
            found.append(route)
        elif getattr(route, "original_router", None) is not None:
            found.extend(_api_routes(route.original_router.routes))
    return found


def _routes(app: FastAPI) -> list[APIRoute]:
    return sorted(
        (route for route in _api_routes(app.routes) if route.path.startswith("/api/")),
        key=lambda route: (route.path, sorted(route.methods or ())),
    )


def contracts(app: FastAPI) -> list[RouteContract]:
    found: list[RouteContract] = []
    for route in _routes(app):
        view, reason = _response_annotation(route)
        for method in sorted(route.methods or ()):
            if reason == "special":
                status = "special"
            elif view is None:
                status = "deferred"
            elif (method, route.path) in VERIFIED:
                status = "verified"
            else:
                status = "eligible"
            found.append(
                RouteContract(
                    method=method,
                    path=route.path,
                    name=route.name,
                    request_model=_request_model(route),
                    response=view,
                    status=status,
                    reason=reason,
                )
            )
    return found


def build_app() -> FastAPI:
    from raiker.api.app import create_app

    return create_app(tempfile.mkdtemp(prefix="raiker-contract-"))


# --- the OpenAPI document ---------------------------------------------------


def openapi_document(app: FastAPI) -> dict[str, Any]:
    """The app's OpenAPI with each verified route's view as its 200 response."""
    document = app.openapi()
    verified = [item for item in contracts(app) if item.status == "verified"]
    if verified:
        _keys, schemas = TypeAdapter.json_schemas(
            [(item, "serialization", TypeAdapter(item.response)) for item in verified],
            ref_template="#/components/schemas/{model}",
        )
        components = document.setdefault("components", {}).setdefault("schemas", {})
        for name, schema in schemas.get("$defs", {}).items():
            components.setdefault(name, schema)
        for item, mode in _keys:
            schema = _keys[(item, mode)]
            operation = document["paths"][item.path][item.method.lower()]
            operation.setdefault("responses", {})["200"] = {
                "description": "Successful Response",
                "content": {"application/json": {"schema": schema}},
            }
    return document


def render_openapi(document: dict[str, Any]) -> str:
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


# --- TypeScript ---------------------------------------------------------------

_HEADER = """\
// Generated by scripts/api_contract.py from the backend's OpenAPI document.
// Do not edit: run `python -m scripts.api_contract`. CI fails when this file
// differs from what the backend produces.
"""


def _ref_name(ref: str) -> str:
    return ref.rsplit("/", 1)[-1]


def _ts(schema: dict[str, Any]) -> str:
    if "$ref" in schema:
        return _ref_name(str(schema["$ref"]))
    if "const" in schema:
        return json.dumps(schema["const"])
    if "enum" in schema:
        return " | ".join(json.dumps(value) for value in schema["enum"])
    for key in ("anyOf", "oneOf"):
        if key in schema:
            members: list[str] = []
            for option in schema[key]:
                rendered = _ts(option)
                if rendered not in members:
                    members.append(rendered)
            return " | ".join(members)
    if "allOf" in schema and len(schema["allOf"]) == 1:
        return _ts(schema["allOf"][0])
    kind = schema.get("type")
    if kind == "string":
        return "string"
    if kind in {"integer", "number"}:
        return "number"
    if kind == "boolean":
        return "boolean"
    if kind == "null":
        return "null"
    if kind == "array":
        if "prefixItems" in schema:
            return "[" + ", ".join(_ts(item) for item in schema["prefixItems"]) + "]"
        inner = _ts(schema.get("items", {}))
        return f"({inner})[]" if " | " in inner else f"{inner}[]"
    if kind == "object":
        if "properties" in schema:
            return _object(schema, indent="  ", all_required=False)
        extra = schema.get("additionalProperties", True)
        return f"Record<string, {'unknown' if extra in (True, {}) else _ts(extra)}>"
    return "unknown"


def _object(schema: dict[str, Any], *, indent: str, all_required: bool) -> str:
    required = set(schema.get("required", ()))
    lines = ["{"]
    for name, prop in schema["properties"].items():
        mark = "" if all_required or name in required else "?"
        lines.append(f"{indent}  {name}{mark}: {_ts(prop)};")
    lines.append(f"{indent}}}")
    return "\n".join(lines)


def _comment(text: str, width: int = 96) -> str:
    text = text.replace("*/", "* /")
    if len(text) + 7 <= width:
        return f"/** {text} */"
    lines, line = ["/**"], " *"
    for word in text.split():
        if len(line) + 1 + len(word) > width:
            lines.append(line)
            line = " *"
        line += f" {word}"
    return "\n".join([*lines, line, " */"])


def _camel(name: str) -> str:
    head, *rest = re.split(r"[_\W]+", name)
    return head + "".join(part[:1].upper() + part[1:] for part in rest)


def render_typescript(document: dict[str, Any], app: FastAPI) -> str:
    schemas: dict[str, Any] = document.get("components", {}).get("schemas", {})
    # Views serialise every declared field; request models list their own
    # required fields. A schema reached from a verified response is a view.
    view_names: set[str] = set()
    for item in contracts(app):
        if item.status != "verified":
            continue
        response = document["paths"][item.path][item.method.lower()]["responses"]["200"]
        stack = [response["content"]["application/json"]["schema"]]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                if "$ref" in node:
                    name = _ref_name(node["$ref"])
                    if name not in view_names:
                        view_names.add(name)
                        stack.append(schemas.get(name, {}))
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
    chunks = [_HEADER, ""]
    for name in sorted(schemas):
        if name in {"HTTPValidationError", "ValidationError"}:
            continue
        schema = schemas[name]
        doc = schema.get("description")
        if doc:
            chunks.append(_comment(" ".join(str(doc).strip().split("\n\n")[0].split())))
        if schema.get("type") == "object" and "properties" in schema:
            body = _object(schema, indent="", all_required=name in view_names)
            chunks.append(f"export interface {name} {body}\n")
        else:
            expression = _ts(schema)
            if len(expression) > 80 and " | " in expression:
                expression = "".join(f"\n  | {member}" for member in expression.split(" | "))
            else:
                expression = f" {expression}"
            chunks.append(f"export type {name} ={expression};\n")
    chunks.append(
        "/** One typed wrapper per verified operation, on the shared transport core. */\n"
        "export const contract = {"
    )
    used: set[str] = set()
    for item in contracts(app):
        if item.status != "verified":
            continue
        operation = document["paths"][item.path][item.method.lower()]
        response = _ts(operation["responses"]["200"]["content"]["application/json"]["schema"])
        parameters = operation.get("parameters", [])
        path_params = [p for p in parameters if p.get("in") == "path"]
        query_params = [p for p in parameters if p.get("in") == "query"]
        args = [f"{_camel(p['name'])}: string" for p in path_params]
        path = item.path
        for p in path_params:
            path = path.replace("{" + p["name"] + "}", "${encodeURIComponent(" + _camel(p["name"]) + ")}")
        target = f"`{path}`" if path_params else json.dumps(path)
        if query_params:
            fields = "; ".join(
                f"{p['name']}?: {_ts(p.get('schema', {})).replace(' | null', '')}"
                for p in query_params
            )
            args.append(f"query: {{ {fields} }} = {{}}")
            target = f"withQuery({target}, query)"
            used.add("withQuery")
        key = _camel(item.name)
        if item.method == "GET":
            used.add("request")
            chunks.append(f"  {key}: ({', '.join(args)}) =>\n    request<{response}>({target}),")
        else:
            used.add("postJson")
            args.append("body: unknown = {}")
            chunks.append(f"  {key}: ({', '.join(args)}) =>\n    postJson<{response}>({target}, body),")
    chunks.append("} as const;\n")
    chunks[1] = "import { " + ", ".join(sorted(used)) + ' } from "../api/core";\n'
    return "\n".join(chunks).rstrip() + "\n"


# --- the inventory ------------------------------------------------------------


def render_inventory(app: FastAPI) -> str:
    rows = contracts(app)
    counts = {status: sum(1 for row in rows if row.status == status) for status in ("verified", "eligible", "deferred", "special")}
    lines = [
        "# API contract inventory",
        "",
        "Generated by `python -m scripts.api_contract`; do not edit. It is the migration",
        "boundary the OPT-01/OPT-02 scope decision in",
        "[the optimisation review](../plans/CODEBASE_OPTIMIZATION_AND_LOC_REDUCTION_2026-09-05.md#scope-decision--opt-01-and-opt-02-2026-10-01)",
        "asks for: what each `/api/` operation answers with, and whether OpenAPI describes it.",
        "",
        "* **verified** — the response is a fields-only read-model view, a contract test",
        "  matched a real response to its schema key for key, and the OpenAPI document",
        "  and `web/src/lib/generated/apiContract.ts` describe it.",
        "* **eligible** — the same view, not yet exercised by that test, so not described.",
        "* **deferred** — the body is assembled in the route or projected by a custom",
        "  `to_dict`; it needs a dedicated response model first (Stage B).",
        "* **special** — a stream, a file or another non-JSON transport; hand-written.",
        "",
        f"**{len(rows)} operations: {counts['verified']} verified, {counts['eligible']} eligible, "
        f"{counts['deferred']} deferred, {counts['special']} special.**",
        "",
        "| Method | Path | Request | Response | Status | Why |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        response = "" if row.response is None else _type_name(row.response)
        reason = row.reason.replace("|", "\\|")
        lines.append(
            f"| {row.method} | `{row.path}` | {row.request_model or ''} | {response} | {row.status} | {reason} |"
        )
    return "\n".join(lines) + "\n"


def _type_name(annotation: Any) -> str:
    if typing.get_origin(annotation) in (list, tuple):
        return f"{_type_name(typing.get_args(annotation)[0])}[]"
    return getattr(annotation, "__name__", str(annotation))


# --- entry point --------------------------------------------------------------


def outputs() -> dict[Path, str]:
    app = build_app()
    document = openapi_document(app)
    return {
        OPENAPI_JSON: render_openapi(document),
        CONTRACT_TS: render_typescript(document, app),
        INVENTORY_MD: render_inventory(app),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if a generated file is stale")
    args = parser.parse_args(argv)
    expected = outputs()
    if args.check:
        stale = [
            path.relative_to(REPO_ROOT).as_posix()
            for path, text in expected.items()
            if (path.read_text(encoding="utf-8") if path.exists() else "") != text
        ]
        for name in stale:
            print(f"{name} is stale; run `python -m scripts.api_contract`", file=sys.stderr)
        return 1 if stale else 0
    for path, text in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
        print(f"wrote {path.relative_to(REPO_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
