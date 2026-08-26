"""Which embedding actually produced a vector, and which one may read it.

MEM-03 — ``retrieve_hybrid_memory`` presented three legs as hybrid retrieval,
but the vector leg called :func:`raiker.vector.embed_text`, the hashing trick
over lowercased alphanumeric tokens. Two of the three legs were therefore the
same signal at different weights, and a memory recorded as "the owner prefers
the encrypted NAS target" was not retrieved by "where should backups go".

The fix is not a better hash. It is making the embedding **an owner-selected
backend that names itself**, so that:

* the query is embedded with the *same* backend that produced the stored
  vectors, because a cosine between two different embedding spaces is a number
  with no meaning;
* vectors from two backends are never mixed in one search — the storage layer
  already fetches exactly one ``embedding_model``, and this module is what
  decides which one that is;
* a workspace that has not chosen a semantic backend keeps working, with the
  hashing embedding **labelled** as the lexical fallback it is, rather than
  presented as semantics that are not there.

Nothing here performs egress on its own. A provider backend is a description of
a choice the owner already made; the call itself still goes through
``model_provider_runtime``, which re-checks the egress allowlist, the provider
gate state and credential presence on every use.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from raiker.vector import LOCAL_EMBEDDING_MODEL, embed_text

#: What kind of signal a backend produces. This is the honest part: only
#: ``semantic`` backends can recall a paraphrase, and the interface says which
#: one is in force rather than letting the word "vector" imply the stronger one.
BackendKind = Literal["lexical_fallback", "local_model", "provider"]

#: The dimension every locally-hashed vector has had since the first release.
#: Stored vectors carry their own ``dimensions`` column; this is only the
#: fallback's own answer.
LOCAL_HASH_DIMENSIONS = 384

#: Selector the owner stores. ``auto`` means "the best backend that is actually
#: configured", which on a default install is the lexical fallback.
DEFAULT_SELECTION = "auto"

#: Ceiling on one governed indexing run (MEM-10). A batch is one approval, so it
#: has to be a bounded one: the owner is agreeing to this many provider calls,
#: not to "as many as the workspace happens to hold".
MAX_MEMORY_INDEX_BATCH = 500


@dataclass(frozen=True)
class EmbeddingBackend:
    """A resolved, usable embedding space.

    ``model_label`` is the value written to and read from
    ``vector_records.embedding_model``. It is the identity of the vector space,
    which is why the resolver never returns a backend whose label it cannot also
    use to read back what it wrote.
    """

    backend_id: str
    kind: BackendKind
    model_label: str
    dimensions: int
    #: Why a *better* backend was not selected. Present even on a successful
    #: resolution, because "you are on the fallback" is the answer the owner
    #: needs and an empty string would read as "all is well".
    reason_code: str = ""

    @property
    def semantic(self) -> bool:
        """Whether this space can relate two texts that share no token."""
        return self.kind != "lexical_fallback"

    def embed(self, text: str) -> list[float]:
        """Embed *text* in this space.

        Only the fallback is computed in-process. A ``local_model`` or
        ``provider`` backend is resolvable *for reading* — its stored vectors can
        be searched — but producing a new vector goes through the governed
        executor, so asking this object to do it is a programming error rather
        than a silent downgrade to a different space.
        """
        if self.kind != "lexical_fallback":
            raise EmbeddingBackendUnavailable(
                f"embedding_backend_requires_executor:{self.backend_id}"
            )
        return embed_text(text, self.dimensions)

    def describe(self) -> dict[str, Any]:
        return {
            "backend_id": self.backend_id,
            "kind": self.kind,
            "model": self.model_label,
            "dimensions": self.dimensions,
            "semantic": self.semantic,
            "reason_code": self.reason_code,
        }


class EmbeddingBackendUnavailable(RuntimeError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


#: The always-available floor. Deliberately named as a fallback in its own kind
#: so no surface can render it as a semantic model.
LEXICAL_FALLBACK_BACKEND = EmbeddingBackend(
    backend_id="local_hash",
    kind="lexical_fallback",
    model_label=LOCAL_EMBEDDING_MODEL,
    dimensions=LOCAL_HASH_DIMENSIONS,
    reason_code="embedding_backend_semantic_not_configured",
)


def _provider_backend(model_label: str, dimensions: int) -> EmbeddingBackend:
    return EmbeddingBackend(
        backend_id="provider",
        kind="provider",
        model_label=model_label,
        dimensions=dimensions,
    )


def _local_model_backend(model_label: str, dimensions: int) -> EmbeddingBackend:
    return EmbeddingBackend(
        backend_id="local_model",
        kind="local_model",
        model_label=model_label,
        dimensions=dimensions,
    )


def resolve_embedding_backend(
    store: Any, *, owner_principal_id: str | None = None
) -> EmbeddingBackend:
    """The embedding space this owner's retrieval must use.

    Resolution is **evidence-led, not configuration-led**: a selection that
    names a model with no stored vectors is not a usable space, so it does not
    win. The order is the owner's explicit choice, then any semantic space that
    actually holds vectors, then the labelled fallback.
    """
    selection = DEFAULT_SELECTION
    try:
        selection = store.get_memory_embedding_backend(owner_principal_id) or DEFAULT_SELECTION
    except AttributeError:  # pragma: no cover - a store predating the column
        selection = DEFAULT_SELECTION
    available = list_embedding_spaces(store, owner_principal_id=owner_principal_id)
    if selection != DEFAULT_SELECTION:
        for space in available:
            if space.model_label == selection:
                return space
        # A named selection that has no vectors is a real condition the owner
        # has to see — silently searching a different space would answer from
        # a corpus they did not choose.
        return EmbeddingBackend(
            backend_id="local_hash",
            kind="lexical_fallback",
            model_label=LOCAL_EMBEDDING_MODEL,
            dimensions=LOCAL_HASH_DIMENSIONS,
            reason_code=f"embedding_backend_selected_has_no_vectors:{selection}",
        )
    for space in available:
        if space.semantic:
            return space
    return LEXICAL_FALLBACK_BACKEND


def list_embedding_spaces(
    store: Any, *, owner_principal_id: str | None = None
) -> list[EmbeddingBackend]:
    """Every embedding space this workspace actually holds vectors in.

    Read from the vectors themselves rather than from a registry of what Raiker
    could in principle call: a space is selectable exactly when searching it
    would return something.
    """
    spaces: list[EmbeddingBackend] = []
    try:
        rows = store.list_memory_embedding_spaces(owner_principal_id=owner_principal_id)
    except AttributeError:  # pragma: no cover - a store predating the method
        rows = []
    for row in rows:
        model_label = str(row["embedding_model"])
        dimensions = int(row["dimensions"])
        if model_label == LOCAL_EMBEDDING_MODEL:
            spaces.append(LEXICAL_FALLBACK_BACKEND)
        elif (
            model_label.startswith("local/")
            or model_label.startswith("local:")
            or model_label.startswith("llama.cpp/")
            or model_label.startswith("llama.cpp:")
            or model_label.startswith("ollama:")
        ):
            spaces.append(_local_model_backend(model_label, dimensions))
        else:
            spaces.append(_provider_backend(model_label, dimensions))
    # Semantic spaces first so `auto` picks one without a second pass, then by
    # label for a stable, testable order.
    return sorted(spaces, key=lambda space: (space.kind == "lexical_fallback", space.model_label))


def embedding_capable_profiles() -> list[dict[str, Any]]:
    """The embedding models this install could actually call, named exactly.

    MEM-10 - :func:`list_embedding_spaces` reads the vectors that exist, which
    is right for *choosing* a space and useless for *getting* one: a default
    install holds no semantic vectors, so the choice is between the fallback and
    the fallback. This reads the other direction, from the model profiles, and
    answers "what could produce a semantic space here".

    A profile is listed only when the embedding model it would use is already a
    concrete name. A profile whose embedding model is a placeholder picks its
    model at selection time, so offering it here would be offering a button that
    cannot say what it is about to call - and naming the model is the whole
    point, because the model *is* the identity of the vector space.

    Nothing here performs egress or checks a credential. It is a description of
    what the profiles declare; the call still goes through
    ``model_provider_runtime``, which re-checks the gate, the egress allowlist
    and the credential on every use.
    """
    from raiker.models.registry import ModelProfileRegistry, RegistryError

    try:
        registry = ModelProfileRegistry.load()
    except (RegistryError, OSError, ValueError):  # pragma: no cover - unreadable config
        return []
    listed: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for profile in registry.profiles:
        raw = profile.raw
        if not bool(raw.get("supports_embeddings", False)):
            continue
        embedding_model = str(raw.get("embedding_model") or "")
        if not embedding_model or "<" in embedding_model or ">" in embedding_model:
            continue
        key = (profile.provider, embedding_model)
        if key in seen:
            continue
        seen.add(key)
        listed.append(
            {
                "profile_id": profile.profile_id,
                "provider": profile.provider,
                "model": embedding_model,
                # The label the vectors will carry, and therefore the space the
                # owner will be able to select once the run finishes.
                "space": f"{profile.provider}:{embedding_model}",
                "local_only": bool(profile.local_only),
                "requires_network": bool(profile.requires_network),
            }
        )
    return sorted(listed, key=lambda item: (not item["local_only"], item["space"]))
