"""QUI-F15 — the Library: everything Raiker has made, and the blocks pinned to it.

Three rules hold for every route here:

* **Owner-scoped, always.** Items, pins and the conversations they name are
  resolved against the signed-in account; another account's id answers as one
  never issued.
* **A pin is copied from the record, never from the browser.** The request
  names a stored turn and a block's place in its answer; the runtime splits that
  stored answer again and keeps only a block it validates. A pin can therefore
  hold nothing the transcript did not already show.
* **Pinning grants nothing.** Filing a block in a project changes no policy,
  gate or context; it is a bookmark with a copy of the block.
"""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Request, status

from raiker.api.dependencies import authenticate, refusal, require_human
from raiker.api.dependencies import workspace_root as _ws
from raiker.api.schemas import LibraryPinMoveRequest, LibraryPinRequest, serialize_dto
from raiker.api.wire.library import (
    LibraryPinned,
    LibraryPinRemoved,
    LibraryPinState,
    LibraryView,
    SessionPins,
)
from raiker.control.library import LIBRARY_KINDS, block_title, library_items
from raiker.runtime.typed_parts import BLOCK_TYPES, content_parts
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()


def _context(request: Request, *, human: bool = False) -> tuple[SQLiteStore, str, str | None]:
    _session, principal = authenticate(request)
    if human:
        require_human(principal)
    store = SQLiteStore(_ws(request))
    owner = str(principal.principal_id)
    return store, owner, store.principal_user_id(owner)


def _visible_session(store: SQLiteStore, session_id: str, user_id: str | None) -> dict[str, Any]:
    session = store.load_session(session_id)
    if session is None or (user_id and session.get("user_id") not in (None, user_id)):
        raise refusal(status.HTTP_404_NOT_FOUND, "unknown_session")
    return session


@router.get("/api/library")
async def get_library(
    request: Request, project_id: str | None = None, kind: str | None = None
) -> dict[str, Any]:
    """Documents, images, designs, pinned blocks and pull requests, newest first."""
    store, owner, user_id = _context(request)
    if kind is not None and kind not in LIBRARY_KINDS:
        raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, "library_kind_unknown")
    if project_id and store.load_project(project_id, user_id=user_id) is None:
        raise refusal(status.HTTP_404_NOT_FOUND, "unknown_project")
    answer: LibraryView = {
        "items": library_items(
            store, owner_principal_id=owner, user_id=user_id, project_id=project_id or None, kind=kind
        ),
        "kinds": list(LIBRARY_KINDS),
    }
    return serialize_dto(answer)


@router.get("/api/library/pins")
async def list_session_pins(request: Request, session_id: str) -> dict[str, Any]:
    """Which blocks of one conversation are pinned, so its toolbars can say so."""
    store, owner, user_id = _context(request)
    _visible_session(store, session_id, user_id)
    answer: SessionPins = {
        "session_id": session_id,
        "pins": [
            cast(LibraryPinState, {
                "pin_id": str(row["pin_id"]),
                "turn_id": str(row["turn_id"]),
                "part_index": int(row["part_index"]),
                "project_id": row["project_id"],
            })
            for row in store.pinned_parts_for_session(owner_principal_id=owner, session_id=session_id)
        ],
    }
    return serialize_dto(answer)


@router.post("/api/library/pins", status_code=status.HTTP_201_CREATED)
async def pin_block(body: LibraryPinRequest, request: Request) -> dict[str, Any]:
    """Pin one block of a stored answer, filed in a project or in the Library only."""
    store, owner, user_id = _context(request, human=True)
    _visible_session(store, body.session_id, user_id)
    turn = store.load_turn(body.turn_id)
    if turn is None or str(turn.get("session_id")) != body.session_id:
        raise refusal(status.HTTP_404_NOT_FOUND, "unknown_turn")
    project_name: str | None = None
    if body.project_id:
        project = store.load_project(body.project_id, user_id=user_id)
        if project is None:
            raise refusal(status.HTTP_404_NOT_FOUND, "unknown_project")
        project_name = str(project["name"])
    parts = content_parts(str(turn.get("summary") or ""))
    if body.part_index >= len(parts) or parts[body.part_index].type not in BLOCK_TYPES:
        # Prose, a refusal, or a place past the end: nothing drawn to pin.
        raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, "library_pin_not_a_block")
    part = parts[body.part_index]
    pin = store.save_library_pin(
        owner_principal_id=owner,
        session_id=body.session_id,
        turn_id=body.turn_id,
        part_index=body.part_index,
        part_type=part.type,
        title=block_title(part.type, part.data),
        data=part.data,
        project_id=body.project_id or None,
    )
    answer: LibraryPinned = {
        "pin_id": str(pin["pin_id"]),
        "project_id": pin["project_id"],
        "project_name": project_name,
    }
    return serialize_dto(answer)


@router.put("/api/library/pins/{pin_id}/project")
async def move_pin(pin_id: str, body: LibraryPinMoveRequest, request: Request) -> dict[str, Any]:
    """File a pin in another project, or in none. Grants and changes nothing else."""
    store, owner, user_id = _context(request, human=True)
    project_name: str | None = None
    if body.project_id:
        project = store.load_project(body.project_id, user_id=user_id)
        if project is None:
            raise refusal(status.HTTP_404_NOT_FOUND, "unknown_project")
        project_name = str(project["name"])
    if not store.move_library_pin(pin_id, owner_principal_id=owner, project_id=body.project_id or None):
        raise refusal(status.HTTP_404_NOT_FOUND, "library_pin_not_found")
    answer: LibraryPinned = {"pin_id": pin_id, "project_id": body.project_id or None, "project_name": project_name}
    return serialize_dto(answer)


@router.delete("/api/library/pins/{pin_id}")
async def unpin_block(pin_id: str, request: Request) -> dict[str, Any]:
    """Remove a pin. The answer it was copied from is untouched."""
    store, owner, _user_id = _context(request, human=True)
    if not store.delete_library_pin(pin_id, owner_principal_id=owner):
        raise refusal(status.HTTP_404_NOT_FOUND, "library_pin_not_found")
    answer: LibraryPinRemoved = {"ok": True, "pin_id": pin_id}
    return serialize_dto(answer)
