from __future__ import annotations

import json
from dataclasses import dataclass
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
        )
        if entry.deleted_at is not None:
            continue
        if scope is not None and entry.scope != scope:
            continue
        if query_lower in body.lower() or query_lower in str(meta.get("tags", [])):
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
    return True


def list_memory(
    *,
    workspace_root: str | Path = ".",
    scope: str | None = None,
    limit: int = 50,
) -> list[MemoryEntry]:
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
        )
        if entry.deleted_at is not None:
            continue
        if scope is not None and entry.scope != scope:
            continue
        results.append(entry)
    return results


def get_memory(
    memory_id: str,
    *,
    workspace_root: str | Path = ".",
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
        )
        if entry.deleted_at is not None:
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
            )
            if entry.deleted_at is not None:
                return None
            return entry
    return None


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
