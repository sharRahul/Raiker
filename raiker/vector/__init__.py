from __future__ import annotations

import hashlib
import math
import re
from collections import defaultdict
from typing import Any

# Name recorded on every locally-created embedding record. Bump the suffix if the
# embedding function below changes, so stored vectors stay attributable to the
# exact algorithm that produced them.
LOCAL_EMBEDDING_MODEL = "raiker-local-hash-v1"

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def embed_text(text: str, dimensions: int = 384) -> list[float]:
    """Deterministic, local, dependency-free text embedding (the hashing trick).

    Tokens are lowercased alphanumeric runs; each token is hashed to a bucket in
    ``[0, dimensions)`` with a sign bit, and its contribution accumulates into
    that bucket. The resulting vector is L2-normalized. This is a genuine,
    reproducible embedding (a feature-hashing / bag-of-tokens vector) computed
    entirely offline — no model download, no network, no external call. It
    captures **lexical** overlap, not learned semantics; a model-backed semantic
    embedding is a separate, egress-gated slice (``model_provider_runtime``).
    """
    if dimensions <= 0:
        raise ValueError("dimensions must be positive")
    vector = [0.0] * dimensions
    for token in _TOKEN_RE.findall(text.lower()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[bucket] += sign
    norm = math.sqrt(sum(v * v for v in vector))
    if norm > 0.0:
        vector = [v / norm for v in vector]
    return vector


class VectorIndex:
    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions
        self._vectors: dict[str, list[float]] = {}
        self._metadata: dict[str, dict[str, Any]] = {}

    def upsert(self, vector_id: str, vector: list[float], metadata: dict[str, Any] | None = None) -> None:
        if len(vector) != self.dimensions:
            raise ValueError(f"expected {self.dimensions} dimensions, got {len(vector)}")
        self._vectors[vector_id] = vector
        self._metadata[vector_id] = metadata or {}

    def delete(self, vector_id: str) -> bool:
        self._vectors.pop(vector_id, None)
        return self._metadata.pop(vector_id, None) is not None

    def search(self, query_vector: list[float], top_k: int = 10) -> list[dict[str, Any]]:
        if not self._vectors:
            return []
        scores: list[tuple[float, str]] = []
        for vid, vec in self._vectors.items():
            score = self._cosine_similarity(query_vector, vec)
            scores.append((score, vid))
        scores.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, vid in scores[:top_k]:
            results.append({"vector_id": vid, "score": round(score, 6), "metadata": self._metadata.get(vid, {})})
        return results

    def count(self) -> int:
        return len(self._vectors)

    def flush(self) -> dict[str, Any]:
        snapshot = {
            "dimensions": self.dimensions,
            "vectors": {vid: vec for vid, vec in self._vectors.items()},
            "metadata": self._metadata,
        }
        self._vectors.clear()
        self._metadata.clear()
        return snapshot

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        dot = sum(av * bv for av, bv in zip(a, b, strict=False))
        na = math.sqrt(sum(av * av for av in a))
        nb = math.sqrt(sum(bv * bv for bv in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    @staticmethod
    def compute_content_hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 512, overlap: int = 64) -> list[str]:
        # An overlap at or above the chunk size advances the cursor by zero or
        # less, so the loop never reaches the end of the text and the chunk list
        # grows until the process dies. Fail on the argument instead.
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if not 0 <= overlap < chunk_size:
            raise ValueError("overlap must be non-negative and smaller than chunk_size")
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start += chunk_size - overlap
        return chunks


class ApproximateVectorIndex(VectorIndex):
    """Bounded LSH candidate lookup with exact cosine re-ranking.

    The vector store is deliberately simple SQLite, which made every recall
    rebuild an in-memory index and linearly compare every vector.  This index
    keeps that exact path for small corpora, then uses deterministic sparse
    random-projection buckets to find a bounded candidate set.  Candidate scores
    are always re-ranked with the same exact cosine calculation ``VectorIndex``
    has always used, so approximation affects which vectors are considered, not
    what a displayed score means.

    The projections contain no model text or owner data: their layout is derived
    solely from ``dimensions``, table and bit number.  They are intentionally
    process-local; ``MemoryVectorIndexCache`` owns freshness against SQLite.
    """

    #: Below this count exact search is faster and gives a stronger result.
    EXACT_SEARCH_LIMIT = 512
    _TABLES = 10
    _BITS_PER_TABLE = 12
    _SPARSE_DIMENSIONS = 12
    _MIN_CANDIDATES = 96

    def __init__(self, dimensions: int = 384) -> None:
        super().__init__(dimensions)
        self._buckets: list[dict[int, set[str]]] = [defaultdict(set) for _ in range(self._TABLES)]
        self._signatures: dict[str, tuple[int, ...]] = {}
        self._projections = tuple(
            tuple(
                tuple(
                    self._projection_sample(dimensions, table, bit, sample)
                    for sample in range(self._SPARSE_DIMENSIONS)
                )
                for bit in range(self._BITS_PER_TABLE)
            )
            for table in range(self._TABLES)
        )

    def upsert(self, vector_id: str, vector: list[float], metadata: dict[str, Any] | None = None) -> None:
        previous = self._signatures.pop(vector_id, None)
        if previous is not None:
            for table, signature in enumerate(previous):
                self._buckets[table][signature].discard(vector_id)
        super().upsert(vector_id, vector, metadata)
        signatures = self._signatures_for(vector)
        self._signatures[vector_id] = signatures
        for table, signature in enumerate(signatures):
            self._buckets[table][signature].add(vector_id)

    def delete(self, vector_id: str) -> bool:
        signatures = self._signatures.pop(vector_id, None)
        if signatures is not None:
            for table, signature in enumerate(signatures):
                self._buckets[table][signature].discard(vector_id)
        return super().delete(vector_id)

    def search(self, query_vector: list[float], top_k: int = 10) -> list[dict[str, Any]]:
        if len(query_vector) != self.dimensions:
            raise ValueError(f"expected {self.dimensions} dimensions, got {len(query_vector)}")
        if len(self._vectors) < self.EXACT_SEARCH_LIMIT:
            return super().search(query_vector, top_k)
        candidates = self._candidates(query_vector)
        # A sparse or adversarially-shaped corpus may not populate enough LSH
        # buckets.  Falling back to the exact path makes recall quality fail-safe
        # rather than silently dropping the one relevant memory.
        if len(candidates) < max(int(top_k), self._MIN_CANDIDATES):
            return super().search(query_vector, top_k)
        scores = [
            (self._cosine_similarity(query_vector, self._vectors[vector_id]), vector_id)
            for vector_id in candidates
        ]
        scores.sort(key=lambda item: (-item[0], item[1]))
        return [
            {
                "vector_id": vector_id,
                "score": round(score, 6),
                "metadata": self._metadata.get(vector_id, {}),
            }
            for score, vector_id in scores[:top_k]
        ]

    def _candidates(self, query_vector: list[float]) -> set[str]:
        candidates: set[str] = set()
        for table, signature in enumerate(self._signatures_for(query_vector)):
            candidates.update(self._buckets[table].get(signature, ()))
            if len(candidates) >= self._MIN_CANDIDATES:
                continue
            # One-bit neighbours preserve the usual near-boundary LSH hits while
            # keeping the work bounded (12 extra bucket reads per table).
            for bit in range(self._BITS_PER_TABLE):
                candidates.update(self._buckets[table].get(signature ^ (1 << bit), ()))
                if len(candidates) >= self._MIN_CANDIDATES:
                    break
        return candidates

    def _signatures_for(self, vector: list[float]) -> tuple[int, ...]:
        signatures: list[int] = []
        for table_projections in self._projections:
            signature = 0
            for bit, samples in enumerate(table_projections):
                projection = sum(vector[dimension] * sign for dimension, sign in samples)
                if projection >= 0.0:
                    signature |= 1 << bit
            signatures.append(signature)
        return tuple(signatures)

    @staticmethod
    def _projection_sample(dimensions: int, table: int, bit: int, sample: int) -> tuple[int, float]:
        digest = hashlib.blake2s(
            f"raiker-ann-v1:{dimensions}:{table}:{bit}:{sample}".encode(), digest_size=8
        ).digest()
        return int.from_bytes(digest[:4], "big") % dimensions, 1.0 if digest[4] & 1 else -1.0


class MemoryVectorIndexCache:
    """Revision-aware cache around an ``ApproximateVectorIndex``.

    Callers provide a database revision and a loader.  The loader is invoked
    only after a relevant memory/vector mutation, so an ordinary turn no longer
    pays to decode every stored embedding before it can answer.
    """

    def __init__(self) -> None:
        self._revision: int | None = None
        self._index: ApproximateVectorIndex | None = None

    def search(
        self,
        *,
        revision: int,
        dimensions: int,
        query_vector: list[float],
        top_k: int,
        load: Any,
    ) -> list[dict[str, Any]]:
        if self._revision != revision or self._index is None or self._index.dimensions != dimensions:
            index = ApproximateVectorIndex(dimensions)
            for row in load():
                try:
                    vector = row["vector"]
                    if isinstance(vector, list) and len(vector) == dimensions:
                        index.upsert(str(row["vector_id"]), vector, dict(row.get("metadata", {})))
                except (KeyError, TypeError, ValueError):
                    continue
            self._index = index
            self._revision = revision
        return self._index.search(query_vector, top_k)
