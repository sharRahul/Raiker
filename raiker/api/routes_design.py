"""Raiker Design's structured documents: documents, versions, systems, proposals, exports, handoffs.

The Asset layer's routes are :mod:`raiker.api.routes_images`. These are the
Composition and Agent layers (DW-01 to DW-12), and they keep three rules:

* **Owner-scoped, always.** Every id is resolved against the signed-in owner;
  another owner's id answers exactly as one that was never issued.
* **A change names the version it was made against.** A change that touched
  nothing changed since is applied on top (``rebased``); one that meets a later
  change is refused, so later work is never overwritten (DW-08).
* **Nothing here grants anything.** An agent proposal is stored, not applied;
  an export writes a file to this workspace; a Build handoff is a context
  document Build's composer carries. The one network call — a proposal — goes
  through the owner's own model router, gates and egress allowlist.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import contextlib
import hashlib
import io
import json
import re
from typing import Any, cast

from fastapi import APIRouter, HTTPException, Request, Response, status
from PIL import Image

from raiker.api.dependencies import authenticate as _auth
from raiker.api.dependencies import refusal
from raiker.api.dependencies import workspace_root as _ws
from raiker.api.schemas import (
    CreateDesignDocumentRequest,
    DesignBaseVersionRequest,
    DesignExportRequest,
    DesignHandoffRequest,
    DesignImportAssetRequest,
    DesignOperationsRequest,
    DesignProposalDecisionRequest,
    DesignProposalRequest,
    DesignSystemChoiceRequest,
    DesignSystemRequest,
    DesignTokenImportRequest,
    UpdateDesignDocumentRequest,
    serialize_dto,
)
from raiker.api.wire.design import (
    DesignAssetUsage,
    DesignChangeView,
    DesignDocumentList,
    DesignDocumentSummary,
    DesignDocumentView,
    DesignExportList,
    DesignExportView,
    DesignHandoffList,
    DesignHandoffRecord,
    DesignHandoffView,
    DesignImportedAsset,
    DesignPalette,
    DesignProposalConflict,
    DesignProposalDecision,
    DesignProposalList,
    DesignProposalView,
    DesignSystemList,
    DesignSystemPreview,
    DesignSystemView,
    DesignTokenImport,
    DesignValidationView,
    DesignVersionList,
    DesignVersionSummary,
    DesignVersionView,
)
from raiker.design import store as design_store
from raiker.design.document import (
    FRAME_PRESETS,
    DesignError,
    all_nodes,
    apply_operations,
    blank_document,
    content_hash,
    find_frame,
)
from raiker.design.pdf import render_pdf
from raiker.design.render import encode_raster, raster_font_name, render_raster, render_svg
from raiker.design.systems import clean_variables, plan_system_change
from raiker.design.validation import validate
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()

#: The largest file one export may write.
MAX_EXPORT_BYTES = 20_000_000
EXPORT_FORMATS = {
    "svg": "image/svg+xml",
    "png": "image/png",
    "pdf": "application/pdf",
    "vector_pdf": "application/pdf",
    "json": "application/json",
}
#: The file extension a download is named with, where it is not the format's name.
EXPORT_EXTENSIONS = {"vector_pdf": "pdf"}


def _principal(request: Request) -> tuple[str, Any]:
    _, principal = _auth(request)
    return str(principal.principal_id), principal


def _store(request: Request) -> SQLiteStore:
    return SQLiteStore(_ws(request))


def _bad(exc: DesignError) -> Exception:
    return refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{exc.reason}:{exc.detail}" if exc.detail else exc.reason)


def _audit(store: SQLiteStore, request: Request, owner: str, event_type: str, payload: dict[str, Any]) -> None:
    """Ids, counts and hashes only — never a brief, a layer's text or exported bytes."""
    from raiker.events.types import make_event  # noqa: PLC0415
    from raiker.events.writer import EventLogWriter  # noqa: PLC0415

    session_id = f"sess_inbox_{owner}"
    with contextlib.suppress(Exception):
        store.create_session(session_id, str(_ws(request)), title="Inbox")
        EventLogWriter(store).append(
            make_event(session_id=session_id, turn_id=None, event_type=event_type, actor="design",
                       payload={"principal_id": owner, **payload})
        )


# ── Documents ────────────────────────────────────────────────────────────


def _summary(row: dict[str, Any]) -> DesignDocumentSummary:
    return cast(DesignDocumentSummary, {key: row[key] for key in DesignDocumentSummary.__annotations__})


def _document(store: SQLiteStore, owner: str, document_id: str) -> dict[str, Any]:
    row = design_store.get_document(store, owner=owner, document_id=document_id)
    if row is None:
        raise refusal(status.HTTP_404_NOT_FOUND, "unknown_design_document")
    return row


def _view(store: SQLiteStore, owner: str, row: dict[str, Any]) -> DesignDocumentView:
    current = design_store.get_version(
        store, owner=owner, document_id=row["document_id"], version=int(row["current_version"])
    )
    view = cast(DesignDocumentView, {**_summary(row), "document": row["document"]})
    view["can_undo"] = bool(current and current["undo_parent"] is not None)
    view["can_redo"] = bool(current and current["redo_target"] is not None)
    return view


def _check_project(store: SQLiteStore, principal: Any, project_id: str | None) -> str | None:
    if not project_id:
        return None
    if store.load_project(project_id, user_id=principal.delegated_by_user_id) is None:
        raise refusal(status.HTTP_404_NOT_FOUND, "unknown_project")
    return project_id


@router.get("/api/design/documents")
async def list_design_documents(request: Request) -> dict[str, Any]:
    owner, _ = _principal(request)
    store = _store(request)
    answer: DesignDocumentList = {
        "documents": [_summary(row) for row in design_store.list_documents(store, owner=owner)],
        "deleted": [_summary(row) for row in design_store.list_documents(store, owner=owner, deleted=True, limit=40)],
        "presets": [
            {"preset": key, "label": str(spec["label"]), "width": int(spec["width"]), "height": int(spec["height"])}
            for key, spec in FRAME_PRESETS.items()
        ],
    }
    return serialize_dto(answer)


@router.post("/api/design/documents")
async def create_design_document(body: CreateDesignDocumentRequest, request: Request) -> dict[str, Any]:
    """DW-01 — a new document with one empty frame. Filing it is explicit and optional."""
    owner, principal = _principal(request)
    store = _store(request)
    project_id = _check_project(store, principal, (body.project_id or "").strip())
    try:
        document = blank_document(body.preset.strip() or "social_square")
    except DesignError as exc:
        raise _bad(exc) from None
    row = design_store.create_document(
        store, owner=owner, title=body.title.strip() or "Untitled design", project_id=project_id, document=document
    )
    answer = _view(store, owner, row)
    return serialize_dto(answer)


@router.get("/api/design/documents/{document_id}")
async def read_design_document(document_id: str, request: Request) -> dict[str, Any]:
    owner, _ = _principal(request)
    store = _store(request)
    answer = _view(store, owner, _document(store, owner, document_id))
    return serialize_dto(answer)


@router.patch("/api/design/documents/{document_id}")
async def update_design_document(
    document_id: str, body: UpdateDesignDocumentRequest, request: Request
) -> dict[str, Any]:
    """Rename, file or unfile. Filing moves this document only — no asset or conversation moves with it."""
    owner, principal = _principal(request)
    store = _store(request)
    _document(store, owner, document_id)
    fields: dict[str, Any] = {}
    if body.title is not None:
        fields["title"] = body.title.strip() or "Untitled design"
    if body.project_id is not None:
        fields["project_id"] = _check_project(store, principal, body.project_id.strip())
    if not fields:
        raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, "nothing_to_update")
    design_store.update_document_meta(store, owner=owner, document_id=document_id, **fields)
    answer = _view(store, owner, _document(store, owner, document_id))
    return serialize_dto(answer)


@router.delete("/api/design/documents/{document_id}")
async def delete_design_document(document_id: str, request: Request) -> dict[str, Any]:
    """Put a document in Recently deleted. Its versions, exports and handoffs stay."""
    owner, _ = _principal(request)
    store = _store(request)
    if not design_store.set_document_deleted(store, owner=owner, document_id=document_id, deleted=True):
        raise refusal(status.HTTP_404_NOT_FOUND, "unknown_design_document")
    row = design_store.get_document(store, owner=owner, document_id=document_id, include_deleted=True)
    assert row is not None
    answer = _summary(row)
    return serialize_dto(answer)


@router.post("/api/design/documents/{document_id}/restore")
async def restore_design_document(document_id: str, request: Request) -> dict[str, Any]:
    owner, _ = _principal(request)
    store = _store(request)
    if not design_store.set_document_deleted(store, owner=owner, document_id=document_id, deleted=False):
        raise refusal(status.HTTP_404_NOT_FOUND, "unknown_deleted_design_document")
    answer = _view(store, owner, _document(store, owner, document_id))
    return serialize_dto(answer)


def _commit(
    store: SQLiteStore, owner: str, row: dict[str, Any], document: dict[str, Any], *, actor: str, kind: str,
    summary: str, scope: set[str], operations: list[Any], undo_parent: int | None,
    redo_target: int | None = None, proposal_id: str | None = None,
) -> int:
    try:
        return design_store.commit_version(
            store, owner=owner, document_id=row["document_id"], base_version=int(row["current_version"]),
            document=document, actor=actor, kind=kind, summary=summary, scope=scope, operations=operations,
            undo_parent=undo_parent, redo_target=redo_target, proposal_id=proposal_id,
        )
    except design_store.VersionConflict:
        raise refusal(status.HTTP_409_CONFLICT, "design_version_conflict") from None


@router.post("/api/design/documents/{document_id}/operations")
async def apply_design_operations(
    document_id: str, body: DesignOperationsRequest, request: Request
) -> dict[str, Any]:
    """DW-02 / DW-08 — the owner's direct edits, as typed operations against ``base_version``."""
    owner, _ = _principal(request)
    store = _store(request)
    row = _document(store, owner, document_id)
    current = int(row["current_version"])
    if body.base_version > current:
        raise refusal(status.HTTP_409_CONFLICT, "design_version_unknown")
    try:
        updated, touched, lines = apply_operations(row["document"], body.operations, actor="owner")
    except DesignError as exc:
        raise _bad(exc) from None
    rebased = body.base_version < current
    if rebased:
        later = design_store.scope_since(store, owner=owner, document_id=document_id, version=body.base_version)
        overlap = sorted(touched & set(later))
        if overlap:
            raise refusal(status.HTTP_409_CONFLICT, "design_version_conflict:" + ",".join(overlap[:12]))
    version = _commit(
        store, owner, row, updated, actor="owner", kind="edit", summary="; ".join(lines)[:300],
        scope=touched, operations=list(body.operations), undo_parent=current,
    )
    answer: DesignChangeView = {
        "ok": True, "version": version, "rebased": rebased, "summary": lines,
        "document": _view(store, owner, _document(store, owner, document_id)),
    }
    return serialize_dto(answer)


@router.get("/api/design/documents/{document_id}/versions")
async def list_design_versions(document_id: str, request: Request) -> dict[str, Any]:
    owner, _ = _principal(request)
    store = _store(request)
    row = _document(store, owner, document_id)
    answer: DesignVersionList = {
        "current_version": int(row["current_version"]),
        "versions": cast(
            list[DesignVersionSummary], design_store.list_versions(store, owner=owner, document_id=document_id)
        ),
    }
    return serialize_dto(answer)


@router.get("/api/design/documents/{document_id}/versions/{version}")
async def read_design_version(document_id: str, version: int, request: Request) -> dict[str, Any]:
    """One earlier version with its layers, to compare beside the current one."""
    owner, _ = _principal(request)
    store = _store(request)
    _document(store, owner, document_id)
    found = design_store.get_version(store, owner=owner, document_id=document_id, version=version)
    if found is None:
        raise refusal(status.HTTP_404_NOT_FOUND, "unknown_design_version")
    answer = cast(DesignVersionView, found)
    return serialize_dto(answer)


def _require_current(row: dict[str, Any], base_version: int) -> None:
    """Undo, redo and restore act on what the owner is looking at, or not at all."""
    if base_version != int(row["current_version"]):
        raise refusal(status.HTTP_409_CONFLICT, "design_version_conflict")


def _snapshot_change(
    store: SQLiteStore, owner: str, row: dict[str, Any], target: dict[str, Any], *, kind: str, summary: str,
    undo_parent: int | None, redo_target: int | None,
) -> DesignChangeView:
    scope = design_store.diff_scope(row["document"], target["document"])
    version = _commit(
        store, owner, row, target["document"], actor="owner", kind=kind, summary=summary, scope=scope,
        operations=[], undo_parent=undo_parent, redo_target=redo_target,
    )
    answer: DesignChangeView = {
        "ok": True, "version": version, "rebased": False, "summary": [summary],
        "document": _view(store, owner, _document(store, owner, row["document_id"])),
    }
    return answer


@router.post("/api/design/documents/{document_id}/undo")
async def undo_design_change(document_id: str, body: DesignBaseVersionRequest, request: Request) -> dict[str, Any]:
    """DW-08 — structured undo: the state before the last change, written as a new version.

    Nothing in the history is removed, so an undo can itself be redone.
    """
    owner, _ = _principal(request)
    store = _store(request)
    row = _document(store, owner, document_id)
    _require_current(row, body.base_version)
    current = design_store.get_version(store, owner=owner, document_id=document_id, version=int(row["current_version"]))
    if current is None or current["undo_parent"] is None:
        raise refusal(status.HTTP_409_CONFLICT, "nothing_to_undo")
    target = design_store.get_version(store, owner=owner, document_id=document_id, version=int(current["undo_parent"]))
    assert target is not None
    answer = _snapshot_change(
        store, owner, row, target, kind="undo", summary=f"Undid: {current['summary']}"[:300],
        undo_parent=target["undo_parent"], redo_target=int(row["current_version"]),
    )
    return serialize_dto(answer)


@router.post("/api/design/documents/{document_id}/redo")
async def redo_design_change(document_id: str, body: DesignBaseVersionRequest, request: Request) -> dict[str, Any]:
    owner, _ = _principal(request)
    store = _store(request)
    row = _document(store, owner, document_id)
    _require_current(row, body.base_version)
    current = design_store.get_version(store, owner=owner, document_id=document_id, version=int(row["current_version"]))
    if current is None or current["redo_target"] is None:
        raise refusal(status.HTTP_409_CONFLICT, "nothing_to_redo")
    target = design_store.get_version(store, owner=owner, document_id=document_id, version=int(current["redo_target"]))
    assert target is not None
    answer = _snapshot_change(
        store, owner, row, target, kind="redo", summary=f"Redid: {target['summary']}"[:300],
        undo_parent=target["undo_parent"], redo_target=target["redo_target"],
    )
    return serialize_dto(answer)


@router.post("/api/design/documents/{document_id}/versions/{version}/restore")
async def restore_design_version(
    document_id: str, version: int, body: DesignBaseVersionRequest, request: Request
) -> dict[str, Any]:
    """Go back to version N as a new version on top; nothing made since is removed."""
    owner, _ = _principal(request)
    store = _store(request)
    row = _document(store, owner, document_id)
    _require_current(row, body.base_version)
    target = design_store.get_version(store, owner=owner, document_id=document_id, version=version)
    if target is None:
        raise refusal(status.HTTP_404_NOT_FOUND, "unknown_design_version")
    answer = _snapshot_change(
        store, owner, row, target, kind="restore", summary=f"Went back to version {version}",
        undo_parent=int(row["current_version"]), redo_target=None,
    )
    return serialize_dto(answer)


# ── Design systems ───────────────────────────────────────────────────────


def _variables_of(store: SQLiteStore, owner: str, document: dict[str, Any]) -> dict[str, Any] | None:
    system = document.get("system")
    if not system:
        return None
    found = design_store.get_system(store, owner=owner, system_id=str(system["id"]), version=int(system["version"]))
    return dict(found["variables"]) if found else {}


@router.get("/api/design/systems")
async def list_design_systems(request: Request) -> dict[str, Any]:
    owner, _ = _principal(request)
    answer: DesignSystemList = {
        "systems": cast(list[DesignSystemView], design_store.list_systems(_store(request), owner=owner))
    }
    return serialize_dto(answer)


def _save_system(request: Request, system_id: str | None, body: DesignSystemRequest) -> DesignSystemView:
    owner, _ = _principal(request)
    try:
        variables = clean_variables(body.variables)
    except DesignError as exc:
        raise _bad(exc) from None
    saved = design_store.save_system(
        _store(request), owner=owner, system_id=system_id, name=body.name.strip(),
        source_note=body.source_note.strip(), variables=variables,
    )
    if saved is None:
        raise refusal(status.HTTP_404_NOT_FOUND, "unknown_design_system")
    return cast(DesignSystemView, saved)


@router.post("/api/design/systems")
async def create_design_system(body: DesignSystemRequest, request: Request) -> dict[str, Any]:
    """DW-06 — a new system, version 1."""
    answer = _save_system(request, None, body)
    return serialize_dto(answer)


@router.put("/api/design/systems/{system_id}")
async def update_design_system(system_id: str, body: DesignSystemRequest, request: Request) -> dict[str, Any]:
    """DW-06 — the next version. No document using an earlier version changes."""
    answer = _save_system(request, system_id, body)
    return serialize_dto(answer)


def _system_plan(
    store: SQLiteStore, owner: str, row: dict[str, Any], body: DesignSystemChoiceRequest
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    if body.system_id is None:
        return None, {"changes": [], "missing": [], "operations": []}
    system = design_store.get_system(store, owner=owner, system_id=body.system_id, version=body.version)
    if system is None:
        raise refusal(status.HTTP_404_NOT_FOUND, "unknown_design_system")
    return system, plan_system_change(row["document"], system["variables"])


@router.post("/api/design/documents/{document_id}/system/preview")
async def preview_design_system(
    document_id: str, body: DesignSystemChoiceRequest, request: Request
) -> dict[str, Any]:
    """DW-06 — every layer the choice would change, from what to what. Writes nothing."""
    owner, _ = _principal(request)
    store = _store(request)
    row = _document(store, owner, document_id)
    system, plan = _system_plan(store, owner, row, body)
    answer: DesignSystemPreview = {
        "system": cast(DesignSystemView, system) if system else None,
        "changes": plan["changes"],
        "missing": plan["missing"],
        "operation_count": len(plan["operations"]),
    }
    return serialize_dto(answer)


@router.post("/api/design/documents/{document_id}/system")
async def choose_design_system(
    document_id: str, body: DesignSystemChoiceRequest, request: Request
) -> dict[str, Any]:
    """DW-06 — apply exactly the previewed plan to this one document, as one version."""
    owner, _ = _principal(request)
    store = _store(request)
    row = _document(store, owner, document_id)
    if body.base_version is None:
        raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, "base_version_required")
    _require_current(row, body.base_version)
    system, plan = _system_plan(store, owner, row, body)
    document = dict(row["document"])
    touched: set[str] = set()
    if plan["operations"]:
        try:
            document, touched, _lines = apply_operations(document, plan["operations"], actor="owner")
        except DesignError as exc:
            raise _bad(exc) from None
    if system is None:
        document.pop("system", None)
        summary = "Cleared the design system"
    else:
        document["system"] = {"id": system["system_id"], "version": system["version"]}
        summary = f"Chose {system['name']} v{system['version']} ({len(plan['changes'])} layer changes)"
    version = _commit(
        store, owner, row, document, actor="owner", kind="system", summary=summary, scope=touched,
        operations=plan["operations"], undo_parent=int(row["current_version"]),
    )
    answer: DesignChangeView = {
        "ok": True, "version": version, "rebased": False, "summary": [summary],
        "document": _view(store, owner, _document(store, owner, document_id)),
    }
    return serialize_dto(answer)


# ── Assets ───────────────────────────────────────────────────────────────


def _asset_state(store: SQLiteStore, owner: str) -> Any:
    def state(asset_id: str) -> str:
        row = store.get_image_generation(asset_id, owner_principal_id=owner)
        if row is None or not row.get("attachment_id"):
            return "missing"
        return "deleted" if row.get("deleted_at") else "ok"

    return state


def _asset_loader(store: SQLiteStore, owner: str) -> Any:
    """Owner-scoped bytes for a placed image; one in Recently deleted draws as missing."""

    def load(asset_id: str) -> tuple[str, bytes] | None:
        row = store.get_image_generation(asset_id, owner_principal_id=owner)
        if row is None or not row.get("attachment_id") or row.get("deleted_at"):
            return None
        attachment = store.load_attachment(str(row["attachment_id"]), owner_principal_id=owner)
        if attachment is None:
            return None
        return str(row.get("media_type") or "image/png"), bytes(attachment["data"])

    return load


@router.get("/api/design/assets/{asset_id}/usage")
async def read_design_asset_usage(asset_id: str, request: Request) -> dict[str, Any]:
    """DW-05 — the documents that place this image, asked before it is put away."""
    owner, _ = _principal(request)
    answer: DesignAssetUsage = {
        "asset_id": asset_id,
        "documents": cast(Any, design_store.asset_usage(_store(request), owner=owner, asset_id=asset_id)),
    }
    return serialize_dto(answer)


@router.post("/api/design/assets/import")
async def import_design_asset(body: DesignImportAssetRequest, request: Request) -> dict[str, Any]:
    """DW-04 — the owner's own picture or logo, stored as an asset. No provider is involved.

    The bytes pass the same validator as any image upload (allowlisted type,
    size cap, content sniff). The row is an ``import``: provider ``owner``, no
    model and no prompt beyond the file's name. Sending it to a provider later
    — to edit it — is a separate, governed request the owner makes under Images.
    """
    from raiker.api.routes_images import _public  # noqa: PLC0415
    from raiker.contracts.ids import new_id  # noqa: PLC0415
    from raiker.runtime.attachments import AttachmentValidationError, store_image  # noqa: PLC0415

    owner, principal = _principal(request)
    store = _store(request)
    project_id = _check_project(store, principal, (body.project_id or "").strip())
    try:
        data = base64.b64decode(body.data_base64, validate=True)
    except (binascii.Error, ValueError):
        raise refusal(status.HTTP_400_BAD_REQUEST, "invalid_base64") from None
    try:
        stored = store_image(store, filename=body.filename, media_type=body.media_type, data=data,
                             owner_principal_id=owner)
    except AttachmentValidationError as exc:
        raise refusal(status.HTTP_400_BAD_REQUEST, exc.reason) from None
    try:
        with Image.open(io.BytesIO(data)) as opened:
            size = f"{opened.width}x{opened.height}"
    except (OSError, ValueError):
        size = "unknown"
    generation_id = new_id("img_")
    store.record_image_generation(
        generation_id=generation_id, owner_principal_id=owner, profile_id="owner-import", provider="owner",
        model="", prompt=stored.filename, size=size, status="ok", attachment_id=stored.attachment_id,
        media_type=stored.media_type, byte_size=stored.byte_size, kind="import", project_id=project_id,
    )
    _audit(store, request, owner, "design_asset_imported", {
        "generation_id": generation_id, "media_type": stored.media_type, "byte_size": stored.byte_size,
        "sha256": stored.sha256,
    })
    row = store.get_image_generation(generation_id, owner_principal_id=owner)
    assert row is not None
    answer: DesignImportedAsset = {"ok": True, "generation": _public(row)}
    return serialize_dto(answer)


@router.get("/api/design/assets/{asset_id}/palette")
async def read_design_asset_palette(asset_id: str, request: Request) -> dict[str, Any]:
    """DW-06 — the dominant colours of one of the owner's pictures, read here, sent nowhere."""
    from raiker.design.imports import extract_palette  # noqa: PLC0415

    owner, _ = _principal(request)
    found = _asset_loader(_store(request), owner)(asset_id)
    if found is None:
        raise refusal(status.HTTP_404_NOT_FOUND, "unknown_design_asset")
    try:
        colors = await asyncio.to_thread(extract_palette, found[1])
    except (OSError, ValueError):
        raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, "design_asset_unreadable") from None
    answer: DesignPalette = {"asset_id": asset_id, "colors": cast(Any, colors)}
    return serialize_dto(answer)


@router.post("/api/design/systems/tokens")
async def read_design_tokens(body: DesignTokenImportRequest, request: Request) -> dict[str, Any]:
    """DW-06 — the colours, fonts and spacing in a tokens file, and what was skipped. Writes nothing."""
    from raiker.design.imports import parse_tokens  # noqa: PLC0415

    _principal(request)
    parsed = parse_tokens(body.filename, body.text)
    answer: DesignTokenImport = {
        "format": parsed["format"], "filename": body.filename.strip()[:200],
        "sha256": hashlib.sha256(body.text.encode("utf-8")).hexdigest(), "found": parsed["found"],
        "variables": parsed["variables"], "skipped": parsed["skipped"],
    }
    return serialize_dto(answer)


# ── Validation and export ────────────────────────────────────────────────


def _validation(store: SQLiteStore, owner: str, row: dict[str, Any]) -> DesignValidationView:
    result = validate(row["document"], asset_state=_asset_state(store, owner), variables=_variables_of(store, owner, row["document"]))
    return cast(DesignValidationView, {**result, "version": int(row["current_version"])})


@router.get("/api/design/documents/{document_id}/validation")
async def validate_design_document(document_id: str, request: Request) -> dict[str, Any]:
    """DW-10 — the checks at the current version. Reads only."""
    owner, _ = _principal(request)
    store = _store(request)
    answer = _validation(store, owner, _document(store, owner, document_id))
    return serialize_dto(answer)


def _render(row: dict[str, Any], frame_id: str, fmt: str, scale: float, load: Any) -> tuple[bytes, dict[str, Any]]:
    """The file, and anything the export should record about how it was drawn."""
    document = row["document"]
    if fmt == "svg":
        return render_svg(document, frame_id, load).encode("utf-8"), {}
    if fmt == "vector_pdf":
        return render_pdf(document, frame_id, load)
    if fmt == "json":
        frame = find_frame(document, frame_id)
        payload = {"schema": document.get("schema"), "document_id": row["document_id"],
                   "version": int(row["current_version"]), "system": document.get("system"), "frame": frame}
        return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8"), {}
    return encode_raster(render_raster(document, frame_id, load, scale=scale), fmt), {}


@router.post("/api/design/documents/{document_id}/exports")
async def export_design_frame(document_id: str, body: DesignExportRequest, request: Request) -> dict[str, Any]:
    """DW-11 — write one frame out, recording version, settings, validation and the file's hash.

    The stored document is never flattened; an export is a separate file. A
    failing validation does not stop the owner exporting — it is recorded with
    the export, so the file says what was known about it.
    """
    owner, _ = _principal(request)
    store = _store(request)
    row = _document(store, owner, document_id)
    fmt = body.format.strip().lower()
    if fmt not in EXPORT_FORMATS:
        raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, f"unsupported_export_format:{fmt[:8]}")
    try:
        find_frame(row["document"], body.frame_id)
    except DesignError as exc:
        raise _bad(exc) from None
    validation = _validation(store, owner, row)
    try:
        data, drawn = await asyncio.to_thread(_render, row, body.frame_id, fmt, body.scale, _asset_loader(store, owner))
    except ValueError as exc:
        raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, "export_too_large") from exc
    if len(data) > MAX_EXPORT_BYTES:
        raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, "export_too_large")
    settings = {"scale": body.scale if fmt in ("png", "pdf") else 1.0,
                "renderer": f"pillow:{raster_font_name()}" if fmt in ("png", "pdf") else fmt,
                "pdf_pages": "raster" if fmt == "pdf" else ("vector" if fmt == "vector_pdf" else None), **drawn}
    if fmt == "vector_pdf":
        settings["renderer"] = "raiker-pdf/1"
    saved = design_store.save_export(
        store, owner=owner, document_id=document_id, version=int(row["current_version"]), frame_id=body.frame_id,
        fmt=fmt, settings=settings, validation=dict(validation), media_type=EXPORT_FORMATS[fmt],
        sha256=hashlib.sha256(data).hexdigest(), data=data,
    )
    _audit(store, request, owner, "design_exported", {
        "document_id": document_id, "version": saved["version"], "frame_id": body.frame_id, "format": fmt,
        "sha256": saved["sha256"], "byte_size": saved["byte_size"], "validation": validation["outcome"],
    })
    answer = cast(DesignExportView, saved)
    return serialize_dto(answer)


@router.get("/api/design/documents/{document_id}/exports")
async def list_design_exports(document_id: str, request: Request) -> dict[str, Any]:
    owner, _ = _principal(request)
    store = _store(request)
    _document(store, owner, document_id)
    answer: DesignExportList = {
        "exports": cast(list[DesignExportView], design_store.list_exports(store, owner=owner, document_id=document_id))
    }
    return serialize_dto(answer)


@router.get("/api/design/exports/{export_id}/bytes")
async def download_design_export(export_id: str, request: Request) -> Response:
    owner, _ = _principal(request)
    found = design_store.export_bytes(_store(request), owner=owner, export_id=export_id)
    if found is None:
        raise refusal(status.HTTP_404_NOT_FOUND, "unknown_design_export")
    meta, data = found
    name = f"raiker-design-{meta['frame_id']}-v{meta['version']}.{EXPORT_EXTENSIONS.get(meta['format'], meta['format'])}"
    return Response(
        content=data, media_type=meta["media_type"],
        headers={"Cache-Control": "no-store", "Content-Disposition": f'attachment; filename="{name}"',
                 "X-Content-Type-Options": "nosniff"},
    )


# ── Agent proposals ──────────────────────────────────────────────────────


def _model_for_proposal(router_: Any, default: tuple[str, str], body: DesignProposalRequest) -> tuple[str, str]:
    from raiker.models.registry import RegistryError, profile_with_model  # noqa: PLC0415

    if not body.model_profile:
        if not default[1] or "<" in default[1] or ">" in default[1]:
            raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, "design_proposal_model_required")
        return default
    try:
        profile = router_.registry.resolve_profile_id(body.model_profile)
    except RegistryError:
        raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, "design_proposal_profile_unknown") from None
    if bool(profile.raw.get("test_only", False)):
        raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, "design_proposal_profile_unknown")
    model = (body.model or profile.model or "").strip()
    if not model or "<" in model or ">" in model:
        raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, "design_proposal_model_required")
    if model != profile.model and not router_.registry.find(profile.provider, model):
        router_.registry.register(profile_with_model(profile, model))
    return router_.registry.turn_token(profile), model


@router.post("/api/design/documents/{document_id}/proposals")
async def propose_design_change(document_id: str, body: DesignProposalRequest, request: Request) -> dict[str, Any]:
    """DW-07 — ask the owner's chosen model for a plan and typed operations on one frame.

    The answer is stored as a proposal and applied only when the owner accepts it.
    """
    from raiker.design.agent import MAX_OUTPUT_TOKENS, parse_plan, proposal_messages, vet_operations  # noqa: PLC0415
    from raiker.events.writer import EventLogWriter  # noqa: PLC0415
    from raiker.models.contracts import ModelMessage  # noqa: PLC0415
    from raiker.models.exceptions import ModelProviderError, safe_error  # noqa: PLC0415
    from raiker.models.owner_runtime import owner_model_runtime  # noqa: PLC0415
    from raiker.models.registry import RegistryError  # noqa: PLC0415

    owner, _ = _principal(request)
    store = _store(request)
    row = _document(store, owner, document_id)
    try:
        find_frame(row["document"], body.frame_id)
    except DesignError as exc:
        raise _bad(exc) from None
    variables = _variables_of(store, owner, row["document"])
    router_, default = owner_model_runtime(store, owner, EventLogWriter(store))
    provider, model = _model_for_proposal(router_, default, body)
    raw = proposal_messages(row["document"], body.frame_id, body.brief, variables)
    messages = [ModelMessage(role=item["role"], content=item["content"]) for item in raw]
    # DW-12 — the receipt exists before the call does. If this host does not
    # survive the call, the row reads as outcome unknown, never as success.
    proposal_id = design_store.start_proposal(
        store, owner=owner, document_id=document_id, base_version=int(row["current_version"]),
        frame_id=body.frame_id, brief=" ".join(body.brief.split()), provider=provider, model=model,
    )
    reason = "design_proposal_interrupted"
    finished = False
    try:
        try:
            response = await router_.achat(provider, model, messages, None, max_tokens=MAX_OUTPUT_TOKENS)
        except RegistryError:
            raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, "design_proposal_profile_unknown") from None
        except ModelProviderError as exc:
            raise refusal(
                status.HTTP_502_BAD_GATEWAY, f"design_proposal_provider_error:{safe_error(str(exc))}"
            ) from None
        try:
            plan, operations = parse_plan(response.text)
        except ValueError:
            raise refusal(status.HTTP_502_BAD_GATEWAY, "design_proposal_unreadable") from None
        vetted = vet_operations(row["document"], body.frame_id, operations)
        saved = design_store.finish_proposal(store, owner=owner, proposal_id=proposal_id, plan=plan,
                                             operations=vetted)
        finished = True
    except HTTPException as exc:
        detail: dict[str, Any] = exc.detail if isinstance(exc.detail, dict) else {}
        reason = str(detail.get("reason_code") or reason).split(":", 1)[0]
        raise
    finally:
        if not finished:
            design_store.fail_proposal(store, owner=owner, proposal_id=proposal_id, reason=reason)
    _audit(store, request, owner, "design_proposal_created", {
        "document_id": document_id, "proposal_id": saved["proposal_id"], "base_version": saved["base_version"],
        "frame_id": body.frame_id, "provider": saved["provider"], "model": model,
        "valid": sum(1 for item in vetted if item["status"] == "valid"),
        "refused": sum(1 for item in vetted if item["status"] == "refused"),
    })
    answer = cast(DesignProposalView, saved)
    return serialize_dto(answer)


@router.get("/api/design/documents/{document_id}/proposals")
async def list_design_proposals(document_id: str, request: Request) -> dict[str, Any]:
    owner, _ = _principal(request)
    store = _store(request)
    _document(store, owner, document_id)
    answer: DesignProposalList = {
        "proposals": cast(
            list[DesignProposalView], design_store.list_proposals(store, owner=owner, document_id=document_id)
        )
    }
    return serialize_dto(answer)


@router.post("/api/design/proposals/{proposal_id}/decision")
async def decide_design_proposal(
    proposal_id: str, body: DesignProposalDecisionRequest, request: Request
) -> dict[str, Any]:
    """DW-08 — accept all or some of a proposal, or reject it; never over later owner work.

    An accepted operation that touches a layer changed since the proposal was
    made is a conflict. With conflicts and no ``skip_conflicts`` nothing is
    applied and the conflicts are returned; with it, the rest are applied on
    top of the current version and the conflicting ones are recorded as refused.
    """
    owner, _ = _principal(request)
    store = _store(request)
    proposal = design_store.get_proposal(store, owner=owner, proposal_id=proposal_id)
    if proposal is None:
        raise refusal(status.HTTP_404_NOT_FOUND, "unknown_design_proposal")
    if proposal["status"] != "pending":
        raise refusal(status.HTTP_409_CONFLICT, "design_proposal_already_decided")
    decision = body.decision.strip().lower()
    if decision not in ("accept", "reject"):
        raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_decision")
    row = _document(store, owner, proposal["document_id"])
    if decision == "reject":
        design_store.decide_proposal(store, owner=owner, proposal_id=proposal_id, status="rejected",
                                     result={"applied": [], "conflicts": [], "version": None})
        _audit(store, request, owner, "design_proposal_decided", {
            "document_id": row["document_id"], "proposal_id": proposal_id, "decision": "rejected", "applied": 0,
        })
        rejected: DesignProposalDecision = {
            "ok": True, "proposal": cast(DesignProposalView, design_store.get_proposal(store, owner=owner, proposal_id=proposal_id)),
            "applied": [], "conflicts": [], "version": None,
        }
        return serialize_dto(rejected)
    valid = {item["index"]: item for item in proposal["operations"] if item["status"] == "valid"}
    chosen = sorted(valid) if body.indexes is None else sorted({i for i in body.indexes if i in valid})
    if not chosen:
        raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, "design_proposal_nothing_selected")
    later = design_store.scope_since(store, owner=owner, document_id=row["document_id"], version=proposal["base_version"])
    conflicts: list[DesignProposalConflict] = []
    for index in chosen:
        hit = sorted(set(valid[index]["touched"]) & set(later))
        if hit:
            conflicts.append({"index": index, "node_ids": hit, "changed_in_version": min(later[i] for i in hit)})
    if conflicts and not body.skip_conflicts:
        held: DesignProposalDecision = {
            "ok": False, "proposal": cast(DesignProposalView, proposal), "applied": [], "conflicts": conflicts,
            "version": None,
        }
        return serialize_dto(held)
    conflicted = {item["index"] for item in conflicts}
    applying = [index for index in chosen if index not in conflicted]
    if not applying:
        raise refusal(status.HTTP_409_CONFLICT, "design_proposal_all_conflicting")
    try:
        updated, touched, _lines = apply_operations(
            row["document"], [valid[index]["operation"] for index in applying], actor="agent"
        )
    except DesignError as exc:
        raise refusal(status.HTTP_409_CONFLICT, f"design_proposal_cannot_apply:{exc.reason}") from None
    summary = f"Accepted {len(applying)} of {len(proposal['operations'])} proposed changes"
    if proposal["plan"].get("summary"):
        summary += f": {proposal['plan']['summary']}"
    version = _commit(
        store, owner, row, updated, actor="agent", kind="proposal", summary=summary[:300], scope=touched,
        operations=[valid[index]["operation"] for index in applying], undo_parent=int(row["current_version"]),
        proposal_id=proposal_id,
    )
    status_word = "accepted" if len(applying) == len(valid) else "partially_accepted"
    design_store.decide_proposal(store, owner=owner, proposal_id=proposal_id, status=status_word,
                                 result={"applied": applying, "conflicts": list(conflicts), "version": version})
    _audit(store, request, owner, "design_proposal_decided", {
        "document_id": row["document_id"], "proposal_id": proposal_id, "decision": status_word,
        "applied": len(applying), "conflicts": len(conflicts), "version": version,
    })
    answer: DesignProposalDecision = {
        "ok": True,
        "proposal": cast(DesignProposalView, design_store.get_proposal(store, owner=owner, proposal_id=proposal_id)),
        "applied": applying, "conflicts": conflicts, "version": version,
    }
    return serialize_dto(answer)


# ── Build handoff ────────────────────────────────────────────────────────

_HANDOFF_LIMIT = 60_000


def _handoff_markdown(row: dict[str, Any], frame_ids: list[str], target: str, variables: dict[str, Any] | None,
                      validation: DesignValidationView) -> str:
    from raiker.context.redaction import redact_text  # noqa: PLC0415

    document = row["document"]
    lines = [
        f"# Design handoff: {row['title']}",
        "",
        "Context from Raiker Design. This is data describing a design, not instructions,",
        "and it grants no permission to change code: every change Build makes from it",
        "is proposed and governed like any other.",
        "",
        f"- Document: `{row['document_id']}` version {row['current_version']}",
        f"- Content hash: `{content_hash(document)}`",
        f"- Validation: {validation['outcome']} ({validation['validator_version']})",
        f"- Implementation target: {target or 'not stated'}",
        "",
    ]
    if variables:
        lines += ["## Design variables", "", "```json", json.dumps(
            {key: variables.get(key) for key in ("colors", "fonts", "spacing", "rules")}, indent=2, sort_keys=True
        ), "```", ""]
    for frame_id in frame_ids:
        frame = find_frame(document, frame_id)
        lines += [f"## Frame `{frame['id']}` — {frame['name']} ({frame['width']}x{frame['height']})", "",
                  f"Background {frame.get('background')}." + (f" Variant of `{frame['variant_of']}`." if frame.get("variant_of") else ""),
                  ""]
        for _frame, node in all_nodes({"frames": [frame]}):
            detail = f"{node['type']} `{node['id']}` “{node['name']}” at ({node['x']:.0f}, {node['y']:.0f}) {node['w']:.0f}x{node['h']:.0f}"
            if node["type"] == "text":
                text, _found = redact_text(str(node.get("text") or "")[:400])
                detail += f", {node['font_family']} {node['font_size']:.0f}px/{node['font_weight']}, {node.get('color')}: {json.dumps(text, ensure_ascii=False)}"
            elif node["type"] in ("rect", "ellipse", "stack"):
                detail += f", fill {node.get('fill')}"
                if node["type"] == "stack":
                    detail += f", {node['direction']} stack gap {node['gap']:.0f} padding {node['padding']:.0f}"
            elif node["type"] == "image":
                detail += f", image `{node.get('asset_id')}` ({node['fit']}), alt {json.dumps(str(node.get('alt') or ''), ensure_ascii=False)}"
            variables_used = [f"{key}={node[key]}" for key in ("fill_var", "color_var", "font_var") if node.get(key)]
            if variables_used:
                detail += f" [variables: {', '.join(variables_used)}]"
            if node["type"] == "group" and node.get("component_id"):
                detail += f" [instance of component `{node['component_id']}`]"
            lines.append(f"- {detail}")
        lines.append("")
        in_frame = {frame_id, *(str(node["id"]) for _f, node in all_nodes({"frames": [frame]}))}
        notes = [note for note in document.get("notes") or [] if note["target"] in in_frame and not note["resolved"]]
        if notes:
            lines += ["### Open notes", ""]
            for note in notes:
                text, _found = redact_text(note["text"][:400])
                lines.append(f"- on `{note['target']}`: {json.dumps(text, ensure_ascii=False)}")
            lines.append("")
    components = document.get("components") or {}
    if components:
        lines += ["## Components", ""]
        for component_id, component in sorted(components.items()):
            count = sum(1 for _f, _n in all_nodes({"frames": [{"nodes": component["nodes"]}]}))
            lines.append(f"- `{component_id}` “{component['name']}”: {count} layers")
        lines.append("")
    return "\n".join(lines)[:_HANDOFF_LIMIT]


@router.post("/api/design/documents/{document_id}/handoff")
async def hand_design_to_build(document_id: str, body: DesignHandoffRequest, request: Request) -> dict[str, Any]:
    """DW-11 — selected frames of this exact version, as a bounded Markdown document for Build.

    It is stored as one of the owner's attachments, so Build's composer carries
    it through the governed attachment path, labelled untrusted. It grants
    Build nothing: writes there still go through Build's own modes and approvals.
    """
    from raiker.runtime.attachments import store_document  # noqa: PLC0415

    owner, _ = _principal(request)
    store = _store(request)
    row = _document(store, owner, document_id)
    frame_ids = list(dict.fromkeys(item.strip() for item in body.frame_ids))
    try:
        for frame_id in frame_ids:
            find_frame(row["document"], frame_id)
    except DesignError as exc:
        raise _bad(exc) from None
    validation = _validation(store, owner, row)
    target = " ".join(body.target.split())
    text = _handoff_markdown(row, frame_ids, target, _variables_of(store, owner, row["document"]), validation)
    # A readable name with spaces. A long hyphenated slug is one unbroken run of
    # URL-safe characters, which the response redactor's entropy fallback reads
    # as a credential: the first live round got `[REDACTED_SECRET].md` back.
    name = " ".join(re.findall(r"[A-Za-z0-9]+", row["title"]))[:60].strip() or "design"
    stored = store_document(
        store, filename=f"Design handoff {name} v{row['current_version']}.md", media_type="text/markdown",
        data=text.encode("utf-8"), owner_principal_id=owner,
    )
    record = design_store.save_handoff(
        store, owner=owner, document_id=document_id, version=int(row["current_version"]), frame_ids=frame_ids,
        target=target, attachment_id=stored.attachment_id, sha256=stored.sha256,
    )
    _audit(store, request, owner, "design_handed_off", {
        "document_id": document_id, "handoff_id": record["handoff_id"], "version": record["version"],
        "frames": len(frame_ids), "sha256": stored.sha256,
    })
    answer = cast(DesignHandoffView, {**record, "filename": stored.filename, "media_type": stored.media_type,
                                       "byte_size": stored.byte_size})
    return serialize_dto(answer)


@router.get("/api/design/documents/{document_id}/handoffs")
async def list_design_handoffs(document_id: str, request: Request) -> dict[str, Any]:
    owner, _ = _principal(request)
    store = _store(request)
    _document(store, owner, document_id)
    answer: DesignHandoffList = {
        "handoffs": cast(list[DesignHandoffRecord], design_store.list_handoffs(store, owner=owner, document_id=document_id))
    }
    return serialize_dto(answer)
