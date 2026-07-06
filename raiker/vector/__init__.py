from __future__ import annotations

import hashlib
import math
import re
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
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start += chunk_size - overlap
        return chunks
