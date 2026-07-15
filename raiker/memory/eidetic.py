"""High-fidelity observation metadata; raw payloads stay in governed artifacts."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from raiker.contracts.ids import new_id, utc_now
from raiker.storage.sqlite import SQLiteStore


@dataclass(frozen=True)
class EideticObservation:
    observation_id: str
    source_event_id: str
    session_id: str
    summary: str
    content_sha256: str
    retention: str
    artifact_ref: str | None
    created_at: str


@dataclass(frozen=True)
class GistMemory:
    gist_id: str
    observation_id: str
    summary: str
    confidence: float
    status: str
    created_at: str


def record_observation(*, store: SQLiteStore, source_event_id: str, session_id: str, summary: str, content: str, retention: str = "short_term_30_days", artifact_ref: str | None = None) -> EideticObservation:
    if retention not in {"turn_only", "short_term_7_days", "short_term_30_days", "project_lifetime", "until_forget", "legal_hold"}:
        raise ValueError("invalid_observation_retention")
    item = EideticObservation(new_id("obs_"), source_event_id, session_id, summary, hashlib.sha256(content.encode()).hexdigest(), retention, artifact_ref, utc_now())
    with store.connect() as connection:
        connection.execute("INSERT INTO eidetic_observations (observation_id, source_event_id, session_id, summary, content_sha256, retention, artifact_ref, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", tuple(item.__dict__.values()))
    return item


def propose_gist(*, store: SQLiteStore, observation_id: str, summary: str, confidence: float) -> GistMemory:
    if not 0 <= confidence <= 1 or not summary.strip():
        raise ValueError("invalid_gist")
    gist = GistMemory(new_id("mem_"), observation_id, summary.strip(), confidence, "pending_review", utc_now())
    with store.connect() as connection:
        if connection.execute("SELECT 1 FROM eidetic_observations WHERE observation_id = ?", (observation_id,)).fetchone() is None:
            raise ValueError("unknown_observation")
        connection.execute("INSERT INTO gist_memories VALUES (?, ?, ?, ?, ?, ?)", tuple(gist.__dict__.values()))
    return gist
