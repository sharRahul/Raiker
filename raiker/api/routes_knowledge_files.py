"""Owner-scoped managed knowledge file API.

Two libraries, one contract. ``/api/memory/files`` manages the account's own
document library under ``.raiker/memory-files/``; ``/api/projects/{id}/managed-files``
manages one project's library under ``.raiker/projects/<slug>/``. Both accept
every file type — acceptance is not a claim that Raiker can read the file, only
that it will keep it — and both return per-file results so one bad file in a
folder import never discards its successfully stored siblings.

Every route authenticates before it resolves a project or file identifier, and
an id belonging to another account is reported exactly like an id belonging to
nothing. Uploaded bytes are untrusted data: they are stored, optionally
extracted by a local reader, and never executed.
"""

from __future__ import annotations

import base64
import binascii
import contextlib
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from raiker.api.auth import AuthMiddleware
from raiker.api.sessions import ApiSession
from raiker.knowledge.files import (
    ManagedFileError,
    ManagedFileRecord,
    ManagedFileScope,
    ManagedFileService,
)
from raiker.knowledge.indexing import ManagedFileIndexer
from raiker.runtime.authority.models import Principal
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()

#: Hard per-file cap for a managed import. Matches the attachment store's
#: document cap so one size limit governs everything the owner uploads.
MAX_MANAGED_FILE_BYTES = 32_000_000

#: Base64 inflates by 4/3, so anything longer than this cannot decode to an
#: in-cap file. Checked before decoding rather than after.
_MAX_BASE64_CHARS = (MAX_MANAGED_FILE_BYTES * 4) // 3 + 8

#: Largest number of files one import request may carry. A folder with more than
#: this is imported in batches by the client rather than in one unbounded body.
MAX_IMPORT_BATCH = 200


def _ws(request: Request) -> str | Path:
    return request.app.state.workspace_root  # type: ignore[no-any-return]


def _auth(request: Request) -> tuple[ApiSession, Principal]:
    return AuthMiddleware(_ws(request)).authenticate(request)


def _not_found(reason_code: str) -> HTTPException:
    """404 for everything the caller may not see, so an id cannot be probed."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"ok": False, "reason_code": reason_code},
    )


def _serialize(record: ManagedFileRecord) -> dict[str, Any]:
    return {
        "file_id": record.file_id,
        "scope_kind": record.scope_kind,
        "project_id": record.project_id,
        "relative_path": record.relative_path,
        "media_type": record.media_type,
        "size_bytes": record.size_bytes,
        "content_hash": record.content_hash,
        "index_state": record.index_state,
        "index_error": record.index_error,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def _owned_project_scope(
    request: Request, project_id: str, principal: Principal
) -> ManagedFileScope:
    store = SQLiteStore(_ws(request))
    if store.load_project(project_id, user_id=principal.delegated_by_user_id) is None:
        raise _not_found("project_not_found")
    return ManagedFileScope("project", project_id)


def _list(request: Request, scope: ManagedFileScope, principal_id: str) -> dict[str, Any]:
    store = SQLiteStore(_ws(request))
    rows = store.list_managed_files(
        principal_id, scope_kind=scope.kind, project_id=scope.project_id
    )
    return {
        "ok": True,
        "scope_kind": scope.kind,
        "project_id": scope.project_id,
        "files": [_serialize(ManagedFileRecord.from_row(row)) for row in rows],
    }


def _decode(entry: dict[str, Any]) -> bytes:
    encoded = str(entry.get("data_base64", ""))
    if len(encoded) > _MAX_BASE64_CHARS:
        raise ManagedFileError("managed_file_too_large")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ManagedFileError("invalid_base64") from exc
    if len(data) > MAX_MANAGED_FILE_BYTES:
        raise ManagedFileError("managed_file_too_large")
    return data


def _import(
    request: Request, scope: ManagedFileScope, principal_id: str, body: dict[str, Any]
) -> dict[str, Any]:
    """Store each file in the request independently, then index what can be read.

    One file's failure is that file's result, never the batch's: a folder import
    that trips over a single unreadable member must still keep every sibling it
    already wrote.
    """
    raw = body.get("files")
    if not isinstance(raw, list) or not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"ok": False, "reason_code": "no_files"},
        )
    if len(raw) > MAX_IMPORT_BATCH:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"ok": False, "reason_code": "too_many_files"},
        )
    store = SQLiteStore(_ws(request))
    service = ManagedFileService(_ws(request), store)
    indexer = ManagedFileIndexer(_ws(request), store)
    results: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            results.append({"ok": False, "relative_path": "", "reason_code": "invalid_entry"})
            continue
        relative_path = str(entry.get("relative_path", "") or entry.get("filename", ""))
        media_type = str(entry.get("media_type", "") or "application/octet-stream")
        try:
            data = _decode(entry)
            record = service.import_file(scope, relative_path, data, media_type, principal_id)
        except ManagedFileError as exc:
            results.append(
                {"ok": False, "relative_path": relative_path, "reason_code": str(exc)}
            )
            continue
        # The bytes are stored and the catalogue row exists, so a failed
        # projection leaves only the index missing -- and `retry` is exactly the
        # affordance for that. Losing the import over it would be worse.
        with contextlib.suppress(ManagedFileError):
            record = indexer.index(record.file_id, principal_id)
        results.append({"ok": True, **_serialize(record)})
    return {
        "ok": all(result["ok"] for result in results),
        "scope_kind": scope.kind,
        "project_id": scope.project_id,
        "results": results,
    }


@router.get("/api/memory/files")
async def list_memory_files(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    return _list(request, ManagedFileScope("memory"), auth_data[0].principal_id)


@router.post("/api/memory/files")
async def import_memory_files(
    request: Request,
    body: dict[str, Any],
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    return _import(request, ManagedFileScope("memory"), auth_data[0].principal_id, body)


@router.get("/api/projects/{project_id}/managed-files")
async def list_project_files(
    project_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    scope = _owned_project_scope(request, project_id, auth_data[1])
    return _list(request, scope, auth_data[0].principal_id)


@router.post("/api/projects/{project_id}/managed-files")
async def import_project_files(
    project_id: str,
    request: Request,
    body: dict[str, Any],
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    scope = _owned_project_scope(request, project_id, auth_data[1])
    return _import(request, scope, auth_data[0].principal_id, body)


@router.delete("/api/managed-files/{file_id}")
async def delete_managed_file(
    file_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    store = SQLiteStore(_ws(request))
    indexer = ManagedFileIndexer(_ws(request), store)
    try:
        record = indexer.retire(file_id, auth_data[0].principal_id)
    except ManagedFileError as exc:
        raise _not_found(str(exc)) from exc
    return {"ok": True, **_serialize(record)}


@router.post("/api/managed-files/{file_id}/retry")
async def retry_managed_file(
    file_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    store = SQLiteStore(_ws(request))
    indexer = ManagedFileIndexer(_ws(request), store)
    try:
        record = indexer.index(file_id, auth_data[0].principal_id)
    except ManagedFileError as exc:
        raise _not_found(str(exc)) from exc
    return {"ok": True, **_serialize(record)}
