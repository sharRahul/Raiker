"""Memory controls, observations and memory settings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, NotRequired

from typing_extensions import TypedDict

from raiker.contracts.views import View


@dataclass(frozen=True)
class MemoryControlView(View):
    """User-facing view of one approved memory entry.

    Carries the governance metadata the user needs to trust, scope, and
    control the memory: provenance, sensitivity, confidence, retention, and
    an organizing pin flag. The text is the stored memory text (the same
    data the governed memory store already persists); no new authority is
    granted by exposing it through this read.
    """

    memory_id: str
    text: str
    scope: str
    sensitivity: str
    memory_type: str
    created_at: str
    tags: tuple[str, ...]
    source: str
    provenance: dict[str, Any]
    confidence: float
    trust_score: float
    retention: str
    approval_state: str
    pinned: bool
    search_enabled: bool = True
    expires_at: str | None = None
    archived_at: str | None = None
    source_event_id: str = ""
    created_by: str = ""
    valid_from: str | None = None
    valid_until: str | None = None
    supersedes_memory_id: str | None = None
    remembered_reason: str | None = None
    updated_at: str | None = None
    last_used_at: str | None = None


@dataclass(frozen=True)
class ObservationView(View):
    """MEM-04 — one eidetic observation, as the owner reads it.

    Everything here is metadata *about* material the runtime saw. There is no
    field carrying the material itself, and that is deliberate rather than
    incidental: the point of an observation is that it makes recall possible
    without making a second ungoverned copy of everything the agent has read.
    """

    observation_id: str
    session_id: str
    turn_id: str
    tool_name: str
    source_type: str
    summary: str
    sensitivity: str
    retention: str
    capture_status: str
    skip_reason: str
    promotable_to_memory: bool
    content_sha256: str
    content_bytes: int
    artifact_ref: str | None
    source_event_id: str
    created_at: str
    expires_at: str
    gist_status: str = ""
    gist_summary: str = ""
    gist_id: str = ""


class EmbeddingSpaceView(TypedDict):
    """One embedding space: the vectors a backend produces and whether they mean anything."""

    backend_id: str
    kind: Literal["lexical_fallback", "local_model", "provider"]
    model: str
    dimensions: int
    semantic: bool
    reason_code: str
    #: Only on ``retrieval``: whether a question can be embedded into this space
    #: at read time. A listed space carries no read-path claim.
    query_embeddable: NotRequired[bool]


class EmbeddingProviderView(TypedDict):
    """An embedding model this install could call, and what is waiting to be embedded by it."""

    profile_id: str
    provider: str
    model: str
    #: The label the vectors will carry, and so the space that becomes selectable.
    space: str
    local_only: bool
    requires_network: bool
    unindexed_memories: int
    unindexed_file_chunks: int
    pending_count: int


@dataclass(frozen=True)
class MemorySettingsView(View):
    incognito: bool
    #: MEM-03 — which embedding space recall searches, and what is selectable.
    #: `retrieval` is what is in force *now*, including the reason a weaker
    #: backend is in force; `spaces` is what this workspace actually holds
    #: vectors in, which is the only thing worth offering as a choice.
    embedding_backend: str = "auto"
    retrieval: EmbeddingSpaceView | None = None
    spaces: tuple[EmbeddingSpaceView, ...] = ()
    #: MEM-10 - what it would take to have a semantic space at all. `spaces`
    #: above is read from the vectors that exist, so on a default install it
    #: holds only the lexical fallback and the page can offer no better choice.
    #: These two say why: the embedding models this install could call, and how
    #: many approved memories are waiting to be embedded into one.
    embedding_providers: tuple[EmbeddingProviderView, ...] = ()
    unindexed_memories: int = 0
    unindexed_file_chunks: int = 0
    #: The retrieval implementation, stated separately from the embedding model:
    #: the owner should not have to infer whether growing history changes lookup.
    vector_search_strategy: Literal["exact_then_approximate"] = "exact_then_approximate"
    vector_search_exact_limit: int = 512
