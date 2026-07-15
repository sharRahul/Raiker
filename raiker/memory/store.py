from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from raiker.contracts.ids import new_id, utc_now
from raiker.memory.policy import classify_memory_sensitivity
from raiker.storage.sqlite import SQLiteStore


@dataclass(frozen=True)
class MemoryEntry:
    memory_id: str
    text: str
    scope: str
    sensitivity: str
    source_event_id: str
    memory_type: str
    created_at: str
    tags: tuple[str, ...]
    source: str
    provenance: dict[str, Any]
    confidence: float
    trust_score: float
    retention: str
    approval_state: str
    created_by: str
    updated_at: str | None = None
    deleted_at: str | None = None
    archived_at: str | None = None
    search_enabled: bool = True
    expires_at: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    supersedes_memory_id: str | None = None
    superseded_at: str | None = None
    remembered_reason: str | None = None


@dataclass(frozen=True)
class MemoryGovernance:
    source_event_id: str
    source_session_id: str
    source_turn_id: str | None
    source_type: str
    confidence: float
    trust_score: float
    retention: str
    approval_state: str
    created_by: str


@dataclass(frozen=True)
class MemoryForgetGovernance:
    source_event_id: str
    source_session_id: str
    source_turn_id: str | None
    source_type: str
    deleted_by: str


def _memory_dir(workspace_root: str | Path) -> Path:
    d = Path(workspace_root).resolve() / ".raiker" / "memory"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _entry_path(memory_dir: Path, memory_id: str) -> Path:
    return memory_dir / f"{memory_id}.md"


def _encode_frontmatter(entry: MemoryEntry) -> str:
    meta: dict[str, object] = {
        "memory_id": entry.memory_id,
        "scope": entry.scope,
        "sensitivity": entry.sensitivity,
        "source_event_id": entry.source_event_id,
        "memory_type": entry.memory_type,
        "created_at": entry.created_at,
        "tags": list(entry.tags),
        "source": entry.source,
        "provenance": entry.provenance,
        "confidence": entry.confidence,
        "trust_score": entry.trust_score,
        "retention": entry.retention,
        "approval_state": entry.approval_state,
        "created_by": entry.created_by,
        "updated_at": entry.updated_at,
        "deleted_at": entry.deleted_at,
        "archived_at": entry.archived_at,
        "search_enabled": entry.search_enabled,
        "expires_at": entry.expires_at,
        "valid_from": entry.valid_from,
        "valid_until": entry.valid_until,
        "supersedes_memory_id": entry.supersedes_memory_id,
        "superseded_at": entry.superseded_at,
        "remembered_reason": entry.remembered_reason,
    }
    return json.dumps(meta, sort_keys=True)


def _decode_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    lines = text.split("\n", 1)
    if len(lines) != 2:
        return {}, text
    try:
        meta = json.loads(lines[0])
    except (json.JSONDecodeError, ValueError):
        return {}, text
    return meta, lines[1]


def write_memory(
    text: str,
    *,
    workspace_root: str | Path = ".",
    scope: str = "project",
    source_event_id: str | None = None,
    memory_type: str = "project",
    tags: tuple[str, ...] = (),
    source: str = "agent",
    store: SQLiteStore | None = None,
    governance: MemoryGovernance | None = None,
) -> MemoryEntry:
    if governance is None:
        raise PermissionError("memory_write_requires_governed_path")
    mem_dir = _memory_dir(workspace_root)
    sensitivity = classify_memory_sensitivity(text)
    memory_id = new_id("mem_")
    entry = MemoryEntry(
        memory_id=memory_id,
        text=text,
        scope=scope,
        sensitivity=sensitivity.value,
        source_event_id=source_event_id or new_id("evt_"),
        memory_type=memory_type,
        created_at=utc_now(),
        tags=tags,
        source=source,
        provenance={
            "source_event_id": governance.source_event_id,
            "source_session_id": governance.source_session_id,
            "source_turn_id": governance.source_turn_id,
            "source_type": governance.source_type,
        },
        confidence=governance.confidence,
        trust_score=governance.trust_score,
        retention=governance.retention,
        approval_state=governance.approval_state,
        created_by=governance.created_by,
    )
    content = _encode_frontmatter(entry) + "\n" + text
    _entry_path(mem_dir, memory_id).write_text(content, encoding="utf-8")
    if store is not None:
        store.insert_approved_memory(entry)
    return entry


def search_memory(
    query: str,
    *,
    workspace_root: str | Path = ".",
    scope: str | None = None,
    max_results: int = 20,
    store: SQLiteStore | None = None,
) -> list[MemoryEntry]:
    if store is not None:
        return [_entry_from_row(row) for row in store.search_approved_memory(query, scope=scope, limit=max_results)]
    query_lower = query.lower()
    results: list[MemoryEntry] = []
    mem_dir = _memory_dir(workspace_root)
    if not mem_dir.exists():
        return results
    paths = sorted(mem_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in paths:
        if path.suffix != ".md":
            continue
        if len(results) >= max_results:
            break
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, body = _decode_frontmatter(text)
        memory_id = meta.get("memory_id") or path.stem
        entry = MemoryEntry(
            memory_id=str(memory_id),
            text=body,
            scope=str(meta.get("scope", "project")),
            sensitivity=str(meta.get("sensitivity", "unknown")),
            source_event_id=str(meta.get("source_event_id", "")),
            memory_type=str(meta.get("memory_type", "project")),
            created_at=str(meta.get("created_at", "")),
            tags=tuple(meta.get("tags", [])),
            source=str(meta.get("source", "agent")),
            provenance=dict(meta.get("provenance", {})),
            confidence=float(meta.get("confidence", 0.0)),
            trust_score=float(meta.get("trust_score", 0.0)),
            retention=str(meta.get("retention", "until_forget")),
            approval_state=str(meta.get("approval_state", "approved")),
            created_by=str(meta.get("created_by", "system")),
            updated_at=meta.get("updated_at"),
            deleted_at=meta.get("deleted_at"),
            archived_at=meta.get("archived_at"),
            search_enabled=bool(meta.get("search_enabled", True)),
            expires_at=meta.get("expires_at"),
            valid_from=meta.get("valid_from"), valid_until=meta.get("valid_until"),
            supersedes_memory_id=meta.get("supersedes_memory_id"), superseded_at=meta.get("superseded_at"),
            remembered_reason=meta.get("remembered_reason"),
        )
        if entry.deleted_at is not None or entry.archived_at is not None or (entry.expires_at is not None and entry.expires_at <= utc_now()):
            continue
        if scope is not None and entry.scope != scope:
            continue
        if entry.search_enabled and (query_lower in body.lower() or query_lower in str(meta.get("tags", []))):
            results.append(entry)
    return results


def forget_memory(
    memory_id: str,
    *,
    workspace_root: str | Path = ".",
    store: SQLiteStore | None = None,
    governance: MemoryForgetGovernance | None = None,
) -> bool:
    if governance is None:
        raise PermissionError("memory_forget_requires_governed_path")
    mem_dir = _memory_dir(workspace_root)
    path = _entry_path(mem_dir, memory_id)
    target = path
    if not target.exists():
        for p in mem_dir.glob("*.md"):
            try:
                content = p.read_text(encoding="utf-8")
            except OSError:
                continue
            if memory_id in content and f'"memory_id": "{memory_id}"' in content:
                target = p
                break
        else:
            return False
    try:
        content = target.read_text(encoding="utf-8")
    except OSError:
        return False
    meta, _ = _decode_frontmatter(content)
    now = utc_now()
    tombstone = MemoryEntry(
        memory_id=str(meta.get("memory_id") or memory_id),
        text="",
        scope=str(meta.get("scope", "project")),
        sensitivity=str(meta.get("sensitivity", "unknown")),
        source_event_id=str(meta.get("source_event_id", governance.source_event_id)),
        memory_type=str(meta.get("memory_type", "project")),
        created_at=str(meta.get("created_at", now)),
        tags=tuple(meta.get("tags", [])),
        source=str(meta.get("source", "agent")),
        provenance=dict(
            meta.get(
                "provenance",
                {
                    "source_event_id": governance.source_event_id,
                    "source_session_id": governance.source_session_id,
                    "source_turn_id": governance.source_turn_id,
                    "source_type": governance.source_type,
                },
            )
        ),
        confidence=float(meta.get("confidence", 0.0)),
        trust_score=float(meta.get("trust_score", 0.0)),
        retention=str(meta.get("retention", "until_forget")),
        approval_state="forgotten",
        created_by=str(meta.get("created_by", governance.deleted_by)),
        updated_at=now,
        deleted_at=now,
    )
    target.write_text(_encode_frontmatter(tombstone) + "\n", encoding="utf-8")
    if store is not None:
        store.mark_approved_memory_forgotten(memory_id, deleted_at=now, updated_at=now)
        store.deactivate_memory_projections(memory_id)
    return True


def set_memory_archived(
    memory_id: str, *, archived: bool, workspace_root: str | Path = ".", store: SQLiteStore | None = None
) -> MemoryEntry | None:
    """Archive/restore a memory without changing its content or provenance."""
    entry = get_memory(memory_id, workspace_root=workspace_root, include_expired=True, include_archived=True)
    if entry is None:
        return None
    updated = replace(entry, archived_at=utc_now() if archived else None, updated_at=utc_now())
    _entry_path(_memory_dir(workspace_root), memory_id).write_text(
        _encode_frontmatter(updated) + "\n" + updated.text, encoding="utf-8"
    )
    if store is not None:
        store.set_approved_memory_archived(memory_id, archived_at=updated.archived_at, updated_at=updated.updated_at)
        store.set_memory_projections_active(memory_id, not archived)
    return updated


def list_memory(
    *,
    workspace_root: str | Path = ".",
    scope: str | None = None,
    limit: int = 50,
    store: SQLiteStore | None = None,
) -> list[MemoryEntry]:
    if store is not None:
        return [_entry_from_row(row) for row in store.list_approved_memory(scope=scope, limit=limit)]
    results: list[MemoryEntry] = []
    mem_dir = _memory_dir(workspace_root)
    if not mem_dir.exists():
        return results
    paths = sorted(mem_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in paths:
        if path.suffix != ".md":
            continue
        if len(results) >= limit:
            break
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, body = _decode_frontmatter(content)
        entry = MemoryEntry(
            memory_id=str(meta.get("memory_id") or path.stem),
            text=body,
            scope=str(meta.get("scope", "project")),
            sensitivity=str(meta.get("sensitivity", "unknown")),
            source_event_id=str(meta.get("source_event_id", "")),
            memory_type=str(meta.get("memory_type", "project")),
            created_at=str(meta.get("created_at", "")),
            tags=tuple(meta.get("tags", [])),
            source=str(meta.get("source", "agent")),
            provenance=dict(meta.get("provenance", {})),
            confidence=float(meta.get("confidence", 0.0)),
            trust_score=float(meta.get("trust_score", 0.0)),
            retention=str(meta.get("retention", "until_forget")),
            approval_state=str(meta.get("approval_state", "approved")),
            created_by=str(meta.get("created_by", "system")),
            updated_at=meta.get("updated_at"),
            deleted_at=meta.get("deleted_at"),
            archived_at=meta.get("archived_at"),
            search_enabled=bool(meta.get("search_enabled", True)),
            expires_at=meta.get("expires_at"),
            valid_from=meta.get("valid_from"), valid_until=meta.get("valid_until"),
            supersedes_memory_id=meta.get("supersedes_memory_id"), superseded_at=meta.get("superseded_at"),
            remembered_reason=meta.get("remembered_reason"),
        )
        if entry.deleted_at is not None or entry.archived_at is not None or (entry.expires_at is not None and entry.expires_at <= utc_now()):
            continue
        if scope is not None and entry.scope != scope:
            continue
        results.append(entry)
    return results


def get_memory(
    memory_id: str,
    *,
    workspace_root: str | Path = ".",
    include_expired: bool = False,
    include_archived: bool = False,
) -> MemoryEntry | None:
    mem_dir = _memory_dir(workspace_root)
    path = _entry_path(mem_dir, memory_id)
    if path.exists():
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return None
        meta, body = _decode_frontmatter(content)
        entry = MemoryEntry(
            memory_id=str(meta.get("memory_id") or memory_id),
            text=body,
            scope=str(meta.get("scope", "project")),
            sensitivity=str(meta.get("sensitivity", "unknown")),
            source_event_id=str(meta.get("source_event_id", "")),
            memory_type=str(meta.get("memory_type", "project")),
            created_at=str(meta.get("created_at", "")),
            tags=tuple(meta.get("tags", [])),
            source=str(meta.get("source", "agent")),
            provenance=dict(meta.get("provenance", {})),
            confidence=float(meta.get("confidence", 0.0)),
            trust_score=float(meta.get("trust_score", 0.0)),
            retention=str(meta.get("retention", "until_forget")),
            approval_state=str(meta.get("approval_state", "approved")),
            created_by=str(meta.get("created_by", "system")),
            updated_at=meta.get("updated_at"),
            deleted_at=meta.get("deleted_at"),
            archived_at=meta.get("archived_at"),
            search_enabled=bool(meta.get("search_enabled", True)),
            expires_at=meta.get("expires_at"),
            valid_from=meta.get("valid_from"), valid_until=meta.get("valid_until"),
            supersedes_memory_id=meta.get("supersedes_memory_id"), superseded_at=meta.get("superseded_at"),
            remembered_reason=meta.get("remembered_reason"),
        )
        if entry.deleted_at is not None or (not include_archived and entry.archived_at is not None) or (
            not include_expired and entry.expires_at is not None and entry.expires_at <= utc_now()
        ):
            return None
        return entry
    for p in mem_dir.glob("*.md"):
        try:
            content = p.read_text(encoding="utf-8")
        except OSError:
            continue
        if memory_id in content:
            meta, body = _decode_frontmatter(content)
            entry = MemoryEntry(
                memory_id=str(meta.get("memory_id") or p.stem),
                text=body,
                scope=str(meta.get("scope", "project")),
                sensitivity=str(meta.get("sensitivity", "unknown")),
                source_event_id=str(meta.get("source_event_id", "")),
                memory_type=str(meta.get("memory_type", "project")),
                created_at=str(meta.get("created_at", "")),
                tags=tuple(meta.get("tags", [])),
                source=str(meta.get("source", "agent")),
                provenance=dict(meta.get("provenance", {})),
                confidence=float(meta.get("confidence", 0.0)),
                trust_score=float(meta.get("trust_score", 0.0)),
                retention=str(meta.get("retention", "until_forget")),
                approval_state=str(meta.get("approval_state", "approved")),
                created_by=str(meta.get("created_by", "system")),
                updated_at=meta.get("updated_at"),
                deleted_at=meta.get("deleted_at"),
                archived_at=meta.get("archived_at"),
                search_enabled=bool(meta.get("search_enabled", True)),
                expires_at=meta.get("expires_at"),
                valid_from=meta.get("valid_from"), valid_until=meta.get("valid_until"),
                supersedes_memory_id=meta.get("supersedes_memory_id"), superseded_at=meta.get("superseded_at"),
                remembered_reason=meta.get("remembered_reason"),
            )
            if entry.deleted_at is not None or (
                not include_expired and entry.expires_at is not None and entry.expires_at <= utc_now()
            ):
                return None
            return entry
    return None


def update_memory(
    memory_id: str, *, workspace_root: str | Path = ".", text: str | None = None,
    search_enabled: bool | None = None, expires_at: str | None = None,
    update_expires_at: bool = False,
    store: SQLiteStore | None = None,
) -> MemoryEntry | None:
    entry = get_memory(memory_id, workspace_root=workspace_root, include_expired=True)
    if entry is None:
        return None
    updated = replace(
        entry,
        text=entry.text if text is None else text,
        sensitivity=entry.sensitivity if text is None else classify_memory_sensitivity(text).value,
        search_enabled=entry.search_enabled if search_enabled is None else search_enabled,
        expires_at=expires_at if update_expires_at else entry.expires_at,
        updated_at=utc_now(),
    )
    _entry_path(_memory_dir(workspace_root), memory_id).write_text(
        _encode_frontmatter(updated) + "\n" + updated.text, encoding="utf-8"
    )
    if store is not None:
        store.update_approved_memory(updated)
    return updated


def correct_memory(
    memory_id: str, text: str, *, workspace_root: str | Path = ".", store: SQLiteStore,
    governance: MemoryGovernance, remembered_reason: str,
) -> MemoryEntry | None:
    """Create a replacement fact, preserving the corrected record as evidence."""
    original = get_memory(memory_id, workspace_root=workspace_root, include_expired=True, include_archived=True)
    if original is None or not text.strip() or not remembered_reason.strip():
        return None
    replacement = write_memory(
        text, workspace_root=workspace_root, scope=original.scope, source_event_id=governance.source_event_id,
        memory_type=original.memory_type, tags=original.tags, source="human_correction", store=store,
        governance=governance,
    )
    replacement = replace(replacement, remembered_reason=remembered_reason.strip(), supersedes_memory_id=memory_id)
    _entry_path(_memory_dir(workspace_root), replacement.memory_id).write_text(
        _encode_frontmatter(replacement) + "\n" + replacement.text, encoding="utf-8"
    )
    store.update_approved_memory(replacement)
    if not store.supersede_approved_memory(memory_id, replacement.memory_id, at=utc_now()):
        return None
    return replacement


def _entry_from_row(row: dict[str, Any]) -> MemoryEntry:
    return MemoryEntry(
        memory_id=str(row["memory_id"]), text=str(row["text"]), scope=str(row["scope"]),
        sensitivity=str(row["sensitivity"]), source_event_id=str(row["source_event_id"]),
        memory_type=str(row["memory_type"]), created_at=str(row["created_at"]),
        tags=tuple(json.loads(str(row["tags_json"]))), source=str(row["source"]),
        provenance=json.loads(str(row["provenance_json"])), confidence=float(row["confidence"]),
        trust_score=float(row["trust_score"]), retention=str(row["retention"]),
        approval_state=str(row["approval_state"]), created_by=str(row["created_by"]),
        updated_at=row["updated_at"], deleted_at=row["deleted_at"], archived_at=row["archived_at"],
        search_enabled=bool(row["search_enabled"]), expires_at=row["expires_at"],
        valid_from=row["valid_from"], valid_until=row["valid_until"],
        supersedes_memory_id=row["supersedes_memory_id"], superseded_at=row["superseded_at"],
        remembered_reason=row["remembered_reason"],
    )


def memory_status(*, workspace_root: str | Path = ".") -> dict[str, object]:
    entries = list_memory(workspace_root=workspace_root)
    return {
        "approved_memory_count": len(entries),
        "memory_store": "markdown_files",
        "persistence_path": str(_memory_dir(workspace_root)),
        "tags": sorted(
            set(tag for e in entries for tag in e.tags)
        ),
    }
