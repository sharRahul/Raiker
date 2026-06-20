from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from raiker.contracts.ids import new_id, utc_now
from raiker.memory.policy import MemorySensitivity, classify_memory_sensitivity
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
) -> MemoryEntry:
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
        if not path.suffix == ".md":
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
        )
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
) -> bool:
    mem_dir = _memory_dir(workspace_root)
    path = _entry_path(mem_dir, memory_id)
    if not path.exists():
        for p in mem_dir.glob("*.md"):
            try:
                content = p.read_text(encoding="utf-8")
            except OSError:
                continue
            if memory_id in content and f'"memory_id": "{memory_id}"' in content:
                p.unlink()
                if store is not None:
                    store.delete_approved_memory(memory_id)
                return True
        return False
    path.unlink()
    if store is not None:
        store.delete_approved_memory(memory_id)
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
        if not path.suffix == ".md":
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
        )
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
        return MemoryEntry(
            memory_id=str(meta.get("memory_id") or memory_id),
            text=body,
            scope=str(meta.get("scope", "project")),
            sensitivity=str(meta.get("sensitivity", "unknown")),
            source_event_id=str(meta.get("source_event_id", "")),
            memory_type=str(meta.get("memory_type", "project")),
            created_at=str(meta.get("created_at", "")),
            tags=tuple(meta.get("tags", [])),
            source=str(meta.get("source", "agent")),
        )
    for p in mem_dir.glob("*.md"):
        try:
            content = p.read_text(encoding="utf-8")
        except OSError:
            continue
        if memory_id in content:
            meta, body = _decode_frontmatter(content)
            return MemoryEntry(
                memory_id=str(meta.get("memory_id") or p.stem),
                text=body,
                scope=str(meta.get("scope", "project")),
                sensitivity=str(meta.get("sensitivity", "unknown")),
                source_event_id=str(meta.get("source_event_id", "")),
                memory_type=str(meta.get("memory_type", "project")),
                created_at=str(meta.get("created_at", "")),
                tags=tuple(meta.get("tags", [])),
                source=str(meta.get("source", "agent")),
            )
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
