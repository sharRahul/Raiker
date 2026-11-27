"""Raiker Notes — a linked-Markdown notebook in the owner's notes folder.

The folder is the one Memory › Controls names (an Obsidian vault works as is),
or ``Notes`` beside the workspace when none is chosen. Raiker's own memory is
one folder in it, ``Raiker Memory/``: a note saved there is synced back into
memory straight away, through the same rules as an edit made in Obsidian.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, Depends, Request, status

from raiker.api.dependencies import authenticate as _auth
from raiker.api.dependencies import refusal
from raiker.api.schemas import serialize_dto
from raiker.api.sessions import ApiSession
from raiker.api.wire.notes import (
    NoteBacklinks,
    NoteGraph,
    NoteResolved,
    NoteSearchHit,
    NotesIndex,
    NoteTrashed,
    NoteView,
)
from raiker.control.dashboard import DashboardService
from raiker.notes.vault import NotesError, NotesVault
from raiker.runtime.authority.models import Principal

router = APIRouter()

_NOT_FOUND = {"note_not_found", "note_mention_not_found"}
_CONFLICT = {"note_changed_elsewhere", "note_exists"}


def notes_root(service: DashboardService, owner: str) -> Path:
    chosen = service.store.memory_vault_path(owner)
    return Path(chosen) if chosen else Path(service.workspace_root) / "Notes"


def _vault(request: Request, auth_data: tuple[ApiSession, Principal]) -> tuple[DashboardService, NotesVault, str]:
    ws = request.app.state.workspace_root  # type: ignore[attr-defined]
    service = DashboardService(ws)
    owner = auth_data[0].principal_id
    if not service._is_human(owner):  # noqa: SLF001
        raise refusal(status.HTTP_403_FORBIDDEN, "not_authorized_human")
    return service, NotesVault(notes_root(service, owner)), owner


def _refuse(error: NotesError) -> Exception:
    code = str(error)
    return refusal(
        status.HTTP_404_NOT_FOUND if code in _NOT_FOUND
        else status.HTTP_409_CONFLICT if code in _CONFLICT
        else status.HTTP_422_UNPROCESSABLE_CONTENT,
        code,
    )


def _after_write(service: DashboardService, owner: str, path: str) -> None:
    """A note saved in ``Raiker Memory/`` changes memory, under the vault rules."""
    from raiker.memory.vault import MEMORY_FOLDER

    if path.startswith(f"{MEMORY_FOLDER}/") and service.store.memory_vault_path(owner):
        service.sync_memory_vault(owner)


@router.get("/api/notes")
async def list_notes(request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)) -> dict[str, Any]:
    _, vault, _ = _vault(request, auth_data)
    answer = cast(NotesIndex, await asyncio.to_thread(lambda: {
        "root": str(vault.root),
        "notes": [item.__dict__ for item in vault.files()],
        "tags": vault.tags(),
    }))
    return serialize_dto(answer)


@router.get("/api/notes/note")
async def read_note(request: Request, path: str, auth_data: tuple[ApiSession, Principal] = Depends(_auth)) -> dict[str, Any]:
    _, vault, _ = _vault(request, auth_data)
    try:
        data = await asyncio.to_thread(vault.read, path)
        answer = cast(NoteView, {"links_updated": 0, **data})
        return serialize_dto(answer)
    except NotesError as error:
        raise _refuse(error) from error


@router.put("/api/notes/note")
async def save_note(request: Request, body: dict[str, Any], auth_data: tuple[ApiSession, Principal] = Depends(_auth)) -> dict[str, Any]:
    """Save a note; ``expected_mtime`` is the version edited, so a change made elsewhere is not overwritten."""
    service, vault, owner = _vault(request, auth_data)
    expected = body.get("expected_mtime")
    try:
        saved = await asyncio.to_thread(
            lambda: vault.write(
                str(body.get("path", "")), str(body.get("content", "")),
                expected_mtime=float(expected) if expected is not None else None,
            )
        )
    except (NotesError, ValueError) as error:
        raise _refuse(NotesError(str(error))) from error
    await asyncio.to_thread(_after_write, service, owner, saved["path"])
    data = saved
    answer = cast(NoteView, {"links_updated": 0, **data})
    return serialize_dto(answer)


@router.post("/api/notes/note")
async def create_note(request: Request, body: dict[str, Any], auth_data: tuple[ApiSession, Principal] = Depends(_auth)) -> dict[str, Any]:
    _, vault, _ = _vault(request, auth_data)
    try:
        data = await asyncio.to_thread(vault.create, str(body.get("path", "")), str(body.get("content", "")))
        answer = cast(NoteView, {"links_updated": 0, **data})
        return serialize_dto(answer)
    except NotesError as error:
        raise _refuse(error) from error


@router.delete("/api/notes/note")
async def trash_note(request: Request, path: str, auth_data: tuple[ApiSession, Principal] = Depends(_auth)) -> dict[str, Any]:
    """Move a note to the vault's ``.trash`` (restorable), as Obsidian does."""
    _, vault, _ = _vault(request, auth_data)
    try:
        trashed = await asyncio.to_thread(vault.delete, path)
    except NotesError as error:
        raise _refuse(error) from error
    answer = cast(NoteTrashed, {"ok": True, "trashed": trashed})
    return serialize_dto(answer)


@router.post("/api/notes/rename")
async def rename_note(request: Request, body: dict[str, Any], auth_data: tuple[ApiSession, Principal] = Depends(_auth)) -> dict[str, Any]:
    """Rename a note and rewrite every link to it."""
    _, vault, _ = _vault(request, auth_data)
    try:
        data = await asyncio.to_thread(vault.rename, str(body.get("from", "")), str(body.get("to", "")))
        answer = cast(NoteView, {"links_updated": 0, **data})
        return serialize_dto(answer)
    except NotesError as error:
        raise _refuse(error) from error


@router.get("/api/notes/backlinks")
async def note_backlinks(request: Request, path: str, auth_data: tuple[ApiSession, Principal] = Depends(_auth)) -> dict[str, Any]:
    _, vault, _ = _vault(request, auth_data)
    try:
        answer = cast(NoteBacklinks, await asyncio.to_thread(vault.backlinks, path))
    except NotesError as error:
        raise _refuse(error) from error
    return serialize_dto(answer)


@router.post("/api/notes/link-mention")
async def link_note_mention(request: Request, body: dict[str, Any], auth_data: tuple[ApiSession, Principal] = Depends(_auth)) -> dict[str, Any]:
    """Turn an unlinked mention into a link, in place."""
    service, vault, owner = _vault(request, auth_data)
    try:
        saved = await asyncio.to_thread(
            vault.link_mention, str(body.get("source", "")), int(body.get("line", -1)), str(body.get("target", ""))
        )
    except (NotesError, ValueError) as error:
        raise _refuse(NotesError(str(error))) from error
    await asyncio.to_thread(_after_write, service, owner, saved["path"])
    data = saved
    answer = cast(NoteView, {"links_updated": 0, **data})
    return serialize_dto(answer)


@router.get("/api/notes/graph")
async def note_graph(
    request: Request, path: str | None = None, depth: int = 1,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    _, vault, _ = _vault(request, auth_data)
    try:
        answer = cast(NoteGraph, await asyncio.to_thread(vault.graph, path, depth))
    except NotesError as error:
        raise _refuse(error) from error
    return serialize_dto(answer)


@router.get("/api/notes/search")
async def search_notes(request: Request, q: str, auth_data: tuple[ApiSession, Principal] = Depends(_auth)) -> list[dict[str, Any]]:
    _, vault, _ = _vault(request, auth_data)
    answer: list[NoteSearchHit] = cast(list[NoteSearchHit], await asyncio.to_thread(vault.search, q))
    return serialize_dto(answer)


@router.post("/api/notes/daily")
async def open_daily_note(request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)) -> dict[str, Any]:
    """Today's note (``Daily/YYYY-MM-DD``), created from ``Templates/Daily.md`` when that exists."""
    _, vault, _ = _vault(request, auth_data)
    template_path = vault.root / "Templates" / "Daily.md"
    template = template_path.read_text(encoding="utf-8") if template_path.is_file() else None
    data = await asyncio.to_thread(lambda: vault.daily(template=template))
    answer = cast(NoteView, {"links_updated": 0, **data})
    return serialize_dto(answer)


@router.get("/api/notes/resolve")
async def resolve_note_link(
    request: Request, target: str, from_path: str = "",
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    _, vault, _ = _vault(request, auth_data)
    answer = cast(NoteResolved, {"path": await asyncio.to_thread(lambda: vault.resolve(target, from_path=from_path))})
    return serialize_dto(answer)
