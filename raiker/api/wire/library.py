"""QUI-F15 — what the Library routes answer with."""

from __future__ import annotations

from typing_extensions import TypedDict

from raiker.control.library import LibraryItem


class LibraryView(TypedDict):
    items: list[LibraryItem]
    #: Every kind the Library can hold, in the order the filter lists them.
    kinds: list[str]


class LibraryPinState(TypedDict):
    pin_id: str
    turn_id: str
    part_index: int
    project_id: str | None


class SessionPins(TypedDict):
    session_id: str
    pins: list[LibraryPinState]


class LibraryPinned(TypedDict):
    pin_id: str
    project_id: str | None
    project_name: str | None


class LibraryPinRemoved(TypedDict):
    ok: bool
    pin_id: str
