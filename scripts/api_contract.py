# SPDX-License-Identifier: Apache-2.0
"""The API contract: which routes OpenAPI can describe, and the files derived from it.

OPT-01/OPT-02 (FIXED-664, FIXED-665, FIXED-678 and FIXED-679). The
routes annotate ``-> dict[str, Any]``, so FastAPI's OpenAPI document would name
no response field on its own. This module works out, per route, what the response actually is:

* **verified** — the handler's answer has a declared type: ``serialize_dto`` of
  an annotated local, a ``cast``, a typed helper or service return, or a
  fields-only read-model view (or a list of one) — a ``TypedDict`` or a ``View``
  — *and* ``tests/test_api_contract_responses.py`` has called the route and
  matched the body to that schema key for key;
* **eligible** — the same, not yet exercised by that test, so not attached;
* **deferred** — the body has no declared type yet;
* **special** — a stream, a file, or another non-JSON transport, which stays
  hand-written.

Every ordinary JSON operation is verified, and
``tests/test_api_contract_generation.py`` keeps it that way: a new route
declares its answer and gets a case in ``tests/contract_cases/``.

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
import types
import typing
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.routing import APIRoute
from pydantic import TypeAdapter
from starlette.responses import Response as StarletteResponse
from typing_extensions import is_typeddict

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
        ("DELETE", "/api/account"),
        ("DELETE", "/api/brain/sources"),
        ("DELETE", "/api/brain/sources/grants"),
        ("DELETE", "/api/channels/pairings/{pairing_id}"),
        ("DELETE", "/api/code/repos/{repo_id}"),
        ("DELETE", "/api/connector-store/{connector_id}"),
        ("DELETE", "/api/git-credential"),
        ("DELETE", "/api/git-credential/grant"),
        ("DELETE", "/api/images/{generation_id}"),
        ("DELETE", "/api/images/{generation_id}/purge"),
        ("DELETE", "/api/knowledge-sources"),
        ("DELETE", "/api/managed-files/{file_id}"),
        ("DELETE", "/api/mcp/servers/{server_id}"),
        ("DELETE", "/api/memory/{memory_id}"),
        ("DELETE", "/api/memory/{memory_id}/purge"),
        ("DELETE", "/api/model-library/roots"),
        ("DELETE", "/api/model-operations/{operation_id}"),
        ("DELETE", "/api/models/chatgpt-codex/connection"),
        ("DELETE", "/api/projects/{project_id}"),
        ("DELETE", "/api/projects/{project_id}/root"),
        ("DELETE", "/api/sessions/bulk"),
        ("DELETE", "/api/sessions/{session_id}"),
        ("DELETE", "/api/sessions/{session_id}/command-grant"),
        ("DELETE", "/api/skills/{skill_id}"),
        ("DELETE", "/api/telemetry/destinations/{destination_id}"),
        ("DELETE", "/api/vault/key"),
        ("DELETE", "/api/web-access/blocklist/{rule_id}"),
        ("GET", "/api/approvals"),
        ("GET", "/api/approvals/resumable"),
        ("GET", "/api/approvals/{approval_id}"),
        ("GET", "/api/audit/exports"),
        ("GET", "/api/auth/bootstrap-status"),
        ("GET", "/api/auth/session-state"),
        ("GET", "/api/auth/sessions"),
        ("GET", "/api/auth/whoami"),
        ("GET", "/api/brain"),
        ("GET", "/api/brain/settings"),
        ("GET", "/api/brain/sources/browse"),
        ("GET", "/api/brain/sources/roots"),
        ("GET", "/api/capability-gates"),
        ("GET", "/api/capability-gates/{capability}"),
        ("GET", "/api/capability-modes/{capability}"),
        ("GET", "/api/channels"),
        ("GET", "/api/chat-search"),
        ("GET", "/api/checkpoints"),
        ("GET", "/api/checkpoints/{checkpoint_id}"),
        ("GET", "/api/checkpoints/{checkpoint_id}/branch-plan"),
        ("GET", "/api/checkpoints/{checkpoint_id}/restore-plan"),
        ("GET", "/api/code/map"),
        ("GET", "/api/code/map/paths"),
        ("GET", "/api/build/boundary"),
        ("GET", "/api/code/repos"),
        ("GET", "/api/code/repos/{repo_id}/browse"),
        ("GET", "/api/code/repos/{repo_id}/changes"),
        ("GET", "/api/code/repos/{repo_id}/diagnostics"),
        ("GET", "/api/code/repos/{repo_id}/file"),
        ("GET", "/api/command-runs"),
        ("GET", "/api/command-runs/{run_id}"),
        ("GET", "/api/command-runs/{run_id}/output"),
        ("GET", "/api/command-runs/{run_id}/receipt"),
        ("GET", "/api/connections"),
        ("GET", "/api/connector-store"),
        ("GET", "/api/credential-deltas"),
        ("GET", "/api/diagnostics"),
        ("GET", "/api/diagnostics/export"),
        ("GET", "/api/environment"),
        ("GET", "/api/events"),
        ("GET", "/api/execution-environments"),
        ("GET", "/api/extensions"),
        ("GET", "/api/git-credential"),
        ("GET", "/api/guide"),
        ("GET", "/api/guide/{slug}"),
        ("GET", "/api/health"),
        ("GET", "/api/hooks"),
        ("GET", "/api/host"),
        ("GET", "/api/host/paths"),
        ("GET", "/api/host/update"),
        ("GET", "/api/hugging-face/search"),
        ("GET", "/api/hugging-face/trending"),
        ("GET", "/api/hugging-face/{owner}/{repository}/variants"),
        ("GET", "/api/images"),
        ("GET", "/api/knowledge-sources"),
        ("GET", "/api/local-runtimes"),
        ("GET", "/api/mcp/agent-access"),
        ("GET", "/api/mcp/offers"),
        ("GET", "/api/mcp/servers"),
        ("GET", "/api/mcp/servers/{server_id}/findings"),
        ("GET", "/api/mcp/servers/{server_id}/sessions"),
        ("GET", "/api/memory"),
        ("GET", "/api/memory/entity-proposals"),
        ("GET", "/api/memory/export"),
        ("GET", "/api/memory/files"),
        ("GET", "/api/memory/integrity"),
        ("GET", "/api/memory/observations"),
        ("GET", "/api/memory/proposals"),
        ("GET", "/api/memory/relationship-proposals"),
        ("GET", "/api/memory/settings"),
        ("GET", "/api/memory/{memory_id}/history"),
        ("GET", "/api/memory/{memory_id}/purge-preview"),
        ("GET", "/api/memory/{memory_id}/source"),
        ("GET", "/api/model-decision"),
        ("GET", "/api/model-decisions"),
        ("GET", "/api/model-library"),
        ("GET", "/api/model-operations"),
        ("GET", "/api/model-operations/{operation_id}/partial-files"),
        ("GET", "/api/model-readiness"),
        ("GET", "/api/model-setup"),
        ("GET", "/api/models"),
        ("GET", "/api/models/capacities"),
        ("GET", "/api/models/chatgpt-codex/status"),
        ("GET", "/api/models/pricing"),
        ("GET", "/api/models/weekly-usage"),
        ("GET", "/api/models/{profile_id}/provider-models"),
        ("GET", "/api/notifications"),
        ("GET", "/api/plugins"),
        ("GET", "/api/projects"),
        ("GET", "/api/projects/tree"),
        ("GET", "/api/projects/{project_id}"),
        ("GET", "/api/projects/{project_id}/browse"),
        ("GET", "/api/projects/{project_id}/deletion-preview"),
        ("GET", "/api/projects/{project_id}/files"),
        ("GET", "/api/projects/{project_id}/managed-files"),
        ("GET", "/api/projects/{project_id}/root/status"),
        ("GET", "/api/read-capabilities"),
        ("GET", "/api/runtime-mode"),
        ("GET", "/api/runtime-readiness"),
        ("GET", "/api/security/containment"),
        ("GET", "/api/security/credentials"),
        ("GET", "/api/security/findings"),
        ("GET", "/api/security/health"),
        ("GET", "/api/sessions"),
        ("GET", "/api/sessions/{session_id}"),
        ("GET", "/api/sessions/{session_id}/attachments"),
        ("GET", "/api/sessions/{session_id}/attachments/{attachment_id}/preview"),
        ("GET", "/api/sessions/{session_id}/attachments/{attachment_id}/provenance"),
        ("GET", "/api/sessions/{session_id}/branch-origin"),
        ("GET", "/api/sessions/{session_id}/context-usage"),
        ("GET", "/api/sessions/{session_id}/export/manifest"),
        ("GET", "/api/sessions/{session_id}/plan"),
        ("GET", "/api/sessions/{session_id}/recall"),
        ("GET", "/api/sessions/{session_id}/sources"),
        ("GET", "/api/sessions/{session_id}/turns/{turn_id}/sources/{source_id}/excerpt"),
        ("GET", "/api/settings"),
        ("GET", "/api/settings/composer-approval-mode"),
        ("GET", "/api/setup"),
        ("GET", "/api/skills"),
        ("GET", "/api/speech/runtime"),
        ("GET", "/api/standing-grants"),
        ("GET", "/api/surface-models"),
        ("GET", "/api/tasks"),
        ("GET", "/api/tasks/{task_id}"),
        ("GET", "/api/telemetry/destinations"),
        ("GET", "/api/turns/{turn_id}"),
        ("GET", "/api/vault/status"),
        ("GET", "/api/web-access/blocklist"),
        ("GET", "/api/work-in-flight"),
        ("GET", "/api/work-threads"),
        ("GET", "/api/work-threads/page"),
        ("POST", "/api/approvals/{approval_id}/answer"),
        ("POST", "/api/approvals/{approval_id}/replace"),
        ("POST", "/api/approvals/{approval_id}/resolve"),
        ("POST", "/api/approvals/{approval_id}/resolve-critical"),
        ("POST", "/api/approvals/{approval_id}/resume"),
        ("POST", "/api/attachments"),
        ("POST", "/api/audit/export"),
        ("POST", "/api/auth/elevate"),
        ("POST", "/api/auth/login"),
        ("POST", "/api/auth/logout"),
        ("POST", "/api/auth/mfa/activate"),
        ("POST", "/api/auth/mfa/disable"),
        ("POST", "/api/auth/mfa/enroll"),
        ("POST", "/api/auth/mfa/verify"),
        ("POST", "/api/auth/password"),
        ("POST", "/api/auth/password-recovery/begin"),
        ("POST", "/api/auth/password-recovery/complete"),
        ("POST", "/api/auth/register"),
        ("POST", "/api/auth/session"),
        ("POST", "/api/auth/sessions/{session_id}/revoke"),
        ("POST", "/api/brain/sources"),
        ("POST", "/api/brain/sources/grants"),
        ("POST", "/api/brain/sources/review"),
        ("POST", "/api/brain/sources/upload"),
        ("POST", "/api/capability-gates/{capability}/disable"),
        ("POST", "/api/capability-gates/{capability}/set"),
        ("POST", "/api/capability-gates/{capability}/threat-ack"),
        ("POST", "/api/capability-modes/{capability}/allow"),
        ("POST", "/api/capability-modes/{capability}/ask"),
        ("POST", "/api/capability-modes/{capability}/auto"),
        ("POST", "/api/capability-modes/{capability}/deny"),
        ("POST", "/api/channels/deliver-test"),
        ("POST", "/api/channels/pairings"),
        ("POST", "/api/channels/{connector_id}/approval-response"),
        ("POST", "/api/channels/{connector_id}/inbound"),
        ("POST", "/api/channels/{connector_id}/telegram"),
        ("POST", "/api/checkpoints/{checkpoint_id}/branch"),
        ("POST", "/api/checkpoints/{checkpoint_id}/restore"),
        ("POST", "/api/code/map/rebuild"),
        ("POST", "/api/code/repos"),
        ("POST", "/api/command-runs/{run_id}/stop"),
        ("POST", "/api/connector-store/{connector_id}/actions"),
        ("POST", "/api/connector-store/{connector_id}/install"),
        ("POST", "/api/connector-store/{connector_id}/manifest"),
        ("POST", "/api/credential-deltas/{run_id}/discard"),
        ("POST", "/api/execution-environments/{profile_id}/probe"),
        ("POST", "/api/execution-environments/{profile_id}/reset"),
        ("POST", "/api/git-credential/grant"),
        ("POST", "/api/host/pause"),
        ("POST", "/api/host/quit"),
        ("POST", "/api/host/restart"),
        ("POST", "/api/host/resume"),
        ("POST", "/api/host/update/apply"),
        ("POST", "/api/host/update/check"),
        ("POST", "/api/hugging-face/download"),
        ("POST", "/api/hugging-face/download/preview"),
        ("POST", "/api/images"),
        ("POST", "/api/images/{generation_id}/restore"),
        ("POST", "/api/images/{generation_id}/revert"),
        ("POST", "/api/instances"),
        ("POST", "/api/interrupts"),
        ("POST", "/api/language/check"),
        ("POST", "/api/local-runtimes/detect"),
        ("POST", "/api/managed-files/{file_id}/retry"),
        ("POST", "/api/mcp/servers"),
        ("POST", "/api/mcp/servers/remote"),
        ("POST", "/api/mcp/servers/{server_id}/connect"),
        ("POST", "/api/mcp/servers/{server_id}/kill"),
        ("POST", "/api/mcp/servers/{server_id}/pause"),
        ("POST", "/api/mcp/servers/{server_id}/resume"),
        ("POST", "/api/memory/conversation-index/rebuild"),
        ("POST", "/api/memory/eidetic/cleanup"),
        ("POST", "/api/memory/embedding-index"),
        ("POST", "/api/memory/entity-proposals/scan"),
        ("POST", "/api/memory/entity-proposals/{candidate_id}/decision"),
        ("POST", "/api/memory/entity-relationships/{relationship_id}/reject"),
        ("POST", "/api/memory/files"),
        ("POST", "/api/memory/gists/{gist_id}/discard"),
        ("POST", "/api/memory/import"),
        ("GET", "/api/memory/import/batches"),
        ("POST", "/api/memory/import/batches/{batch_id}/undo"),
        ("POST", "/api/memory/import/preview"),
        ("POST", "/api/memory/observations/delete"),
        ("POST", "/api/memory/proposals/{candidate_id}/decision"),
        ("POST", "/api/memory/reconcile"),
        ("POST", "/api/memory/relationship-proposals/scan"),
        ("POST", "/api/memory/relationship-proposals/{candidate_id}/decision"),
        ("POST", "/api/memory/{memory_id}/correct"),
        ("POST", "/api/model-conversion"),
        ("POST", "/api/model-conversion/preview"),
        ("POST", "/api/model-library/rescan"),
        ("POST", "/api/model-library/roots"),
        ("POST", "/api/model-library/{model_id:path}/deploy"),
        ("POST", "/api/model-library/{model_id:path}/deploy-mlx"),
        ("POST", "/api/model-operations"),
        ("POST", "/api/model-operations/preview"),
        ("POST", "/api/model-operations/{operation_id}/cancel"),
        ("POST", "/api/model-operations/{operation_id}/delete-partial-files"),
        ("POST", "/api/model-operations/{operation_id}/retry"),
        ("POST", "/api/model-readiness/check"),
        ("POST", "/api/models/capacities/refresh"),
        ("POST", "/api/models/catalogues/refresh"),
        ("POST", "/api/models/chatgpt-codex/connection"),
        ("POST", "/api/models/chatgpt-codex/login"),
        ("POST", "/api/models/pricing/refresh"),
        ("POST", "/api/notifications/{notification_id}/read"),
        ("POST", "/api/ollama/pull"),
        ("POST", "/api/projects"),
        ("POST", "/api/projects/{project_id}/managed-files"),
        ("POST", "/api/projects/{project_id}/root/attach"),
        ("POST", "/api/projects/{project_id}/root/index"),
        ("POST", "/api/prompts"),
        ("POST", "/api/runtime-mode/activate"),
        ("POST", "/api/runtime-mode/disable"),
        ("POST", "/api/security/breach-check"),
        ("POST", "/api/security/containment/{capability}/{subject_id}/{action}"),
        ("POST", "/api/security/credentials/{provider}/verify"),
        ("POST", "/api/security/health-check"),
        ("POST", "/api/security/scan"),
        ("POST", "/api/sessions/{session_id}/compact"),
        ("POST", "/api/setup/backup/create"),
        ("POST", "/api/skills"),
        ("POST", "/api/skills/build"),
        ("POST", "/api/skills/import"),
        ("POST", "/api/skills/verify"),
        ("POST", "/api/speech/runtime/probe"),
        ("POST", "/api/standing-grants"),
        ("POST", "/api/standing-grants/{grant_id}/revoke"),
        ("POST", "/api/stop-all"),
        ("POST", "/api/tasks"),
        ("POST", "/api/tasks/{task_id}/resume"),
        ("POST", "/api/tasks/{task_id}/run"),
        ("POST", "/api/telemetry/destinations"),
        ("POST", "/api/telemetry/destinations/{destination_id}/export"),
        ("POST", "/api/tray/session"),
        ("POST", "/api/web-access/blocklist"),
        ("POST", "/api/web-access/blocklist/test"),
        ("PUT", "/api/brain/settings"),
        ("PUT", "/api/channels/pairings/{pairing_id}/destination"),
        ("PUT", "/api/channels/pairings/{pairing_id}/enabled"),
        ("PUT", "/api/channels/pairings/{pairing_id}/routing"),
        ("PUT", "/api/channels/pairings/{pairing_id}/senders"),
        ("PUT", "/api/code/repos/selection"),
        ("PUT", "/api/connector-store/{connector_id}/credentials"),
        ("PUT", "/api/connector-store/{connector_id}/enabled"),
        ("PUT", "/api/execution-environments/configure"),
        ("PUT", "/api/execution-environments/selection"),
        ("PUT", "/api/git-credential"),
        ("PUT", "/api/hugging-face/credential"),
        ("PUT", "/api/mcp/servers/{server_id}"),
        ("PUT", "/api/memory/embedding-backend"),
        ("PUT", "/api/memory/incognito"),
        ("PUT", "/api/memory/{memory_id}"),
        ("PUT", "/api/memory/{memory_id}/archive"),
        ("PUT", "/api/memory/{memory_id}/expiry"),
        ("PUT", "/api/memory/{memory_id}/pin"),
        ("PUT", "/api/memory/{memory_id}/scope"),
        ("PUT", "/api/memory/{memory_id}/search"),
        ("PUT", "/api/model-advisor"),
        ("PUT", "/api/model-fallback"),
        ("PUT", "/api/model-selection"),
        ("PUT", "/api/model-setup"),
        ("PUT", "/api/models/{profile_id}/available-models"),
        ("PUT", "/api/models/{profile_id}/capacity"),
        ("PUT", "/api/models/{profile_id}/connection"),
        ("PUT", "/api/models/{profile_id}/price"),
        ("PUT", "/api/models/{profile_id}/weekly-budget"),
        ("PUT", "/api/projects/selection"),
        ("PUT", "/api/projects/{project_id}/archive"),
        ("PUT", "/api/projects/{project_id}/context"),
        ("PUT", "/api/projects/{project_id}/move"),
        ("PUT", "/api/projects/{project_id}/restore"),
        ("PUT", "/api/sessions/{session_id}/archive"),
        ("PUT", "/api/sessions/{session_id}/command-grant"),
        ("PUT", "/api/sessions/{session_id}/pin"),
        ("PUT", "/api/sessions/{session_id}/project"),
        ("PUT", "/api/sessions/{session_id}/rename"),
        ("PUT", "/api/sessions/{session_id}/tags"),
        ("PUT", "/api/sessions/{session_id}/unarchive"),
        ("PUT", "/api/settings"),
        ("PUT", "/api/settings/composer-approval-mode"),
        ("PUT", "/api/setup"),
        ("PUT", "/api/skills/{skill_id}"),
        ("PUT", "/api/skills/{skill_id}/active"),
        ("PUT", "/api/skills/{skill_id}/command"),
        ("PUT", "/api/speech/runtime"),
        ("PUT", "/api/surface-models"),
        ("PUT", "/api/telemetry/destinations/{destination_id}/cadence"),
        ("PUT", "/api/vault/key"),
    }
)

#: A stream, a file, or a raw (non-JSON) request body: none of them is an
#: ordinary JSON operation, so each stays hand-written.
_SPECIAL_MARKERS = (
    "StreamingResponse",
    "FileResponse",
    "EventSourceResponse",
    "Response(",
    "await request.body()",
)


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
    code: str = "200"  # the success status the route answers with


def _wire_is_fields(view: Any, seen: set[Any] | None = None) -> bool:
    """True when ``view``'s JSON is exactly what its declaration says, all the way down.

    A fields-only :class:`View` serialises its declared fields; a ``TypedDict``
    is the dict itself, its keys checked by ``mypy`` where it is built. Anything
    nested must be one of those, or a plain value.
    """
    seen = set() if seen is None else seen
    if view in seen:
        return True
    seen.add(view)
    if is_typeddict(view):
        hints = typing.get_type_hints(view)
    elif isinstance(view, type) and dataclasses.is_dataclass(view) and issubclass(view, View):
        if view.to_dict is not View.to_dict:
            return False
        hints = typing.get_type_hints(view)
    else:
        return False
    for annotation in hints.values():
        stack = [annotation]
        while stack:
            item = stack.pop()
            stack.extend(typing.get_args(item))
            if is_typeddict(item) or (isinstance(item, type) and dataclasses.is_dataclass(item)):
                if not _wire_is_fields(item, seen):
                    return False
            elif isinstance(item, type) and hasattr(item, "to_dict"):
                return False
    return True


def _view_of(annotation: Any) -> Any | None:
    """The annotation when it is a fields-only view, a list/tuple of one, or ``X | None``.

    ``X | None`` is a lookup the route turns into a 404 before it serialises, so
    the 200 answer is ``X``.
    """
    origin = typing.get_origin(annotation)
    if origin in (typing.Union, types.UnionType):
        members = [arg for arg in typing.get_args(annotation) if arg is not type(None)]
        if len(members) == 1:
            return _view_of(members[0])
        # One of several shapes — every member must be a wire view itself.
        views = [_view_of(member) for member in members]
        if any(view is None or typing.get_origin(view) is list for view in views):
            return None
        return typing.Union[tuple(views)]  # noqa: UP007 - built at runtime
    if origin in (list, tuple):
        args = [arg for arg in typing.get_args(annotation) if arg is not Ellipsis]
        inner = _view_of(args[0]) if len(args) == 1 else None
        if inner is None or typing.get_origin(inner) is list:
            return None
        return list[inner]  # type: ignore[valid-type]
    if _wire_is_fields(annotation):
        return annotation
    projected = _projection(annotation)
    return projected if projected is not None and _wire_is_fields(projected) else None


def _projection(annotation: Any) -> Any | None:
    """The TypedDict a class's own ``to_dict`` is declared to return, if it is one.

    A read model whose wire differs from its fields (it renames, nests or
    derives a key) keeps its ``to_dict``; declaring that method's return as a
    TypedDict makes the projection itself the contract, checked by mypy where
    the dict is built.
    """
    to_dict = getattr(annotation, "to_dict", None) if isinstance(annotation, type) else None
    if to_dict is None:
        return None
    returned = _hints(to_dict).get("return")
    return returned if is_typeddict(returned) else None


def _own_nodes(function: ast.AST) -> list[ast.AST]:
    """The handler's own nodes — not those of a function or lambda nested in it."""
    found: list[ast.AST] = []
    stack = list(ast.iter_child_nodes(function))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        found.append(node)
        stack.extend(ast.iter_child_nodes(node))
    return found


class _Resolver:
    """What one handler's ``serialize_dto(...)`` argument is, read from its source.

    Accepted, because each makes the wire the model's fields by construction:

    * ``View(...)`` — the route builds the view itself;
    * ``helper(...)`` — a module function annotated to return a view;
    * ``factory(request).method(...)`` or ``Service(...).method(...)`` — a
      service method annotated to return a view (Stage A's case);
    * ``[<any of these> for ...]`` — a list of one;
    * a local name assigned once from any of these.
    """

    def __init__(self, endpoint: Callable[..., Any], body: ast.AST) -> None:
        self.module = sys.modules[endpoint.__module__]
        self.assigned: dict[str, ast.expr] = {}
        self.annotated: dict[str, ast.expr] = {}
        for node in _own_nodes(body):
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name):
                    self.assigned[target.id] = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                self.annotated[node.target.id] = node.annotation

    def _deref(self, node: ast.expr) -> ast.expr:
        seen: set[str] = set()
        while isinstance(node, ast.Name) and node.id in self.assigned and node.id not in seen:
            seen.add(node.id)
            node = self.assigned[node.id]
        return node

    def _global(self, name: str) -> Any:
        return getattr(self.module, name, None)

    def _service_type(self, receiver: ast.expr) -> Any | None:
        receiver = self._deref(receiver)
        if not (isinstance(receiver, ast.Call) and isinstance(receiver.func, ast.Name)):
            return None
        target = self._global(receiver.func.id)
        if isinstance(target, type):
            return target
        if callable(target):
            return _hints(target).get("return")
        return None

    def _annotation(self, node: ast.expr) -> Any:
        """Evaluate a local's annotation in the handler's module."""
        return eval(compile(ast.Expression(node), "<annotation>", "eval"), vars(self.module))  # noqa: S307

    def resolve(self, node: ast.expr) -> tuple[Any | None, str]:
        if isinstance(node, ast.Name) and node.id in self.annotated:
            # `answer: View = ...` — the declared type, which mypy holds the
            # assigned value to.
            try:
                annotation = self._annotation(self.annotated[node.id])
            except Exception:  # noqa: BLE001 - an unresolvable annotation is "deferred"
                return None, f"annotation of {node.id} does not resolve"
            view = _view_of(annotation)
            if view is None:
                return None, f"{node.id} is declared {_type_name(annotation)}, not a fields-only view"
            return view, f"declared {_type_name(view)}"
        node = self._deref(node)
        if isinstance(node, ast.Await):
            node = self._deref(node.value)
        if isinstance(node, ast.ListComp):
            inner, how = self.resolve(node.elt)
            if inner is None or typing.get_origin(inner) is list:
                return None, how
            return list[inner], how  # type: ignore[valid-type]
        if not isinstance(node, ast.Call):
            return None, "body assembled in the route"
        func = node.func
        if isinstance(func, ast.Name) and func.id == "cast" and node.args:
            # `cast(View, value)` — the type the route declares its body to be.
            try:
                view = _view_of(self._annotation(node.args[0]))
            except Exception:  # noqa: BLE001 - an unresolvable annotation is "deferred"
                view = None
            return (view, "declared by cast") if view is not None else (None, "cast to a non-view")
        if isinstance(func, ast.Name):
            target = self._global(func.id)
            if isinstance(target, type) and not is_typeddict(target):
                view = _view_of(target)
                if view is None:
                    return None, f"{func.id} is not a fields-only view"
                return view, f"built as {func.id}"
            if callable(target):
                annotation = _hints(target).get("return")
                view = _view_of(annotation)
                if view is None:
                    return None, f"{func.id} returns {_type_name(annotation)}, not a fields-only view"
                return view, f"{func.id}"
            return None, f"{func.id} not found"
        if isinstance(func, ast.Attribute):
            service_type = self._service_type(func.value)
            if service_type is None:
                return None, "body assembled in the route"
            target = getattr(service_type, func.attr, None)
            if target is None:
                return None, f"{getattr(service_type, '__name__', service_type)}.{func.attr} not found"
            annotation = _hints(target).get("return")
            view = _view_of(annotation)
            if view is None:
                return None, f"{func.attr} returns {_type_name(annotation)}, not a fields-only view"
            return view, f"{getattr(service_type, '__name__', '')}.{func.attr}"
        return None, "body assembled in the route"


def _handler_view(endpoint: Callable[..., Any]) -> tuple[Any | None, str]:
    """The one view every ``return`` of the handler serialises, or why there is none."""
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(endpoint)))
    except (OSError, TypeError, SyntaxError):
        return None, "source unavailable"
    body = tree.body[0]
    resolver = _Resolver(endpoint, body)
    returns = [node for node in _own_nodes(body) if isinstance(node, ast.Return)]
    if not returns:
        return None, "body assembled in the route"
    found: list[tuple[Any, str]] = []
    for node in returns:
        value = node.value
        if not (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id == "serialize_dto"
            and len(value.args) == 1
        ):
            return None, "body assembled in the route"
        view, how = resolver.resolve(value.args[0])
        if view is None:
            return None, how
        found.append((view, how))
    views = list(dict.fromkeys(view for view, _ in found))
    if len(views) == 1:
        return found[0]
    if any(typing.get_origin(view) is list for view in views):
        return None, "returns a list in one branch and an object in another"
    # A route answering one of several declared shapes: the union is the contract.
    return typing.Union[tuple(views)], " | ".join(how for _, how in found)  # noqa: UP007


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
    returned = _hints(endpoint).get("return")
    if isinstance(returned, type) and issubclass(returned, StarletteResponse):
        return None, "special"
    return _handler_view(endpoint)


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
                    code=str(route.status_code or 200),
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
            operation = document["paths"][_openapi_path(item.path)][item.method.lower()]
            responses = operation.setdefault("responses", {})
            if item.code != "200":
                responses.pop("200", None)
            responses[item.code] = {
                "description": "Successful Response",
                "content": {"application/json": {"schema": schema}},
            }
    return document


def _openapi_path(path: str) -> str:
    """The path as OpenAPI spells it: Starlette's ``{name:path}`` converter dropped."""
    return re.sub(r"\{(\w+):\w+\}", r"{\1}", path)


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


def _dataclass_names(annotation: Any, seen: set[Any] | None = None) -> set[str]:
    """The names of every dataclass reachable from ``annotation``."""
    seen = set() if seen is None else seen
    names: set[str] = set()
    stack = [annotation]
    while stack:
        item = stack.pop()
        if item in seen:
            continue
        seen.add(item)
        stack.extend(typing.get_args(item))
        if isinstance(item, type) and dataclasses.is_dataclass(item):
            names.add(item.__name__)
            stack.extend(typing.get_type_hints(item).values())
        elif is_typeddict(item):
            stack.extend(typing.get_type_hints(item).values())
    return names


def render_typescript(document: dict[str, Any], app: FastAPI) -> str:
    schemas: dict[str, Any] = document.get("components", {}).get("schemas", {})
    # A dataclass view serialises every declared field, defaults included, so
    # each is required on the wire; a TypedDict and a request model say for
    # themselves which keys are required.
    view_names: set[str] = set()
    for item in contracts(app):
        if item.status == "verified":
            view_names |= _dataclass_names(item.response)
    chunks = [_HEADER, ""]
    for name in sorted(schemas):
        if name in {"HTTPValidationError", "ValidationError"}:
            continue
        schema = schemas[name]
        doc = schema.get("description")
        if doc:
            chunks.append(_comment(" ".join(str(doc).strip().split("\n\n")[0].split())))
        if schema.get("type") == "object" and "properties" in schema:
            # An object type rather than an interface: a type literal is
            # assignable to `Record<string, unknown>`, which a request model's
            # open field (`list[dict[str, Any]]`) is generated as.
            body = _object(schema, indent="", all_required=name in view_names)
            chunks.append(f"export type {name} = {body};\n")
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
    shared = Counter(
        (item.method, item.name) for item in contracts(app) if item.status == "verified"
    )
    for item in contracts(app):
        if item.status != "verified":
            continue
        operation = document["paths"][_openapi_path(item.path)][item.method.lower()]
        response = _ts(operation["responses"][item.code]["content"]["application/json"]["schema"])
        parameters = operation.get("parameters", [])
        path_params = [p for p in parameters if p.get("in") == "path"]
        query_params = [p for p in parameters if p.get("in") == "query"]
        args = [f"{_camel(p['name'])}: string" for p in path_params]
        path = _openapi_path(item.path)
        for p in path_params:
            path = path.replace("{" + p["name"] + "}", "${encodeURIComponent(" + _camel(p["name"]) + ")}")
        target = f"`{path}`" if path_params else json.dumps(path)
        if query_params:
            fields = "; ".join(
                f"{p['name']}{'' if p.get('required') else '?'}: "
                f"{_ts(p.get('schema', {})).replace(' | null', '')}"
                for p in query_params
            )
            required = any(p.get("required") for p in query_params)
            args.append(f"query: {{ {fields} }}" + ("" if required else " = {}"))
            target = f"withQuery({target}, query)"
            used.add("withQuery")
        key = _camel(item.name)
        if shared[(item.method, item.name)] > 1:
            # One handler serving two paths (an alias): each wrapper is named by
            # its own path, so neither shadows the other.
            key = _camel(item.method.lower() + "_" + re.sub(r"[{}]", "", item.path.removeprefix("/api/")))
        request_body = operation.get("requestBody", {})
        body = request_body.get("content", {}).get("application/json", {})
        if body:
            optional = "" if request_body.get("required") else "?"
            args.append(f"body{optional}: {_ts(body.get('schema', {}))}")
        header_params = [p for p in parameters if p.get("in") == "header"]
        headers = ", ".join(f'"{p["name"]}": {_camel(p["name"])}' for p in header_params)
        args += [f"{_camel(p['name'])}{'' if p.get('required') else '?'}: string" for p in header_params]
        options = ", ".join(
            part for part in (
                "body" if body else "",
                f"headers: {{ {headers} }}" if header_params else "",
            ) if part
        )
        if item.method == "GET" and not options:
            used.add("request")
            call = f"request<{response}>({target})"
        else:
            used.add("call")
            suffix = f", {{ {options} }}" if options else ""
            call = f'call<{response}>("{item.method}", {target}{suffix})'
        chunks.append(f"  {key}: ({', '.join(args)}) =>\n    {call},")
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
        "Generated by `python -m scripts.api_contract`; do not edit. What each `/api/`",
        "operation answers with, and whether OpenAPI describes it (OPT-01/OPT-02 —",
        "[FIXED-678](../plans/FIXED_ITEMS.md#fixed-678--most-routes-answers-were-described-nowhere-but-the-clients-copy),",
        "[FIXED-679](../plans/FIXED_ITEMS.md#fixed-679--the-client-still-hand-wrote-the-wrappers-for-routes-openapi-now-describes)).",
        "",
        "* **verified** — the response has a declared type, a contract test matched a",
        "  real response to its schema key for key, and the OpenAPI document",
        "  and `web/src/lib/generated/apiContract.ts` describe it.",
        "* **eligible** — the same view, not yet exercised by that test, so not described.",
        "* **deferred** — the body has no declared type; a test fails while any is.",
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
    if typing.get_origin(annotation) in (typing.Union, types.UnionType):
        return " \\| ".join(_type_name(arg) for arg in typing.get_args(annotation))
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
