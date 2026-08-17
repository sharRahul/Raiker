"""High-fidelity observation metadata; raw payloads stay in governed artifacts."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta

from raiker.contracts.ids import new_id, utc_now
from raiker.storage.sqlite import SQLiteStore

#: Retention classes an observation may carry, and how many days each keeps the
#: row. ``None`` means "no automatic expiry" — the owner deletes it or nothing
#: does. These are the classes `EIDETIC_MEMORY_AND_LEARNING_SPEC.md` names; the
#: two without a day count are the two that document says are never swept.
RETENTION_DAYS: dict[str, int | None] = {
    "turn_only": 0,
    "short_term_7_days": 7,
    "short_term_30_days": 30,
    "project_lifetime": None,
    "until_forget": None,
    "legal_hold": None,
}

#: An observation the runtime *refused* to capture is still a row. Recording the
#: refusal is what makes an empty Observations list readable: nothing captured
#: because nothing ran looks identical, from the owner's side, to nothing
#: captured because everything was credential-shaped.
CAPTURED = "captured"
SKIPPED = "skipped"


def _expiry_for(retention: str, created_at: str) -> str:
    days = RETENTION_DAYS.get(retention)
    if days is None:
        return ""
    moment = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    return (moment + timedelta(days=days)).isoformat().replace("+00:00", "Z")


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
    owner_principal_id: str = ""
    turn_id: str = ""
    tool_name: str = ""
    source_type: str = "tool_result"
    sensitivity: str = "unknown"
    capture_status: str = CAPTURED
    skip_reason: str = ""
    promotable_to_memory: bool = False
    content_bytes: int = 0
    expires_at: str = ""


@dataclass(frozen=True)
class GistMemory:
    gist_id: str
    observation_id: str
    summary: str
    confidence: float
    status: str
    created_at: str


_INSERT_COLUMNS = (
    "observation_id", "source_event_id", "session_id", "summary", "content_sha256",
    "retention", "artifact_ref", "created_at", "owner_principal_id", "turn_id",
    "tool_name", "source_type", "sensitivity", "capture_status", "skip_reason",
    "promotable_to_memory", "content_bytes", "expires_at",
)


def record_observation(
    *,
    store: SQLiteStore,
    source_event_id: str,
    session_id: str,
    summary: str,
    content: str,
    retention: str = "short_term_30_days",
    artifact_ref: str | None = None,
    owner_principal_id: str = "",
    turn_id: str = "",
    tool_name: str = "",
    source_type: str = "tool_result",
    sensitivity: str = "unknown",
    capture_status: str = CAPTURED,
    skip_reason: str = "",
    promotable_to_memory: bool = False,
) -> EideticObservation:
    if retention not in RETENTION_DAYS:
        raise ValueError("invalid_observation_retention")
    if capture_status not in {CAPTURED, SKIPPED}:
        raise ValueError("invalid_observation_capture_status")
    created_at = utc_now()
    # A skipped observation carries no checksum of the material it refused: a
    # digest of a credential is still a fact about the credential, and the row
    # exists to say "this was not kept", not to keep a fingerprint of it.
    digest = "" if capture_status == SKIPPED else hashlib.sha256(content.encode()).hexdigest()
    item = EideticObservation(
        observation_id=new_id("obs_"),
        source_event_id=source_event_id,
        session_id=session_id,
        summary=summary,
        content_sha256=digest,
        retention=retention,
        artifact_ref=artifact_ref,
        created_at=created_at,
        owner_principal_id=owner_principal_id,
        turn_id=turn_id,
        tool_name=tool_name,
        source_type=source_type,
        sensitivity=sensitivity,
        capture_status=capture_status,
        skip_reason=skip_reason,
        promotable_to_memory=promotable_to_memory,
        content_bytes=0 if capture_status == SKIPPED else len(content.encode()),
        expires_at=_expiry_for(retention, created_at),
    )
    values = tuple(
        int(value) if isinstance(value, bool) else value
        for value in (getattr(item, column) for column in _INSERT_COLUMNS)
    )
    with store.connect() as connection:
        connection.execute(
            f"INSERT INTO eidetic_observations ({', '.join(_INSERT_COLUMNS)}) "
            f"VALUES ({', '.join('?' * len(_INSERT_COLUMNS))})",
            values,
        )
    return item


def propose_gist(
    *, store: SQLiteStore, observation_id: str, summary: str, confidence: float
) -> GistMemory:
    if not 0 <= confidence <= 1 or not summary.strip():
        raise ValueError("invalid_gist")
    gist = GistMemory(new_id("mem_"), observation_id, summary.strip(), confidence, "pending_review", utc_now())
    with store.connect() as connection:
        row = connection.execute(
            "SELECT capture_status FROM eidetic_observations WHERE observation_id = ?",
            (observation_id,),
        ).fetchone()
        if row is None:
            raise ValueError("unknown_observation")
        # A refusal has nothing to compress. Proposing a gist from one would put
        # a summary of material the runtime declined to keep in front of the
        # owner as a memory candidate.
        if str(row["capture_status"]) == SKIPPED:
            raise ValueError("observation_not_capturable")
        connection.execute(
            "INSERT INTO gist_memories (gist_id, observation_id, summary, confidence, status, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            tuple(gist.__dict__.values()),
        )
    return gist


def list_observations(
    *, store: SQLiteStore, owner_principal_id: str, limit: int = 200
) -> list[EideticObservation]:
    """Every observation this owner recorded, newest first.

    Owner-scoped on the read rather than filtered afterwards: rows written
    before this scoping existed carry an empty owner and belong to nobody, so
    they are not another owner's to see either.
    """
    with store.connect() as connection:
        rows = connection.execute(
            f"SELECT {', '.join(_INSERT_COLUMNS)} FROM eidetic_observations"
            " WHERE owner_principal_id = ? ORDER BY created_at DESC, observation_id DESC LIMIT ?",
            (owner_principal_id, max(1, min(int(limit), 1000))),
        ).fetchall()
    return [
        EideticObservation(
            observation_id=str(row["observation_id"]),
            source_event_id=str(row["source_event_id"]),
            session_id=str(row["session_id"]),
            summary=str(row["summary"]),
            content_sha256=str(row["content_sha256"]),
            retention=str(row["retention"]),
            artifact_ref=(str(row["artifact_ref"]) if row["artifact_ref"] else None),
            created_at=str(row["created_at"]),
            owner_principal_id=str(row["owner_principal_id"]),
            turn_id=str(row["turn_id"] or ""),
            tool_name=str(row["tool_name"] or ""),
            source_type=str(row["source_type"] or "tool_result"),
            sensitivity=str(row["sensitivity"] or "unknown"),
            capture_status=str(row["capture_status"] or CAPTURED),
            skip_reason=str(row["skip_reason"] or ""),
            promotable_to_memory=bool(row["promotable_to_memory"]),
            content_bytes=int(row["content_bytes"] or 0),
            expires_at=str(row["expires_at"] or ""),
        )
        for row in rows
    ]


def delete_observations(
    *, store: SQLiteStore, owner_principal_id: str, observation_ids: set[str]
) -> list[str]:
    """Owner-invoked deletion of named observations, scoped to their owner.

    Separate from the expiry cleanup below on purpose: that path only removes
    what a preview already said was due, which is right for a sweep and wrong
    for "delete this one now" — the control the rest of memory has.
    """
    if not observation_ids:
        raise ValueError("observation_ids_required")
    deleted: list[str] = []
    with store.connect() as connection:
        for observation_id in sorted(observation_ids):
            cursor = connection.execute(
                "DELETE FROM eidetic_observations WHERE observation_id = ? AND owner_principal_id = ?",
                (observation_id, owner_principal_id),
            )
            if cursor.rowcount:
                deleted.append(observation_id)
    return deleted


def expiry_preview(*, store: SQLiteStore, now: str) -> list[str]:
    days = {name: value for name, value in RETENTION_DAYS.items() if value is not None}
    current = datetime.fromisoformat(now.replace("Z", "+00:00"))
    with store.connect() as connection:
        rows = connection.execute("SELECT observation_id, retention, created_at FROM eidetic_observations").fetchall()
    return [str(row["observation_id"]) for row in rows if row["retention"] in days and datetime.fromisoformat(str(row["created_at"]).replace("Z", "+00:00")) + timedelta(days=days[str(row["retention"])]) <= current]


def cleanup_expired_observations(*, store: SQLiteStore, now: str, confirmed_ids: set[str]) -> list[str]:
    """Owner invokes this explicit, idempotent cleanup after inspecting a preview."""
    due = set(expiry_preview(store=store, now=now))
    if not confirmed_ids or not confirmed_ids.issubset(due):
        raise PermissionError("eidetic_cleanup_confirmation_required")
    with store.connect() as connection:
        connection.executemany("DELETE FROM eidetic_observations WHERE observation_id = ?", ((item,) for item in sorted(confirmed_ids)))
    return sorted(confirmed_ids)
