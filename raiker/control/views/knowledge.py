"""The brain graph: nodes, edges and the read that holds them."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from typing_extensions import NotRequired, TypedDict

from raiker.contracts.views import View


@dataclass(frozen=True)
class BrainNodeView(View):
    node_id: str
    node_type: str
    label: str
    status: str
    detail: str | None = None
    progress_percent: int | None = None
    is_real: bool = True


@dataclass(frozen=True)
class BrainEdgeView(View):
    source: str
    target: str
    relationship: str
    is_active: bool = False
    relationship_id: str | None = None
    evidence_memory_id: str | None = None
    owner_can_reject: bool = False


@dataclass(frozen=True)
class BrainView(View):
    generated_at: str
    nodes: tuple[BrainNodeView, ...]
    edges: tuple[BrainEdgeView, ...]
    illustrative_motion_notice: str = (
        "Animated pulses indicate visual activity only; every node and connection is stored runtime data."
    )



class BrainSourceRoot(TypedDict):
    """A place the Knowledge Map may look. ``path`` only for a folder the owner granted."""

    root_id: str
    label: str
    detail: str
    kind: Literal["raiker", "granted", "database"]
    browsable: bool
    path: str | None


class BrainSourceRoots(TypedDict):
    roots: list[BrainSourceRoot]


class BrainSourceChild(TypedDict):
    name: str
    path: str
    kind: Literal["folder", "file"]
    size_bytes: int | None


class BrainSourceBrowse(TypedDict):
    """One folder inside a root; an empty ``path`` answers with the roots themselves."""

    path: str
    parent: str | None
    roots: list[BrainSourceRoot]
    children: list[BrainSourceChild]
    truncated: bool


class BrainSourceReview(TypedDict):
    """What adding a source would read, before anything is read (NEW-MAP-03)."""

    path: str
    kind: Literal["folder", "file"]
    supported_files: int
    unsupported_files: int
    total_bytes: int
    examples: list[str]
    warnings: list[str]
    review_cap: int
    visited_entries: int
    truncated: bool
    truncated_reason: str | None


class BrainSourceResult(TypedDict):
    ok: bool
    path: str


class BrainSourceGranted(TypedDict):
    ok: bool
    root_id: str
    path: str


class BrainSourceRevoked(TypedDict):
    ok: bool
    root_id: str


class BrainSourceUploaded(TypedDict):
    """A file copied into the workspace, with the owner's permission to keep the copy."""

    ok: bool
    path: str
    stored_copy: bool
    byte_size: int


class BrainPreferences(TypedDict):
    settings: dict[str, Any]


class BrainPreferencesSaved(TypedDict):
    ok: bool
    settings: dict[str, Any]
    updated_at: str


class KnowledgeSource(TypedDict):
    """One thing Raiker may read: a file it holds, or a folder the owner granted (BUG-305)."""

    source_id: str
    kind: Literal["managed_file", "granted_folder"]
    label: str
    location: str
    scope: str
    held: bool
    index_state: str
    recall: bool
    graph: bool
    added_at: str


class KnowledgeSources(TypedDict):
    sources: list[KnowledgeSource]
    held_count: int
    granted_count: int


class KnowledgeSourceRevoked(TypedDict):
    ok: bool
    source_id: str
