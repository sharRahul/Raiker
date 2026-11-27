"""Wire shapes for Raiker Notes."""

from __future__ import annotations

from typing import Any, TypedDict


class NoteFileView(TypedDict):
    path: str
    name: str
    mtime: float
    size: int


class NoteTagCount(TypedDict):
    tag: str
    count: int


class NotesIndex(TypedDict):
    root: str
    notes: list[NoteFileView]
    tags: list[NoteTagCount]


class NoteHeading(TypedDict):
    level: int
    text: str
    line: int


class NoteTask(TypedDict):
    text: str
    done: bool
    line: int


class NoteLink(TypedDict):
    target: str
    heading: str
    block: str
    alias: str
    embed: bool
    line: int
    resolved: str | None


class NoteView(TypedDict):
    path: str
    name: str
    content: str
    mtime: float
    properties: dict[str, Any]
    tags: list[str]
    aliases: list[str]
    headings: list[NoteHeading]
    tasks: list[NoteTask]
    links: list[NoteLink]
    links_updated: int


class NoteMention(TypedDict):
    path: str
    name: str
    line: int
    context: str
    match: str


class NoteBacklinks(TypedDict):
    path: str
    linked: list[NoteMention]
    unlinked: list[NoteMention]


class NoteGraphNode(TypedDict):
    path: str
    name: str
    links_in: int


class NoteGraphEdge(TypedDict):
    source: str
    target: str


class NoteGraph(TypedDict):
    nodes: list[NoteGraphNode]
    edges: list[NoteGraphEdge]
    unresolved: list[str]


class NoteSearchHit(TypedDict):
    path: str
    name: str
    line: int | None
    snippet: str
    mtime: float


class NoteTrashed(TypedDict):
    ok: bool
    trashed: str


class NoteResolved(TypedDict):
    path: str | None
